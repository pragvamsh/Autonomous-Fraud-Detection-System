import mysql.connector
from mysql.connector import Error

DB_CONFIG = {
    'host': '127.0.0.1',
    'user': 'root',
    'password': 'Nihanth@06',
    'database': 'fraud_detection_test',
    'auth_plugin': 'mysql_native_password'
}


def get_db_connection():
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        return connection
    except Error as e:
        print(f"Error connecting to MySQL: {e}")
        return None


def ensure_tables_exist():
    """
    Creates all required tables if they don't already exist.
    Also runs ALTER TABLE migrations for columns added in later phases.
    Idempotent — safe to call on every startup.
    """
    conn = get_db_connection()
    if not conn:
        print("WARNING: Could not connect to DB to verify table existence.")
        return
    try:
        cursor = conn.cursor()

        # ── customers ───────────────────────────────────────────────────────
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS customers (
                id                INT AUTO_INCREMENT PRIMARY KEY,
                customer_id       VARCHAR(6)    NOT NULL UNIQUE,
                account_number    VARCHAR(12)   NOT NULL UNIQUE,
                full_name         VARCHAR(150)  NOT NULL,
                date_of_birth     DATE          NOT NULL,
                gender            ENUM('male','female','other') NOT NULL,
                is_minor          TINYINT(1)    DEFAULT 0,
                email             VARCHAR(254)  NOT NULL UNIQUE,
                phone_number      VARCHAR(10)   NOT NULL UNIQUE,
                address           TEXT          NOT NULL,
                city              VARCHAR(100)  NOT NULL,
                state             VARCHAR(100)  NOT NULL,
                country           VARCHAR(50)   DEFAULT 'India',
                aadhaar_hash      VARCHAR(255)  NOT NULL UNIQUE,
                pan_number        VARCHAR(10)   NOT NULL UNIQUE,
                account_type      ENUM('savings','current') NOT NULL,
                balance           DECIMAL(15,2) NOT NULL DEFAULT 0.00,
                password_hash     VARCHAR(255),
                password_set      TINYINT(1)    DEFAULT 0,
                is_first_login    TINYINT(1)    DEFAULT 1,
                is_email_verified TINYINT(1)    DEFAULT 0,
                must_change_pw    TINYINT(1)    DEFAULT 1,
                created_at        TIMESTAMP     DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # ── otp_tokens ──────────────────────────────────────────────────────
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS otp_tokens (
                id           INT AUTO_INCREMENT PRIMARY KEY,
                customer_id  VARCHAR(6)   NOT NULL,
                hashed_otp   VARCHAR(255) NOT NULL,
                purpose      ENUM('EMAIL_VERIFY','PASSWORD_CHANGE','FRAUD_MFA') NOT NULL,
                expires_at   DATETIME     NOT NULL,
                used         TINYINT(1)   DEFAULT 0,
                created_at   TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
            )
        """)

        # Patch existing otp_tokens table to add FRAUD_MFA purpose (for ABA OTP verification)
        _safe_alter(cursor, """
            ALTER TABLE otp_tokens
            MODIFY COLUMN purpose ENUM('EMAIL_VERIFY','PASSWORD_CHANGE','FRAUD_MFA') NOT NULL
        """)

        # ── transactions ─────────────────────────────────────────────────────
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id               INT AUTO_INCREMENT PRIMARY KEY,
                transaction_id   VARCHAR(20)   NOT NULL UNIQUE,
                customer_id      VARCHAR(6)    NOT NULL,
                type             ENUM('CREDIT','DEBIT') NOT NULL,
                amount           DECIMAL(15,2) NOT NULL,
                description      VARCHAR(255),
                balance_after    DECIMAL(15,2) NOT NULL,
                created_at       TIMESTAMP     DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
            )
        """)

        # Phase 3 additions — monitoring agent columns
        _safe_alter(cursor, "ALTER TABLE transactions ADD COLUMN recipient_account VARCHAR(12) DEFAULT NULL")
        _safe_alter(cursor, "ALTER TABLE transactions ADD COLUMN risk_score INT DEFAULT NULL")
        _safe_alter(cursor, "ALTER TABLE transactions ADD COLUMN fraud_flag TINYINT(1) DEFAULT 0")
        _safe_alter(cursor, """
            ALTER TABLE transactions
            ADD COLUMN agent_status ENUM('PENDING','EVALUATED','FAILED','SKIPPED') DEFAULT 'PENDING'
        """)

        # ── customer_behaviour_profiles ──────────────────────────────────────
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS customer_behaviour_profiles (
                customer_id              VARCHAR(6)    PRIMARY KEY,
                avg_amount               DECIMAL(15,2) DEFAULT 0.00,
                std_amount               DECIMAL(15,2) DEFAULT 0.00,
                max_single_amount        DECIMAL(15,2) DEFAULT 0.00,
                avg_daily_volume         DECIMAL(15,2) DEFAULT 0.00,
                transaction_frequency    DECIMAL(8,2)  DEFAULT 0.00,
                usual_hour_start         INT           DEFAULT 9,
                usual_hour_end           INT           DEFAULT 18,
                known_recipients_count   INT           DEFAULT 0,
                total_data_points        INT           DEFAULT 0,
                cold_start               TINYINT(1)    DEFAULT 1,
                profile_strength         DECIMAL(4,3)  DEFAULT 0.000,
                last_updated             TIMESTAMP     DEFAULT CURRENT_TIMESTAMP
                                         ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
            )
        """)

        # ── fraud_alerts ─────────────────────────────────────────────────────
        # CREATE TABLE includes all columns from the start for fresh installs.
        # The _safe_alter calls below patch any existing table that was created
        # by an older version of this file — idempotent, safe to run every time.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS fraud_alerts (
                id                      INT AUTO_INCREMENT PRIMARY KEY,
                transaction_id          VARCHAR(20)   NOT NULL,
                customer_id             VARCHAR(6)    NOT NULL,

                risk_score              INT           NOT NULL,
                ml_score                INT           NOT NULL,
                rag_score               INT           DEFAULT NULL,

                decision                ENUM('ALLOW','FLAG','ALERT','BLOCK') NOT NULL,

                anomaly_flags           JSON          DEFAULT NULL,
                rag_citations           JSON          DEFAULT NULL,
                agent_reasoning         TEXT          DEFAULT NULL,

                disagreement            TINYINT(1)    DEFAULT 0,
                rag_available           TINYINT(1)    DEFAULT 1,
                cold_start_profile      TINYINT(1)    DEFAULT 0,
                fallback_mode           TINYINT(1)    DEFAULT 0,
                
                raa_stages              JSON          DEFAULT NULL,

                typology_code           VARCHAR(50)   DEFAULT NULL,
                low_confidence_fallback TINYINT(1)    DEFAULT 0,

                reversal_initiated      TINYINT(1)    DEFAULT 0,
                reversal_success        TINYINT(1)    DEFAULT NULL,

                created_at              TIMESTAMP     DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (transaction_id) REFERENCES transactions(transaction_id),
                FOREIGN KEY (customer_id)    REFERENCES customers(customer_id)
            )
        """)

        # Patch any existing fraud_alerts table that is missing these columns.
        # errno 1060 (duplicate column) is silently ignored by _safe_alter.
        _safe_alter(cursor, "ALTER TABLE fraud_alerts ADD COLUMN rag_score INT DEFAULT NULL")
        _safe_alter(cursor, "ALTER TABLE fraud_alerts ADD COLUMN rag_citations JSON DEFAULT NULL")
        _safe_alter(cursor, "ALTER TABLE fraud_alerts ADD COLUMN agent_reasoning TEXT DEFAULT NULL")
        _safe_alter(cursor, "ALTER TABLE fraud_alerts ADD COLUMN disagreement TINYINT(1) DEFAULT 0")
        _safe_alter(cursor, "ALTER TABLE fraud_alerts ADD COLUMN rag_available TINYINT(1) DEFAULT 1")
        _safe_alter(cursor, "ALTER TABLE fraud_alerts ADD COLUMN cold_start_profile TINYINT(1) DEFAULT 0")
        _safe_alter(cursor, "ALTER TABLE fraud_alerts ADD COLUMN fallback_mode TINYINT(1) DEFAULT 0")
        _safe_alter(cursor, "ALTER TABLE fraud_alerts ADD COLUMN typology_code VARCHAR(50) DEFAULT NULL")
        _safe_alter(cursor, "ALTER TABLE fraud_alerts ADD COLUMN low_confidence_fallback TINYINT(1) DEFAULT 0")
        _safe_alter(cursor, "ALTER TABLE fraud_alerts ADD COLUMN reversal_initiated TINYINT(1) DEFAULT 0")
        _safe_alter(cursor, "ALTER TABLE fraud_alerts ADD COLUMN reversal_success TINYINT(1) DEFAULT NULL")

        # ── PRA columns on fraud_alerts (written by PRA response executor) ────
        _safe_alter(cursor, "ALTER TABLE fraud_alerts ADD COLUMN pra_processed TINYINT(1) NOT NULL DEFAULT 0")
        _safe_alter(cursor, "ALTER TABLE fraud_alerts ADD COLUMN pra_verdict VARCHAR(20) DEFAULT NULL")
        # DECIMAL(6,2) not INT — bilstm_model and pattern_scorer write floats (e.g. 74.83, 88.50)
        _safe_alter(cursor, "ALTER TABLE fraud_alerts ADD COLUMN pattern_score DECIMAL(6,2) DEFAULT NULL")
        _safe_alter(cursor, "ALTER TABLE fraud_alerts ADD COLUMN bilstm_score DECIMAL(6,2) DEFAULT NULL")
        # precedent_adj and reg_adj — written by pra_agent.py from RAG L2/L1 results
        _safe_alter(cursor, "ALTER TABLE fraud_alerts ADD COLUMN precedent_adj DECIMAL(6,2) DEFAULT NULL")
        _safe_alter(cursor, "ALTER TABLE fraud_alerts ADD COLUMN reg_adj DECIMAL(6,2) DEFAULT NULL")
        _safe_alter(cursor, "ALTER TABLE fraud_alerts ADD COLUMN urgency_multiplier DECIMAL(5,3) DEFAULT NULL")
        _safe_alter(cursor, "ALTER TABLE fraud_alerts ADD COLUMN pra_reg_citations JSON DEFAULT NULL")
        _safe_alter(cursor, "ALTER TABLE fraud_alerts ADD COLUMN sequence_length INT DEFAULT NULL")
        _safe_alter(cursor, "ALTER TABLE fraud_alerts ADD COLUMN feature_snapshot JSON DEFAULT NULL")

        # ── RAA columns on fraud_alerts ───────────────────────────────────────
        _safe_alter(cursor, "ALTER TABLE fraud_alerts ADD COLUMN raa_processed TINYINT(1) NOT NULL DEFAULT 0")
        _safe_alter(cursor, "ALTER TABLE fraud_alerts ADD COLUMN raa_verdict VARCHAR(16) DEFAULT NULL")
        _safe_alter(cursor, "ALTER TABLE fraud_alerts ADD COLUMN final_raa_score DECIMAL(6,2) DEFAULT NULL")
        _safe_alter(cursor, "ALTER TABLE fraud_alerts ADD COLUMN customer_tier VARCHAR(4) DEFAULT NULL")
        _safe_alter(cursor, "ALTER TABLE fraud_alerts ADD COLUMN score_a DECIMAL(6,2) DEFAULT NULL")
        _safe_alter(cursor, "ALTER TABLE fraud_alerts ADD COLUMN score_b DECIMAL(6,2) DEFAULT NULL")
        _safe_alter(cursor, "ALTER TABLE fraud_alerts ADD COLUMN str_required TINYINT(1) DEFAULT 0")
        _safe_alter(cursor, "ALTER TABLE fraud_alerts ADD COLUMN ctr_flag TINYINT(1) DEFAULT 0")
        _safe_alter(cursor, "ALTER TABLE fraud_alerts ADD COLUMN investigation_note TEXT DEFAULT NULL")
        _safe_alter(cursor, "ALTER TABLE fraud_alerts ADD COLUMN raa_citations JSON DEFAULT NULL")
        _safe_alter(cursor, "ALTER TABLE fraud_alerts ADD COLUMN raa_stages JSON DEFAULT NULL")
        # Compound index for RAA poller (pra done + raa pending)
        try:
            cursor.execute(
                "ALTER TABLE fraud_alerts ADD INDEX idx_raa (pra_processed, raa_processed)"
            )
        except Exception:
            pass  # index already exists

        # Compound index for PRA poller — (pra_processed, verdict) used in every 500ms poll
        # Without this index the poller does a full table scan on fraud_alerts continuously
        try:
            cursor.execute(
                "ALTER TABLE fraud_alerts ADD INDEX idx_pra (pra_processed, verdict)"
            )
        except Exception:
            pass  # index already exists

        # Recovery: reset any rows stuck in pra_processed=2 (claimed but never completed)
        # This handles worker crashes mid-flight. Rows claimed >120s ago are safe to retry.
        try:
            cursor.execute("""
                UPDATE fraud_alerts
                SET pra_processed = 0
                WHERE pra_processed = 2
                  AND created_at < NOW() - INTERVAL 120 SECOND
            """)
            recovered = cursor.rowcount
            if recovered > 0:
                print(f"[OK] Recovered {recovered} stale PRA claims (pra_processed=2→0).")
        except Exception:
            pass

        # Recovery: reset any rows stuck in raa_processed=2 (claimed but never completed)
        try:
            cursor.execute("""
                UPDATE fraud_alerts
                SET raa_processed = 0
                WHERE raa_processed = 2
                  AND created_at < NOW() - INTERVAL 120 SECOND
            """)
            recovered = cursor.rowcount
            if recovered > 0:
                print(f"[OK] Recovered {recovered} stale RAA claims (raa_processed=2→0).")
        except Exception:
            pass

        # ── action_packages ───────────────────────────────────────────────────
        # Written by RAA, consumed by ABA.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS action_packages (
                package_id    VARCHAR(48) PRIMARY KEY,
                alert_id      INT         NOT NULL,
                payload       JSON        NOT NULL,
                dispatched_at DATETIME    DEFAULT NOW(),
                aba_consumed  TINYINT(1)  DEFAULT 0,
                INDEX idx_aba (aba_consumed, dispatched_at)
            )
        """)

        # ── payment_transactions ─────────────────────────────────────────────
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS payment_transactions (
                id                    INT AUTO_INCREMENT PRIMARY KEY,
                payment_id            VARCHAR(20)   NOT NULL UNIQUE,

                sender_customer_id    VARCHAR(6)    NOT NULL,
                sender_account        VARCHAR(12)   NOT NULL,
                recipient_account     VARCHAR(12)   NOT NULL,
                recipient_customer_id VARCHAR(6)    DEFAULT NULL,

                amount                DECIMAL(15,2) NOT NULL,
                description           VARCHAR(255),

                debit_transaction_id  VARCHAR(20)   DEFAULT NULL,
                credit_transaction_id VARCHAR(20)   DEFAULT NULL,

                status                ENUM(
                                          'INITIATED',
                                          'COMPLETED',
                                          'FAILED',
                                          'REVERSED',
                                          'PENDING_REVIEW'
                                      ) DEFAULT 'INITIATED',

                risk_score            INT           DEFAULT NULL,
                fraud_alert_id        INT           DEFAULT NULL,

                created_at            TIMESTAMP     DEFAULT CURRENT_TIMESTAMP,
                completed_at          TIMESTAMP     DEFAULT NULL,

                FOREIGN KEY (sender_customer_id) REFERENCES customers(customer_id),
                FOREIGN KEY (fraud_alert_id)     REFERENCES fraud_alerts(id)
            )
        """)

        # ── customer_pattern_profiles ─────────────────────────────────────────
        # Rolling pattern state per customer — cached and updated by PRA.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS customer_pattern_profiles (
                customer_id              VARCHAR(6)    PRIMARY KEY,
                rolling_avg_risk         DECIMAL(5,2)  DEFAULT 0.00,
                trend_direction          ENUM('STABLE','RISING','FALLING') DEFAULT 'STABLE',
                escalation_count         INT           DEFAULT 0,
                consecutive_blocks       INT           DEFAULT 0,
                last_pattern_alert_at    TIMESTAMP     DEFAULT NULL,
                last_updated             TIMESTAMP     DEFAULT CURRENT_TIMESTAMP
                                         ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
            )
        """)

        # ── pattern_alerts ────────────────────────────────────────────────────
        # One row per PRA evaluation — linked to payment_transactions.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pattern_alerts (
                id                  INT AUTO_INCREMENT PRIMARY KEY,
                payment_id          VARCHAR(20)   NOT NULL,
                customer_id         VARCHAR(6)    NOT NULL,

                pattern_score       INT           NOT NULL,
                temporal_score      INT           NOT NULL DEFAULT 0,
                network_score       INT           NOT NULL DEFAULT 0,
                rag_adjustment      INT           NOT NULL DEFAULT 0,

                decision            VARCHAR(20)   NOT NULL,

                pattern_types       JSON          DEFAULT NULL,
                network_flags       JSON          DEFAULT NULL,
                agent_reasoning     TEXT          DEFAULT NULL,
                typology_code       VARCHAR(50)   DEFAULT NULL,

                tma_risk_score      INT           DEFAULT NULL,
                tma_decision        VARCHAR(10)   DEFAULT NULL,

                created_at          TIMESTAMP     DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
            )
        """)

        # Add pattern_alert_id to payment_transactions
        _safe_alter(cursor,
            "ALTER TABLE payment_transactions ADD COLUMN pattern_alert_id INT DEFAULT NULL"
        )

        # Widen pattern_alerts.decision from ENUM to VARCHAR(20) for PRA verdicts
        # (DE-ESCALATE, MAINTAIN, ESCALATE, CRITICAL)
        try:
            cursor.execute(
                "ALTER TABLE pattern_alerts MODIFY COLUMN decision VARCHAR(20) NOT NULL"
            )
        except Exception:
            pass  # already VARCHAR or column doesn't exist yet

        # ── novel_pattern_candidates ─────────────────────────────────────────
        # Staging table for PRA feedback loop — high-scoring BiLSTM sequences
        # with no matching L3 typology are staged here for human review.
        # Confirmed patterns are later ingested into ChromaDB L3.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS novel_pattern_candidates (
                id                  INT AUTO_INCREMENT PRIMARY KEY,
                alert_id            INT           NOT NULL,
                customer_id         VARCHAR(6)    NOT NULL,
                bilstm_score        DECIMAL(6,2)  NOT NULL,
                flag_labels         JSON          DEFAULT NULL,
                hidden_state        JSON          DEFAULT NULL,
                review_status       ENUM('PENDING','CONFIRMED','REJECTED')
                                    NOT NULL DEFAULT 'PENDING',
                assigned_typology   VARCHAR(16)   DEFAULT NULL,
                urgency_multiplier  DECIMAL(4,2)  DEFAULT NULL,
                regulatory_action   VARCHAR(255)  DEFAULT NULL,
                created_at          TIMESTAMP     DEFAULT CURRENT_TIMESTAMP,
                reviewed_at         TIMESTAMP     DEFAULT NULL,
                reviewed_by         VARCHAR(100)  DEFAULT NULL,
                FOREIGN KEY (alert_id)    REFERENCES fraud_alerts(id),
                FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
            )
        """)

        # ── ABA columns on customers ────────────────────────────────────────────
        _safe_alter(cursor, "ALTER TABLE customers ADD COLUMN is_frozen TINYINT(1) DEFAULT 0")
        _safe_alter(cursor, "ALTER TABLE customers ADD COLUMN frozen_at DATETIME DEFAULT NULL")
        _safe_alter(cursor, "ALTER TABLE customers ADD COLUMN frozen_reason VARCHAR(255) DEFAULT NULL")
        _safe_alter(cursor, "ALTER TABLE customers ADD COLUMN frozen_by_alert_id INT DEFAULT NULL")
        _safe_alter(cursor, "ALTER TABLE customers ADD COLUMN credential_reset_required TINYINT(1) DEFAULT 0")
        _safe_alter(cursor, "ALTER TABLE customers ADD COLUMN credential_reset_alert_id INT DEFAULT NULL")
        # OTP attempt tracking fallback columns (used when Redis is unavailable)
        _safe_alter(cursor, "ALTER TABLE customers ADD COLUMN otp_attempt_count INT DEFAULT 0")
        _safe_alter(cursor, "ALTER TABLE customers ADD COLUMN soft_lock_until DATETIME DEFAULT NULL")

        # ── ABA columns on fraud_alerts ─────────────────────────────────────────
        _safe_alter(cursor, "ALTER TABLE fraud_alerts ADD COLUMN aba_processed TINYINT(1) DEFAULT 0")
        _safe_alter(cursor, "ALTER TABLE fraud_alerts ADD COLUMN aba_gateway_action VARCHAR(30) DEFAULT NULL")
        _safe_alter(cursor, "ALTER TABLE fraud_alerts ADD COLUMN aba_actions_executed JSON DEFAULT NULL")
        _safe_alter(cursor, "ALTER TABLE fraud_alerts ADD COLUMN aba_case_id VARCHAR(48) DEFAULT NULL")

        # Index for ABA poller (raa done, aba pending)
        try:
            cursor.execute(
                "ALTER TABLE fraud_alerts ADD INDEX idx_aba (raa_processed, aba_processed)"
            )
        except Exception:
            pass  # index already exists

        # ── regulatory_queue ────────────────────────────────────────────────────
        # CTR/STR filings for compliance
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS regulatory_queue (
                id                INT AUTO_INCREMENT PRIMARY KEY,
                filing_id         VARCHAR(48) NOT NULL UNIQUE,
                type              ENUM('CTR', 'STR') NOT NULL,
                alert_id          INT NOT NULL,
                customer_id       VARCHAR(6) NOT NULL,
                amount            DECIMAL(15,2) DEFAULT NULL,
                status            ENUM('AUTO_FILED', 'PENDING_APPROVAL', 'APPROVED', 'FILED', 'REJECTED')
                                  NOT NULL DEFAULT 'PENDING_APPROVAL',
                draft_content     JSON DEFAULT NULL,
                investigation_note TEXT DEFAULT NULL,
                approved_by       VARCHAR(100) DEFAULT NULL,
                approved_at       DATETIME DEFAULT NULL,
                filed_at          DATETIME DEFAULT NULL,
                created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_status (status, created_at)
            )
        """)

        # ── fraud_cases ─────────────────────────────────────────────────────────
        # Cases created by ABA for CLA consumption
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS fraud_cases (
                id                INT AUTO_INCREMENT PRIMARY KEY,
                case_id           VARCHAR(48) NOT NULL UNIQUE,
                alert_id          INT NOT NULL,
                package_id        VARCHAR(48) NOT NULL,
                customer_id       VARCHAR(6) NOT NULL,
                priority          ENUM('P1', 'P2', 'P3') NOT NULL DEFAULT 'P2',
                status            ENUM('OPEN', 'INVESTIGATING', 'ESCALATED', 'RESOLVED', 'CLOSED')
                                  NOT NULL DEFAULT 'OPEN',
                evidence_pack     JSON NOT NULL,
                cla_consumed      TINYINT(1) DEFAULT 0,
                assigned_to       VARCHAR(100) DEFAULT NULL,
                resolution_notes  TEXT DEFAULT NULL,
                created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                closed_at         DATETIME DEFAULT NULL,
                INDEX idx_cla (cla_consumed, created_at),
                INDEX idx_priority (priority, status)
            )
        """)

        # ── notification_queue ──────────────────────────────────────────────────
        # Async notification delivery
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notification_queue (
                id                INT AUTO_INCREMENT PRIMARY KEY,
                notification_id   VARCHAR(48) NOT NULL UNIQUE,
                customer_id       VARCHAR(6) NOT NULL,
                alert_id          INT NOT NULL,
                channel           ENUM('PUSH', 'EMAIL', 'SMS') NOT NULL,
                template_code     VARCHAR(50) NOT NULL,
                payload           JSON NOT NULL,
                status            ENUM('PENDING', 'SENT', 'FAILED', 'EXPIRED') NOT NULL DEFAULT 'PENDING',
                attempts          INT DEFAULT 0,
                last_attempt_at   DATETIME DEFAULT NULL,
                sent_at           DATETIME DEFAULT NULL,
                created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_status (status, created_at)
            )
        """)

        # ── aba_execution_log ───────────────────────────────────────────────────
        # Audit trail of all ABA actions
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS aba_execution_log (
                id                INT AUTO_INCREMENT PRIMARY KEY,
                package_id        VARCHAR(48) NOT NULL,
                alert_id          INT NOT NULL,
                customer_id       VARCHAR(6) NOT NULL,
                verdict           VARCHAR(20) NOT NULL,
                gateway_action    VARCHAR(30) NOT NULL,
                actions_executed  JSON NOT NULL,
                execution_time_ms INT NOT NULL,
                error_message     TEXT DEFAULT NULL,
                created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_package (package_id),
                INDEX idx_alert (alert_id)
            )
        """)

        # Recovery: reset any packages stuck in aba_consumed=2 (claimed but never completed)
        try:
            cursor.execute("""
                UPDATE action_packages
                SET aba_consumed = 0
                WHERE aba_consumed = 2
                  AND dispatched_at < NOW() - INTERVAL 120 SECOND
            """)
            recovered = cursor.rowcount
            if recovered > 0:
                print(f"[OK] Recovered {recovered} stale ABA claims (aba_consumed=2→0).")
        except Exception:
            pass

        # ── cla_citations ───────────────────────────────────────────────────────────
        # Citation library for CLA agent — regulatory rules, fraud patterns, precedents
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cla_citations (
                id                INT AUTO_INCREMENT PRIMARY KEY,
                citation_id       VARCHAR(48) NOT NULL UNIQUE,
                category          ENUM('REGULATORY', 'PRECEDENT', 'TYPOLOGY') NOT NULL,
                source_layer      VARCHAR(8) DEFAULT NULL,
                title             VARCHAR(255) NOT NULL,
                content           TEXT NOT NULL,
                tags              JSON DEFAULT NULL,
                severity          ENUM('LOW', 'MEDIUM', 'HIGH', 'CRITICAL') DEFAULT 'MEDIUM',
                created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_category (category, severity)
            )
        """)

        # ── cla_archive ─────────────────────────────────────────────────────────────
        # Archived STR filings with citation lineage
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cla_archive (
                id                INT AUTO_INCREMENT PRIMARY KEY,
                filing_id         VARCHAR(48) NOT NULL UNIQUE,
                case_id           VARCHAR(48) NOT NULL,
                alert_id          INT NOT NULL,
                customer_id       VARCHAR(6) NOT NULL,
                filing_type       ENUM('CTR', 'STR') NOT NULL,
                str_content       JSON NOT NULL,
                citations_used    JSON NOT NULL,
                pdf_path          VARCHAR(500) DEFAULT NULL,
                filed_at          DATETIME NOT NULL,
                filed_by          VARCHAR(100) DEFAULT 'CLA_AUTO',
                archived_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_case (case_id),
                INDEX idx_customer (customer_id, archived_at)
            )
        """)

        conn.commit()
        print("[OK] All tables verified/created.")
        print("[OK] All monitoring agent columns verified/added.")
        print("[OK] All pattern agent tables verified/added.")
        print("[OK] novel_pattern_candidates table verified/added.")
        print("[OK] All RAA columns and action_packages table verified/added.")
        print("[OK] All ABA columns and tables verified/added.")
        print("[OK] All CLA tables verified/added.")

    except Error as e:
        print(f"Error creating tables: {e}")
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


def _safe_alter(cursor, sql: str):
    """
    Executes an ALTER TABLE statement and silently ignores
    'Duplicate column name' errors (errno 1060) which means
    the column already exists. Any other error is re-raised.
    """
    try:
        cursor.execute(sql)
    except Error as e:
        if e.errno == 1060:
            pass  # Column already exists — idempotent, safe to ignore
        else:
            raise