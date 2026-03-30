"""
aba_dao.py
──────────
Data Access Objects for the Alert & Block Agent (ABA).

Provides:
  - Polling action_packages for ABA-eligible rows
  - Marking ABA completion (aba_consumed=1)
  - Account freeze/unfreeze operations
  - Regulatory queue writes (CTR/STR)
  - Fraud case creation
  - Notification queue writes
  - Execution logging
  - Health metrics
  - Redis-based OTP attempt tracking and soft-lock management
    (used by payment_routes.py verify-otp flow)
"""

import json
import uuid
from datetime import datetime, timedelta
from mysql.connector import Error
from db import get_db_connection


# ── Redis client (lazy singleton) ──────────────────────────────────────────────
# Using a lazy singleton avoids import-time failures if Redis is not running.
# All Redis functions handle ConnectionError gracefully and log a warning.

_redis_client = None
_redis_available = None  # None = untested, True = available, False = unavailable

def _get_redis():
    """Returns a Redis client, creating it on first call.
    Once Redis is detected as unavailable, returns None immediately to prevent repeated timeouts."""
    global _redis_client, _redis_available

    # If Redis is known to be unavailable, skip connection attempt
    if _redis_available is False:
        return None

    # If already initialized and available, return it
    if _redis_client is not None and _redis_available is True:
        return _redis_client

    if _redis_client is None:
        try:
            import redis
            _redis_client = redis.Redis(
                host='localhost',
                port=6379,
                db=0,
                decode_responses=True,   # return str not bytes
                socket_connect_timeout=0.3,  # 300ms timeout for fast fallback
                socket_timeout=0.3,
            )
            _redis_client.ping()         # verify connection on first use
            _redis_available = True
        except Exception as e:
            print(f"[ABA DAO] WARN: Redis not available — OTP/soft-lock features "
                  f"will use DB fallback: {e}")
            _redis_client = None
            _redis_available = False
    return _redis_client


# ── Redis OTP / soft-lock helpers ──────────────────────────────────────────────

def increment_otp_attempts(customer_id: str) -> int:
    """
    Increments the OTP failure counter for a customer.
    Counter expires after 15 minutes (900 seconds).
    Returns the updated attempt count.

    Used by payment_routes.verify_payment_otp() to track failures.
    """
    r = _get_redis()
    if r:
        try:
            key      = f"mfa_attempts:{customer_id}"
            attempts = r.incr(key)
            r.expire(key, 900)   # 15-minute rolling window
            return int(attempts)
        except Exception as e:
            print(f"[ABA DAO] Redis incr error: {e}")

    # DB fallback — store in customers table if Redis unavailable
    return _db_increment_otp_attempts(customer_id)


def get_otp_attempt_count(customer_id: str) -> int:
    """Returns the current OTP failure count for a customer."""
    r = _get_redis()
    if r:
        try:
            val = r.get(f"mfa_attempts:{customer_id}")
            return int(val) if val else 0
        except Exception as e:
            print(f"[ABA DAO] Redis get error: {e}")
    return 0


def reset_otp_attempts(customer_id: str):
    """
    Clears the OTP failure counter after a successful verification.
    Also clears the mfa_required and mfa_otp keys.
    """
    r = _get_redis()
    if r:
        try:
            r.delete(
                f"mfa_attempts:{customer_id}",
                f"mfa_required:{customer_id}",
                f"mfa_otp:{customer_id}",
            )
            return
        except Exception as e:
            print(f"[ABA DAO] Redis delete error: {e}")

    # DB fallback
    _db_reset_otp_attempts(customer_id)


def set_soft_lock(customer_id: str, duration_seconds: int = 1800):
    """
    Sets a soft-lock on the customer for the given duration.
    Default 1800 seconds = 30 minutes.

    Soft-locked customers cannot initiate payments until the lock expires.
    Applied after 3 consecutive OTP failures on an ALERT transaction.
    """
    r = _get_redis()
    if r:
        try:
            r.setex(f"soft_lock_until:{customer_id}", duration_seconds, 1)
            return
        except Exception as e:
            print(f"[ABA DAO] Redis setex error: {e}")

    # DB fallback — write soft_lock_until timestamp to customers table
    _db_set_soft_lock(customer_id, duration_seconds)


