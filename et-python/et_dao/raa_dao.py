"""
raa_dao.py
──────────
Data Access Objects for the Risk Assessment Agent (RAA).

Provides:
  - Polling fraud_alerts for RAA-eligible rows
  - Fetching the full alert row for processing
  - Marking RAA completion (raa_processed=1)
  - Saving action_packages consumed by ABA
  - 24h customer aggregate total (for CTR check)
  - Customer account stats (for tier classification)
  - Health metrics (queue depth, processed counts)
"""

import json
from datetime import datetime, timedelta
from mysql.connector import Error
from db import get_db_connection


# ── Polling ────────────────────────────────────────────────────────────────────

def get_unprocessed_alerts(limit: int = 10) -> list[dict]:
    """
    Returns fraud_alerts rows where pra_processed=1 AND raa_processed=0.
    These are ready for RAA evaluation.

    Uses atomic claim pattern (raa_processed=2) to prevent duplicate
    processing when multiple RAA workers poll concurrently.
    """
    conn = get_db_connection()
    if not conn:
        raise RuntimeError("Database connection error.")
    try:
        cursor = conn.cursor(dictionary=True)

        # Step 1: Atomically claim up to `limit` rows
        cursor.execute("""
            UPDATE fraud_alerts
            SET raa_processed = 2
            WHERE pra_processed = 1
              AND raa_processed = 0
            ORDER BY created_at ASC
            LIMIT %s
        """, (limit,))
        claimed = cursor.rowcount
        conn.commit()

        if claimed == 0:
            return []

        # Step 2: Fetch the rows we just claimed
        cursor.execute("""
            SELECT id AS alert_id, id
            FROM fraud_alerts
            WHERE raa_processed = 2
            ORDER BY created_at ASC
            LIMIT %s
        """, (claimed,))
        return cursor.fetchall()
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


def get_full_alert_row(alert_id: int) -> dict | None:
    """
    Fetches the complete fraud_alerts row for a given alert_id.
    Returns None if not found.
    """
    conn = get_db_connection()
    if not conn:
        raise RuntimeError("Database connection error.")
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT *
            FROM fraud_alerts
            WHERE id = %s
            LIMIT 1
        """, (alert_id,))
        row = cursor.fetchone()
        if not row:
            return None

        # Parse JSON fields
        for json_field in ('anomaly_flags', 'rag_citations', 'feature_snapshot',
                           'pra_reg_citations', 'raa_citations'):
            val = row.get(json_field)
            if isinstance(val, str):
                try:
                    row[json_field] = json.loads(val)
                except (json.JSONDecodeError, TypeError):
                    row[json_field] = []
            elif val is None:
                row[json_field] = []

        # Cast numeric fields
        for f in ('risk_score', 'ml_score', 'rag_score', 'pattern_score',
                  'bilstm_score', 'sequence_length'):
            if row.get(f) is not None:
                row[f] = int(row[f])
        for f in ('urgency_multiplier',):
            if row.get(f) is not None:
                row[f] = float(row[f])

        return row
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


# ── Write-back ──────────────────────────────────────────────────────────────────

def mark_raa_processed(alert_id: int, scores: dict):
    """
    Marks raa_processed=1 and writes all RAA scoring results back to fraud_alerts.

    scores keys expected:
      final_raa_score, raa_verdict, customer_tier,
      score_a, score_b, str_required, ctr_flag,
      investigation_note, raa_citations  (JSON-serialisable list)
    """
    conn = get_db_connection()
    if not conn:
        raise RuntimeError("Database connection error.")
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE fraud_alerts
            SET raa_processed     = 1,
                final_raa_score   = %s,
                raa_verdict       = %s,
                customer_tier     = %s,
                score_a           = %s,
                score_b           = %s,
                str_required      = %s,
                ctr_flag          = %s,
                investigation_note= %s,
                raa_citations     = %s
            WHERE id = %s
        """, (
            scores.get('final_raa_score'),
            scores.get('raa_verdict'),
            scores.get('customer_tier'),
            scores.get('score_a'),
            scores.get('score_b'),
            int(bool(scores.get('str_required', False))),
            int(bool(scores.get('ctr_flag', False))),
            scores.get('investigation_note'),
            json.dumps(scores.get('raa_citations', [])),
            alert_id,
        ))
        conn.commit()
    except Error as e:
        conn.rollback()
        raise RuntimeError(f"Database error marking RAA processed: {e}")
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


