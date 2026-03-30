from mysql.connector import Error
from db import get_db_connection
from datetime import datetime, timedelta


# ── Profile reads/writes ───────────────────────────────────────────────────────

def get_behaviour_profile(customer_id: str) -> dict | None:
    """
    Returns the customer's stored behavioural baseline profile.
    Returns None if no profile exists yet (brand new customer).
    """
    conn = get_db_connection()
    if not conn:
        raise RuntimeError("Database connection error.")
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT
                customer_id, avg_amount, std_amount, max_single_amount,
                avg_daily_volume, transaction_frequency,
                usual_hour_start, usual_hour_end,
                known_recipients_count, total_data_points,
                cold_start, profile_strength, last_updated
            FROM customer_behaviour_profiles
            WHERE customer_id = %s
        """, (customer_id,))
        row = cursor.fetchone()
        if not row:
            return None
        for field in ('avg_amount', 'std_amount', 'max_single_amount',
                      'avg_daily_volume', 'transaction_frequency', 'profile_strength'):
            if row[field] is not None:
                row[field] = float(row[field])
        return row
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


def upsert_behaviour_profile(customer_id: str, profile: dict):
    """
    Inserts or updates the behavioural profile for a customer.
    last_updated is managed automatically by MySQL ON UPDATE CURRENT_TIMESTAMP.
    """
    conn = get_db_connection()
    if not conn:
        raise RuntimeError("Database connection error.")
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO customer_behaviour_profiles (
                customer_id, avg_amount, std_amount, max_single_amount,
                avg_daily_volume, transaction_frequency,
                usual_hour_start, usual_hour_end,
                known_recipients_count, total_data_points,
                cold_start, profile_strength
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                avg_amount             = VALUES(avg_amount),
                std_amount             = VALUES(std_amount),
                max_single_amount      = VALUES(max_single_amount),
                avg_daily_volume       = VALUES(avg_daily_volume),
                transaction_frequency  = VALUES(transaction_frequency),
                usual_hour_start       = VALUES(usual_hour_start),
                usual_hour_end         = VALUES(usual_hour_end),
                known_recipients_count = VALUES(known_recipients_count),
                total_data_points      = VALUES(total_data_points),
                cold_start             = VALUES(cold_start),
                profile_strength       = VALUES(profile_strength)
        """, (
            customer_id,
            profile['avg_amount'],
            profile['std_amount'],
            profile['max_single_amount'],
            profile['avg_daily_volume'],
            profile['transaction_frequency'],
            profile['usual_hour_start'],
            profile['usual_hour_end'],
            profile['known_recipients_count'],
            profile['total_data_points'],
            profile['cold_start'],
            profile['profile_strength'],
        ))
        conn.commit()
    except Error as e:
        conn.rollback()
        raise RuntimeError(f"Database error upserting behaviour profile: {e}")
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


# ── Transaction history reads ──────────────────────────────────────────────────

def get_recent_transactions(customer_id: str, days: int = 90) -> list[dict]:
    """
    Returns all DEBIT transactions for a customer within the last N days.
    Used by the Profile Builder to compute the behavioural baseline.
    """
    conn = get_db_connection()
    if not conn:
        raise RuntimeError("Database connection error.")
    try:
        cursor = conn.cursor(dictionary=True)
        since = datetime.now() - timedelta(days=days)
        cursor.execute("""
            SELECT
                transaction_id, customer_id, type, amount,
                description, balance_after, recipient_account, created_at
            FROM transactions
            WHERE customer_id = %s
              AND type = 'DEBIT'
              AND created_at >= %s
            ORDER BY created_at DESC
        """, (customer_id, since))
        rows = cursor.fetchall()
        for row in rows:
            row['amount']        = float(row['amount'])
            row['balance_after'] = float(row['balance_after'])
        return rows
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


def get_transactions_last_n_hours(customer_id: str, hours: int) -> list[dict]:
    """
    Returns DEBIT transactions in the last N hours.
    Used by the Anomaly Extractor for velocity signals.
    """
    conn = get_db_connection()
    if not conn:
        raise RuntimeError("Database connection error.")
    try:
        cursor = conn.cursor(dictionary=True)
        since = datetime.now() - timedelta(hours=hours)
        cursor.execute("""
            SELECT transaction_id, amount, recipient_account, created_at
            FROM transactions
            WHERE customer_id = %s
              AND type = 'DEBIT'
              AND created_at >= %s
            ORDER BY created_at DESC
        """, (customer_id, since))
        rows = cursor.fetchall()
        for row in rows:
            row['amount'] = float(row['amount'])
        return rows
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