def is_soft_locked(customer_id: str) -> bool:
    """
    Returns True if the customer is currently soft-locked
    (cannot initiate payments).

    Checked at the top of verify_payment_otp() before processing any OTP.
    """
    r = _get_redis()
    if r:
        try:
            return bool(r.get(f"soft_lock_until:{customer_id}"))
        except Exception as e:
            print(f"[ABA DAO] Redis get soft_lock error: {e}")

    # DB fallback
    return _db_is_soft_locked(customer_id)


def clear_soft_lock(customer_id: str):
    """Manually clears a soft-lock (e.g. by compliance officer action)."""
    r = _get_redis()
    if r:
        try:
            r.delete(f"soft_lock_until:{customer_id}")
            return
        except Exception as e:
            print(f"[ABA DAO] Redis delete soft_lock error: {e}")

    _db_clear_soft_lock(customer_id)


# ── DB fallbacks for Redis operations ─────────────────────────────────────────
# Used when Redis is unavailable. Less precise than Redis (no atomic incr)
# but keeps the system functional.

def _db_increment_otp_attempts(customer_id: str) -> int:
    conn = get_db_connection()
    if not conn:
        return 1
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT otp_attempt_count FROM customers WHERE customer_id = %s",
            (customer_id,)
        )
        row = cursor.fetchone()
        count = (int(row['otp_attempt_count']) + 1) if row else 1
        cursor.execute(
            "UPDATE customers SET otp_attempt_count = %s WHERE customer_id = %s",
            (count, customer_id)
        )
        conn.commit()
        return count
    except Exception:
        return 1
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


def _db_reset_otp_attempts(customer_id: str):
    conn = get_db_connection()
    if not conn:
        return
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE customers SET otp_attempt_count = 0 WHERE customer_id = %s",
            (customer_id,)
        )
        conn.commit()
    except Exception:
        pass
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


def _db_set_soft_lock(customer_id: str, duration_seconds: int):
    conn = get_db_connection()
    if not conn:
        return
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE customers
            SET soft_lock_until = DATE_ADD(NOW(), INTERVAL %s SECOND)
            WHERE customer_id = %s
        """, (duration_seconds, customer_id))
        conn.commit()
    except Exception:
        pass
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


def _db_is_soft_locked(customer_id: str) -> bool:
    conn = get_db_connection()
    if not conn:
        return False
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT soft_lock_until FROM customers
            WHERE customer_id = %s AND soft_lock_until > NOW()
        """, (customer_id,))
        return cursor.fetchone() is not None
    except Exception:
        return False
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


def _db_clear_soft_lock(customer_id: str):
    conn = get_db_connection()
    if not conn:
        return
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE customers SET soft_lock_until = NULL WHERE customer_id = %s",
            (customer_id,)
        )
        conn.commit()
    except Exception:
        pass
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


# ── Polling ─────────────────────────────────────────────────────────────────────

def get_unconsumed_packages(limit: int = 10) -> list[dict]:
    """
    Returns action_packages rows where aba_consumed=0.
    Uses atomic claim pattern (aba_consumed=2) to prevent duplicate
    processing when multiple ABA workers poll concurrently.
    """
    conn = get_db_connection()
    if not conn:
        raise RuntimeError("Database connection error.")
    try:
        cursor = conn.cursor(dictionary=True)

        # Step 1: Atomically claim up to `limit` rows
        cursor.execute("""
            UPDATE action_packages
            SET aba_consumed = 2
            WHERE aba_consumed = 0
            ORDER BY dispatched_at ASC
            LIMIT %s
        """, (limit,))
        claimed = cursor.rowcount
        conn.commit()

        if claimed == 0:
            return []

        # Step 2: Fetch the rows we just claimed
        cursor.execute("""
            SELECT package_id, alert_id, payload, dispatched_at
            FROM action_packages
            WHERE aba_consumed = 2
            ORDER BY dispatched_at ASC
            LIMIT %s
        """, (claimed,))
        rows = cursor.fetchall()

        # Parse JSON payload
        for row in rows:
            if isinstance(row['payload'], str):
                try:
                    row['payload'] = json.loads(row['payload'])
                except (json.JSONDecodeError, TypeError):
                    row['payload'] = {}
            elif row['payload'] is None:
                row['payload'] = {}
        return rows
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