def mark_raa_processed_flag(alert_id: int):
    """
    Minimal safety function: sets raa_processed=1 without writing scores.
    Used by the orchestrator's finally block to prevent infinite retry loops
    when downstream stages (action_package_builder) fail.

    If mark_raa_processed() already set it, this is a harmless no-op
    (sets 1 to 1).
    """
    conn = get_db_connection()
    if not conn:
        raise RuntimeError("Database connection error.")
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE fraud_alerts SET raa_processed = 1 WHERE id = %s",
            (alert_id,)
        )
        conn.commit()
    except Error as e:
        conn.rollback()
        raise RuntimeError(f"Database error in mark_raa_processed_flag: {e}")
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


def save_action_package(package_id: str, alert_id: int, payload: dict):
    """
    Inserts an action_package row for ABA to consume.
    payload is serialised to JSON.
    """
    conn = get_db_connection()
    if not conn:
        raise RuntimeError("Database connection error.")
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO action_packages (package_id, alert_id, payload)
            VALUES (%s, %s, %s)
        """, (package_id, alert_id, json.dumps(payload)))
        conn.commit()
    except Error as e:
        conn.rollback()
        raise RuntimeError(f"Database error saving action package: {e}")
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


# ── Customer data for tier + regulatory engines ────────────────────────────────

def get_customer_account_stats(customer_id: str) -> dict:
    """
    Returns stats needed by the tier engine:
      tx_count, account_age_days, fraud_flag_count_total,
      fraud_flag_count_30d, fraud_flag_count_90d, is_minor
    """
    conn = get_db_connection()
    if not conn:
        raise RuntimeError("Database connection error.")
    try:
        cursor = conn.cursor(dictionary=True)

        # Transaction count (DEBIT only — matches TMA profile builder)
        cursor.execute("""
            SELECT COUNT(*) AS tx_count
            FROM transactions
            WHERE customer_id = %s AND type = 'DEBIT'
        """, (customer_id,))
        row = cursor.fetchone()
        tx_count = int(row['tx_count']) if row else 0

        # Account age and minor flag from customers table
        cursor.execute("""
            SELECT DATEDIFF(NOW(), created_at) AS age_days, is_minor
            FROM customers
            WHERE customer_id = %s
        """, (customer_id,))
        row = cursor.fetchone()
        account_age_days = int(row['age_days']) if row and row['age_days'] is not None else 0
        is_minor = bool(row['is_minor']) if row else False

        # Total historical fraud flags
        cursor.execute("""
            SELECT COUNT(*) AS cnt
            FROM fraud_alerts
            WHERE customer_id = %s AND decision IN ('FLAG','ALERT','BLOCK')
        """, (customer_id,))
        row = cursor.fetchone()
        fraud_flag_count_total = int(row['cnt']) if row else 0

        # Fraud flags in last 30 days
        since_30d = datetime.now() - timedelta(days=30)
        cursor.execute("""
            SELECT COUNT(*) AS cnt
            FROM fraud_alerts
            WHERE customer_id = %s
              AND decision IN ('FLAG','ALERT','BLOCK')
              AND created_at >= %s
        """, (customer_id, since_30d))
        row = cursor.fetchone()
        fraud_flag_count_30d = int(row['cnt']) if row else 0

        # Fraud flags in last 90 days
        since_90d = datetime.now() - timedelta(days=90)
        cursor.execute("""
            SELECT COUNT(*) AS cnt
            FROM fraud_alerts
            WHERE customer_id = %s
              AND decision IN ('FLAG','ALERT','BLOCK')
              AND created_at >= %s
        """, (customer_id, since_90d))
        row = cursor.fetchone()
        fraud_flag_count_90d = int(row['cnt']) if row else 0

        return {
            'tx_count':              tx_count,
            'account_age_days':      account_age_days,
            'fraud_flag_count_total': fraud_flag_count_total,
            'fraud_flag_count_30d':  fraud_flag_count_30d,
            'fraud_flag_count_90d':  fraud_flag_count_90d,
            'is_minor':              is_minor,
        }
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


def get_24h_customer_total(customer_id: str) -> float:
    """
    Returns the total DEBIT amount sent by this customer in the last 24 hours.
    Used by the regulatory engine for CTR aggregate threshold check.
    """
    conn = get_db_connection()
    if not conn:
        raise RuntimeError("Database connection error.")
    try:
        cursor = conn.cursor()
        since = datetime.now() - timedelta(hours=24)
        cursor.execute("""
            SELECT COALESCE(SUM(amount), 0)
            FROM transactions
            WHERE customer_id = %s
              AND type = 'DEBIT'
              AND created_at >= %s
        """, (customer_id, since))
        row = cursor.fetchone()
        return float(row[0]) if row else 0.0
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


# ── Health metrics ─────────────────────────────────────────────────────────────

def get_raa_health_stats() -> dict:
    """
    Returns health metrics for the /api/raa/health endpoint.
    """
    conn = get_db_connection()
    if not conn:
        return {'queue_depth': -1, 'error': 'DB connection failed'}
    try:
        cursor = conn.cursor(dictionary=True)

        # Queue depth: pra done, raa pending
        cursor.execute("""
            SELECT COUNT(*) AS cnt
            FROM fraud_alerts
            WHERE pra_processed = 1 AND raa_processed = 0
        """)
        queue_depth = int(cursor.fetchone()['cnt'])

        since_1h = datetime.now() - timedelta(hours=1)

        # Processed in last hour
        cursor.execute("""
            SELECT COUNT(*) AS cnt
            FROM fraud_alerts
            WHERE raa_processed = 1 AND created_at >= %s
        """, (since_1h,))
        processed_last_1h = int(cursor.fetchone()['cnt'])

        # Avg score last hour
        cursor.execute("""
            SELECT COALESCE(AVG(final_raa_score), 0) AS avg_score
            FROM fraud_alerts
            WHERE raa_processed = 1 AND created_at >= %s
        """, (since_1h,))
        avg_score = round(float(cursor.fetchone()['avg_score']), 2)

        # STR drafted last hour
        cursor.execute("""
            SELECT COUNT(*) AS cnt
            FROM fraud_alerts
            WHERE raa_processed = 1 AND str_required = 1 AND created_at >= %s
        """, (since_1h,))
        str_drafted_last_1h = int(cursor.fetchone()['cnt'])

        # CTR flagged last hour
        cursor.execute("""
            SELECT COUNT(*) AS cnt
            FROM fraud_alerts
            WHERE raa_processed = 1 AND ctr_flag = 1 AND created_at >= %s
        """, (since_1h,))
        ctr_flagged_last_1h = int(cursor.fetchone()['cnt'])

        return {
            'queue_depth':        queue_depth,
            'processed_last_1h':  processed_last_1h,
            'avg_score_last_1h':  avg_score,
            'str_drafted_last_1h': str_drafted_last_1h,
            'ctr_flagged_last_1h': ctr_flagged_last_1h,
        }
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


def get_raa_alert_by_payment(payment_id: str, customer_id: str) -> dict | None:
    """
    Retrieves the RAA verdict and scores for a specific payment.
    Links fraud_alerts to payment via transaction_id.
    """
    conn = get_db_connection()
    if not conn:
        raise RuntimeError("Database connection error.")
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT fa.*
            FROM fraud_alerts fa
            JOIN payment_transactions pt ON fa.transaction_id = pt.debit_transaction_id
            WHERE pt.payment_id = %s AND pt.sender_customer_id = %s
            LIMIT 1
        """, (payment_id, customer_id))
        row = cursor.fetchone()
        if not row:
            return None
        
        # Parse JSON fields
        for json_field in ('raa_citations',):
            val = row.get(json_field)
            if isinstance(val, str):
                try:
                    row[json_field] = json.loads(val)
                except (json.JSONDecodeError, TypeError):
                    row[json_field] = []
            elif val is None:
                row[json_field] = []
        
        # Convert timestamps to strings for JSON serialization
        if row.get('created_at'):
            row['created_at'] = str(row['created_at'])
        
        return row
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