def get_known_recipients(customer_id: str) -> set[str]:
    """
    Returns all unique recipient accounts this customer has ever
    transacted with. Used to detect new/unknown recipients.
    """
    conn = get_db_connection()
    if not conn:
        raise RuntimeError("Database connection error.")
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT recipient_account
            FROM transactions
            WHERE customer_id = %s
              AND type = 'DEBIT'
              AND recipient_account IS NOT NULL
        """, (customer_id,))
        rows = cursor.fetchall()
        return {row[0] for row in rows}
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


def get_daily_volume(customer_id: str) -> float:
    """
    Returns the total amount sent by this customer today (midnight to now).
    Used by the Anomaly Extractor for daily volume threshold checks.
    """
    conn = get_db_connection()
    if not conn:
        raise RuntimeError("Database connection error.")
    try:
        cursor = conn.cursor()
        today_midnight = datetime.now().replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        cursor.execute("""
            SELECT COALESCE(SUM(amount), 0)
            FROM transactions
            WHERE customer_id = %s
              AND type = 'DEBIT'
              AND created_at >= %s
        """, (customer_id, today_midnight))
        row = cursor.fetchone()
        return float(row[0]) if row else 0.0
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


# ── Fraud alert writes ─────────────────────────────────────────────────────────

def save_fraud_alert(alert: dict) -> int:
    """
    Inserts a fraud alert record into the fraud_alerts table.
    Returns the inserted row ID.

    Changes vs original:
      [ADD] typology_code          — best-matching FIU-IND typology from L3
      [ADD] low_confidence_fallback — True when RAG confidence < 0.65

    Requires the following ALTER TABLE to be run once (or added to db.py):
      ALTER TABLE fraud_alerts
        ADD COLUMN typology_code VARCHAR(50) DEFAULT NULL,
        ADD COLUMN low_confidence_fallback TINYINT(1) DEFAULT 0;
    """
    conn = get_db_connection()
    if not conn:
        raise RuntimeError("Database connection error.")
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO fraud_alerts (
                transaction_id, customer_id,
                risk_score, ml_score, rag_score,
                decision, anomaly_flags, feature_snapshot, rag_citations,
                agent_reasoning,
                disagreement, rag_available,
                cold_start_profile, fallback_mode,
                typology_code, low_confidence_fallback
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
        """, (
            alert['transaction_id'],
            alert['customer_id'],
            alert['risk_score'],
            alert['ml_score'],
            alert.get('rag_score'),
            alert['decision'],
            alert.get('anomaly_flags'),
            alert.get('feature_snapshot'),
            alert.get('rag_citations'),
            alert.get('agent_reasoning'),
            alert.get('disagreement', 0),
            alert.get('rag_available', 1),
            alert.get('cold_start_profile', 0),
            alert.get('fallback_mode', 0),
            alert.get('typology_code'),
            alert.get('low_confidence_fallback', 0),
        ))
        conn.commit()
        return cursor.lastrowid
    except Error as e:
        conn.rollback()
        raise RuntimeError(f"Database error saving fraud alert: {e}")
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


def update_transaction_after_evaluation(transaction_id: str,
                                         risk_score: int,
                                         fraud_flag: int,
                                         agent_status: str):
    """
    Writes risk_score, fraud_flag, and agent_status back to the
    transactions row after evaluation.
    """
    conn = get_db_connection()
    if not conn:
        raise RuntimeError("Database connection error.")
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE transactions
            SET risk_score   = %s,
                fraud_flag   = %s,
                agent_status = %s
            WHERE transaction_id = %s
        """, (risk_score, fraud_flag, agent_status, transaction_id))
        conn.commit()
    except Error as e:
        conn.rollback()
        raise RuntimeError(f"Database error updating transaction after evaluation: {e}")
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


def update_payment_fraud_result(payment_id: str,
                                 fraud_alert_id: int,
                                 risk_score: int,
                                 decision: str):
    """
    Links the fraud alert back to the payment_transactions record.
    Sets status to PENDING_REVIEW if decision is FLAG or above.
    """
    conn = get_db_connection()
    if not conn:
        raise RuntimeError("Database connection error.")
    try:
        cursor = conn.cursor()
        new_status = (
            'PENDING_REVIEW' if decision in ('FLAG', 'ALERT', 'BLOCK')
            else 'COMPLETED'
        )
        cursor.execute("""
            UPDATE payment_transactions
            SET fraud_alert_id = %s,
                risk_score     = %s,
                status         = %s
            WHERE payment_id = %s
        """, (fraud_alert_id, risk_score, new_status, payment_id))
        conn.commit()
    except Error as e:
        conn.rollback()
        raise RuntimeError(f"Database error updating payment fraud result: {e}")
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


# ── Customer info reads ────────────────────────────────────────────────────────

def get_customer_info(customer_id: str) -> dict | None:
    """
    Returns lightweight customer metadata for the monitoring agent.
    Does NOT return sensitive fields like password_hash or Aadhaar.
    """
    conn = get_db_connection()
    if not conn:
        raise RuntimeError("Database connection error.")
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT customer_id, account_type, city, state,
                   is_minor, created_at
            FROM customers
            WHERE customer_id = %s
        """, (customer_id,))
        return cursor.fetchone()
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