def mark_aba_consumed(package_id: str):
    """Marks aba_consumed=1 to indicate ABA has finished processing."""
    conn = get_db_connection()
    if not conn:
        raise RuntimeError("Database connection error.")
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE action_packages
            SET aba_consumed = 1
            WHERE package_id = %s
        """, (package_id,))
        conn.commit()
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


def update_fraud_alert_aba(alert_id: int, aba_result: dict):
    """Updates fraud_alerts with ABA processing results."""
    conn = get_db_connection()
    if not conn:
        raise RuntimeError("Database connection error.")
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE fraud_alerts
            SET aba_processed = 1,
                aba_gateway_action = %s,
                aba_actions_executed = %s,
                aba_case_id = %s
            WHERE id = %s
        """, (
            aba_result.get('aba_gateway_action'),
            json.dumps(aba_result.get('aba_actions_executed', [])),
            aba_result.get('aba_case_id'),
            alert_id,
        ))
        conn.commit()
    except Error as e:
        conn.rollback()
        raise RuntimeError(f"Database error updating fraud_alerts: {e}")
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


# ── Account Operations ──────────────────────────────────────────────────────────

def set_account_frozen(customer_id: str, is_frozen: bool,
                       frozen_by_alert_id: int = None, reason: str = None):
    """Freezes or unfreezes a customer account."""
    conn = get_db_connection()
    if not conn:
        raise RuntimeError("Database connection error.")
    try:
        cursor = conn.cursor()
        if is_frozen:
            cursor.execute("""
                UPDATE customers
                SET is_frozen = 1,
                    frozen_at = NOW(),
                    frozen_reason = %s,
                    frozen_by_alert_id = %s
                WHERE customer_id = %s
            """, (reason, frozen_by_alert_id, customer_id))
        else:
            cursor.execute("""
                UPDATE customers
                SET is_frozen = 0,
                    frozen_at = NULL,
                    frozen_reason = NULL,
                    frozen_by_alert_id = NULL
                WHERE customer_id = %s
            """, (customer_id,))
        conn.commit()
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


def set_credential_reset_required(customer_id: str, alert_id: int):
    """Marks account for mandatory credential reset on next login."""
    conn = get_db_connection()
    if not conn:
        raise RuntimeError("Database connection error.")
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE customers
            SET credential_reset_required = 1,
                credential_reset_alert_id = %s
            WHERE customer_id = %s
        """, (alert_id, customer_id))
        conn.commit()
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


def get_customer_contact(customer_id: str) -> dict | None:
    """Returns customer contact info (email, phone, name) for notifications."""
    conn = get_db_connection()
    if not conn:
        raise RuntimeError("Database connection error.")
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT email, full_name, phone_number
            FROM customers
            WHERE customer_id = %s
        """, (customer_id,))
        return cursor.fetchone()
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


def is_account_frozen(customer_id: str) -> bool:
    """Checks if a customer account is currently frozen."""
    conn = get_db_connection()
    if not conn:
        raise RuntimeError("Database connection error.")
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT is_frozen FROM customers WHERE customer_id = %s
        """, (customer_id,))
        row = cursor.fetchone()
        return bool(row['is_frozen']) if row else False
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


# ── Regulatory Queue ────────────────────────────────────────────────────────────

def save_regulatory_filing(filing: dict) -> str:
    """Inserts CTR/STR filing into regulatory_queue. Returns filing_id."""
    conn = get_db_connection()
    if not conn:
        raise RuntimeError("Database connection error.")
    try:
        cursor = conn.cursor()
        filing_id = (f"FIL-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                     f"-{uuid.uuid4().hex[:8].upper()}")

        cursor.execute("""
            INSERT INTO regulatory_queue (
                filing_id, type, alert_id, customer_id, amount,
                status, draft_content, investigation_note
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            filing_id,
            filing['type'],
            filing['alert_id'],
            filing['customer_id'],
            filing.get('amount'),
            filing['status'],
            json.dumps(filing.get('draft_content')) if filing.get('draft_content') else None,
            filing.get('investigation_note'),
        ))
        conn.commit()
        return filing_id
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


# ── Fraud Cases ─────────────────────────────────────────────────────────────────