def get_customer_raa_alerts(customer_id: str, limit: int = 10) -> list:
    """
    Retrieves the last N RAA alerts for a customer.
    Returns alerts that have been processed by RAA (raa_processed=1).
    """
    conn = get_db_connection()
    if not conn:
        raise RuntimeError("Database connection error.")
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT id, transaction_id, raa_verdict, final_raa_score,
                   customer_tier, str_required, ctr_flag,
                   investigation_note, created_at
            FROM fraud_alerts
            WHERE customer_id = %s AND raa_processed = 1
            ORDER BY created_at DESC
            LIMIT %s
        """, (customer_id, limit))
        
        rows = cursor.fetchall()
        for row in rows:
            if row.get('created_at'):
                row['created_at'] = str(row['created_at'])
        
        return rows
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


def get_customer_raa_stats(customer_id: str) -> dict:
    """
    Returns aggregated RAA stats for a customer over all time.
    Includes: total alerts, average score, verdict breakdown, flags.
    """
    conn = get_db_connection()
    if not conn:
        raise RuntimeError("Database connection error.")
    try:
        cursor = conn.cursor(dictionary=True)
        
        # Total RAA processed
        cursor.execute("""
            SELECT COUNT(*) AS total_count
            FROM fraud_alerts
            WHERE customer_id = %s AND raa_processed = 1
        """, (customer_id,))
        total = int(cursor.fetchone()['total_count'])
        
        # Average score
        cursor.execute("""
            SELECT COALESCE(AVG(final_raa_score), 0) AS avg_score
            FROM fraud_alerts
            WHERE customer_id = %s AND raa_processed = 1
        """, (customer_id,))
        avg_score = round(float(cursor.fetchone()['avg_score']), 2)
        
        # Verdict breakdown
        cursor.execute("""
            SELECT raa_verdict, COUNT(*) AS count
            FROM fraud_alerts
            WHERE customer_id = %s AND raa_processed = 1
            GROUP BY raa_verdict
        """, (customer_id,))
        verdict_breakdown = {row['raa_verdict']: int(row['count']) for row in cursor.fetchall() if row['raa_verdict'] is not None}
        
        # Flag counts
        cursor.execute("""
            SELECT 
                SUM(CASE WHEN str_required = 1 THEN 1 ELSE 0 END) AS str_count,
                SUM(CASE WHEN ctr_flag = 1 THEN 1 ELSE 0 END) AS ctr_count
            FROM fraud_alerts
            WHERE customer_id = %s AND raa_processed = 1
        """, (customer_id,))
        flags = cursor.fetchone()
        
        return {
            'total_raa_alerts': total,
            'average_risk_score': avg_score,
            'verdict_breakdown': verdict_breakdown,
            'str_flags_raised': int(flags['str_count'] or 0),
            'ctr_flags_raised': int(flags['ctr_count'] or 0),
        }
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


# ── Regulatory Filing (for CLA) ────────────────────────────────────────────────

def insert_regulatory_filing(
    filing_id: str,
    filing_type: str,
    alert_id: int,
    customer_id: str,
    amount: float,
    status: str,
    draft_content: dict,
    investigation_note: str
) -> bool:
    """
    Inserts a regulatory filing (STR/CTR) into the regulatory_queue table.
    Used by CLA agent to create filings.
    
    Args:
        filing_id: Unique filing identifier (e.g., STR-xxx or CTR-xxx)
        filing_type: 'STR' or 'CTR'
        alert_id: Associated fraud_alerts.id
        customer_id: Customer identifier
        amount: Transaction amount
        status: Filing status ('AUTO_FILED', 'PENDING_APPROVAL', 'REJECTED')
        draft_content: JSON content of the filing
        investigation_note: Human-readable investigation note
    
    Returns:
        True on success, False on failure
    """
    conn = get_db_connection()
    if not conn:
        return False
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO regulatory_queue
                (filing_id, type, alert_id, customer_id, amount, status,
                 draft_content, investigation_note, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
        """, (
            filing_id, filing_type, alert_id, customer_id, amount, status,
            json.dumps(draft_content), investigation_note
        ))
        conn.commit()
        return True
    except Exception as e:
        print(f"[raa_dao] insert_regulatory_filing error: {e}")
        conn.rollback()
        return False
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()