def get_fraud_alert_by_payment(payment_id: str, customer_id: str) -> dict | None:
    """
    Retrieves the fraud alert associated with a specific payment.
    Verifies customer ownership (security check).
    Returns None if not found or still processing.
    """
    conn = get_db_connection()
    if not conn:
        raise RuntimeError("Database connection error.")
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT
                fa.id as alert_id,
                fa.risk_score,
                fa.ml_score,
                fa.rag_score,
                fa.decision,
                fa.anomaly_flags,
                fa.rag_citations,
                fa.agent_reasoning,
                fa.disagreement,
                fa.rag_available,
                fa.cold_start_profile,
                fa.fallback_mode,
                fa.typology_code,
                fa.low_confidence_fallback,
                fa.created_at,
                fa.pra_processed,
                fa.pra_verdict,
                fa.pattern_score,
                fa.bilstm_score,
                fa.precedent_adj,
                fa.reg_adj,
                fa.urgency_multiplier,
                fa.sequence_length,
                fa.pra_reg_citations,
                fa.raa_processed,
                fa.raa_verdict,
                fa.final_raa_score,
                fa.customer_tier,
                fa.score_a,
                fa.score_b,
                fa.str_required,
                fa.ctr_flag,
                fa.investigation_note,
                fa.raa_citations,
                fa.raa_stages
            FROM fraud_alerts fa
            JOIN payment_transactions pt
              ON fa.transaction_id = pt.debit_transaction_id
            WHERE pt.payment_id = %s
              AND pt.sender_customer_id = %s
        """, (payment_id, customer_id))
        row = cursor.fetchone()
        if row:
            for int_field in ('risk_score', 'ml_score', 'rag_score', 'pattern_score', 'tma_risk_score'):
                if row.get(int_field) is not None:
                    row[int_field] = int(row[int_field])
            for float_field in ('bilstm_score', 'precedent_adj', 'reg_adj', 'urgency_multiplier', 'final_raa_score', 'score_a', 'score_b'):
                if row.get(float_field) is not None:
                    row[float_field] = float(row[float_field])
            for bool_field in ('disagreement', 'rag_available',
                               'cold_start_profile', 'fallback_mode',
                               'low_confidence_fallback'):
                if row.get(bool_field) is not None:
                    row[bool_field] = bool(row[bool_field])
        return row
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


def get_fraud_alert_by_transaction(transaction_id: str) -> dict | None:
    """
    Retrieves the fraud alert for a specific debit transaction_id.
    Used by the PRA to poll for the TMA result.
    Returns None if TMA hasn't written the result yet.
    """
    conn = get_db_connection()
    if not conn:
        raise RuntimeError("Database connection error.")
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT
                id as alert_id,
                risk_score, ml_score, rag_score,
                decision, typology_code,
                disagreement, rag_available,
                cold_start_profile, fallback_mode,
                low_confidence_fallback, created_at
            FROM fraud_alerts
            WHERE transaction_id = %s
            LIMIT 1
        """, (transaction_id,))
        row = cursor.fetchone()
        if row:
            for int_field in ('risk_score', 'ml_score', 'rag_score'):
                if row.get(int_field) is not None:
                    row[int_field] = int(row[int_field])
        return row
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