def save_fraud_case(case: dict) -> str:
    """Creates a fraud case for CLA consumption. Returns case_id."""
    conn = get_db_connection()
    if not conn:
        raise RuntimeError("Database connection error.")
    try:
        cursor = conn.cursor()
        case_id = (f"CASE-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                   f"-{uuid.uuid4().hex[:8].upper()}")

        cursor.execute("""
            INSERT INTO fraud_cases (
                case_id, alert_id, package_id, customer_id,
                priority, status, evidence_pack, cla_consumed
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            case_id,
            case['alert_id'],
            case['package_id'],
            case['customer_id'],
            case['priority'],
            case.get('status', 'OPEN'),
            json.dumps(case['evidence_pack']),
            case.get('cla_consumed', 0),
        ))
        conn.commit()
        return case_id
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


def get_fraud_case(case_id: str) -> dict | None:
    """Retrieves a fraud case by case_id."""
    conn = get_db_connection()
    if not conn:
        raise RuntimeError("Database connection error.")
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT * FROM fraud_cases WHERE case_id = %s", (case_id,)
        )
        row = cursor.fetchone()
        if row and isinstance(row.get('evidence_pack'), str):
            try:
                row['evidence_pack'] = json.loads(row['evidence_pack'])
            except (json.JSONDecodeError, TypeError):
                row['evidence_pack'] = {}
        return row
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


# ── Notification Queue ──────────────────────────────────────────────────────────

def save_notification(notification: dict) -> str:
    """Queues notification for async delivery. Returns notification_id."""
    conn = get_db_connection()
    if not conn:
        raise RuntimeError("Database connection error.")
    try:
        cursor = conn.cursor()
        notification_id = (f"NOTIF-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                           f"-{uuid.uuid4().hex[:8].upper()}")

        cursor.execute("""
            INSERT INTO notification_queue (
                notification_id, customer_id, alert_id,
                channel, template_code, payload, status
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            notification_id,
            notification['customer_id'],
            notification['alert_id'],
            notification['channel'],
            notification['template'],
            json.dumps(notification['payload']),
            notification.get('status', 'PENDING'),
        ))
        conn.commit()
        return notification_id
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


# ── Execution Logging ───────────────────────────────────────────────────────────

def save_execution_log(log: dict):
    """Saves ABA execution log for audit trail."""
    conn = get_db_connection()
    if not conn:
        raise RuntimeError("Database connection error.")
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO aba_execution_log (
                package_id, alert_id, customer_id, verdict,
                gateway_action, actions_executed, execution_time_ms, error_message
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            log['package_id'],
            log['alert_id'],
            log['customer_id'],
            log['verdict'],
            log['gateway_action'],
            json.dumps(log['actions_executed']),
            log['execution_time_ms'],
            log.get('error_message'),
        ))
        conn.commit()
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


# ── Health Metrics ──────────────────────────────────────────────────────────────

def get_aba_health_stats() -> dict:
    """Returns health metrics for /api/aba/health endpoint."""
    conn = get_db_connection()
    if not conn:
        return {'queue_depth': -1, 'error': 'DB connection failed'}
    try:
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            "SELECT COUNT(*) AS cnt FROM action_packages WHERE aba_consumed = 0"
        )
        queue_depth = int(cursor.fetchone()['cnt'])

        since_1h = datetime.now() - timedelta(hours=1)

        cursor.execute(
            "SELECT COUNT(*) AS cnt FROM aba_execution_log WHERE created_at >= %s",
            (since_1h,)
        )
        processed_last_1h = int(cursor.fetchone()['cnt'])

        cursor.execute(
            "SELECT COUNT(*) AS cnt FROM fraud_cases WHERE DATE(created_at) = CURDATE()"
        )
        cases_today = int(cursor.fetchone()['cnt'])

        cursor.execute("""
            SELECT COUNT(*) AS cnt FROM regulatory_queue
            WHERE type = 'STR' AND DATE(created_at) = CURDATE()
        """)
        str_queued_today = int(cursor.fetchone()['cnt'])

        cursor.execute("""
            SELECT COUNT(*) AS cnt FROM customers
            WHERE is_frozen = 1 AND DATE(frozen_at) = CURDATE()
        """)
        accounts_frozen_today = int(cursor.fetchone()['cnt'])

        return {
            'queue_depth':          queue_depth,
            'processed_last_1h':    processed_last_1h,
            'cases_today':          cases_today,
            'str_queued_today':     str_queued_today,
            'accounts_frozen_today': accounts_frozen_today,
        }
    except Exception as e:
        return {'queue_depth': -1, 'error': str(e)}
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


# ── Stale Claim Recovery ────────────────────────────────────────────────────────

def recover_stale_aba_claims(threshold_seconds: int = 120) -> int:
    """
    Resets packages stuck in aba_consumed=2 (claimed but never completed).
    Returns the count of recovered rows.
    """
    conn = get_db_connection()
    if not conn:
        raise RuntimeError("Database connection error.")
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE action_packages
            SET aba_consumed = 0
            WHERE aba_consumed = 2
              AND dispatched_at < NOW() - INTERVAL %s SECOND
        """, (threshold_seconds,))
        recovered = cursor.rowcount
        conn.commit()
        return recovered
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()