def flag_agent_disagreement(payment_id: str, pattern_decision: str, pattern_score: int):
    """
    [FIX-4] Detects and flags when MonitoringAgent and PatternAgent disagree.
    
    Called from pattern_agent.response_executor after PRA completes.
    Checks if the pattern_decision differs from the monitoring_decision already
    saved in fraud_alerts. If disagreement exists, marks disagreement=True.
    
    Args:
        payment_id: The payment identifier
        pattern_decision: The PRA's decision (ALLOW, FLAG, ALERT, BLOCK)
        pattern_score: The PRA's risk score
    
    Returns:
        A dict with 'disagreement', 'monitoring_decision', 'pattern_decision' fields
    """
    conn = get_db_connection()
    if not conn:
        raise RuntimeError("Database connection error.")
    try:
        cursor = conn.cursor(dictionary=True)
        
        # Get the monitoring alert for this payment
        cursor.execute("""
            SELECT fa.id, fa.decision as monitoring_decision, fa.risk_score as monitoring_score
            FROM fraud_alerts fa
            JOIN payment_transactions pt
              ON fa.transaction_id = pt.debit_transaction_id
            WHERE pt.payment_id = %s
            LIMIT 1
        """, (payment_id,))
        
        row = cursor.fetchone()
        if not row:
            return {'disagreement': False, 'reason': 'No fraud alert found'}
        
        monitoring_decision = row.get('monitoring_decision')
        alert_id = row.get('id')
        
        # Check for disagreement: any decision mismatch beyond ALLOW vs FLAG/ALERT/BLOCK
        # More granular: ALLOW vs anything, or different levels of restriction
        has_disagreement = monitoring_decision != pattern_decision
        
        if has_disagreement:
            # Update fraud_alerts to mark disagreement
            cursor.execute("""
                UPDATE fraud_alerts
                SET disagreement = 1
                WHERE id = %s
            """, (alert_id,))
            conn.commit()
            
            return {
                'disagreement': True,
                'monitoring_decision': monitoring_decision,
                'pattern_decision': pattern_decision,
                'message': (
                    f"Disagreement flagged: TMA={monitoring_decision}({row.get('monitoring_score')}) "
                    f"vs PRA={pattern_decision}({pattern_score})"
                )
            }
        else:
            return {
                'disagreement': False,
                'monitoring_decision': monitoring_decision,
                'pattern_decision': pattern_decision,
                'message': f"Decisions aligned: both {monitoring_decision}"
            }
            
    except Error as e:
        raise RuntimeError(f"Database error flagging disagreement: {e}")
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


# ── CLA Helper Functions ───────────────────────────────────────────────────────

def get_alert_by_id(alert_id: int) -> dict | None:
    """
    Retrieves a fraud alert by its primary key ID.
    Used by CLA agent to fetch complete alert data.
    """
    conn = get_db_connection()
    if not conn:
        return None
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT * FROM fraud_alerts WHERE id = %s
        """, (alert_id,))
        row = cursor.fetchone()
        if row:
            # Convert numeric fields
            for int_field in ('risk_score', 'ml_score', 'rag_score'):
                if row.get(int_field) is not None:
                    row[int_field] = int(row[int_field])
            for float_field in ('bilstm_score', 'precedent_adj', 'reg_adj',
                               'urgency_multiplier', 'final_raa_score', 'score_a', 'score_b'):
                if row.get(float_field) is not None:
                    row[float_field] = float(row[float_field])
            for bool_field in ('disagreement', 'rag_available', 'cold_start_profile',
                              'fallback_mode', 'low_confidence_fallback', 'str_required',
                              'ctr_flag', 'pra_processed', 'raa_processed', 'aba_processed'):
                if row.get(bool_field) is not None:
                    row[bool_field] = bool(row[bool_field])
        return row
    except Exception as e:
        print(f"[monitoring_dao] get_alert_by_id error: {e}")
        return None
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


def get_transaction_by_id(transaction_id: str) -> dict | None:
    """
    Retrieves a transaction by its transaction_id.
    Used by CLA agent to fetch transaction details.
    """
    conn = get_db_connection()
    if not conn:
        return None
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT * FROM transactions WHERE transaction_id = %s
        """, (transaction_id,))
        row = cursor.fetchone()
        if row:
            # Convert numeric fields
            if row.get('amount') is not None:
                row['amount'] = float(row['amount'])
            if row.get('balance_after') is not None:
                row['balance_after'] = float(row['balance_after'])
            if row.get('risk_score') is not None:
                row['risk_score'] = int(row['risk_score'])
            if row.get('fraud_flag') is not None:
                row['fraud_flag'] = bool(row['fraud_flag'])
        return row
    except Exception as e:
        print(f"[monitoring_dao] get_transaction_by_id error: {e}")
        return None
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()
