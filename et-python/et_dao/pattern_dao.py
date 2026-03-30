"""
pattern_dao.py
──────────────
Data Access Objects for the Pattern Recognition Agent (PRA).

Provides:
  - Reading recent TMA alert history for temporal analysis
  - Cross-customer recipient network queries
  - Saving pattern_alerts rows
  - Getting/upserting customer_pattern_profiles
"""

from mysql.connector import Error
from db import get_db_connection
from datetime import datetime, timedelta


# ── TMA alert history reads ────────────────────────────────────────────────────

def get_recent_tma_alerts(customer_id: str, limit: int = 10) -> list[dict]:
    """
    Returns the last N fraud_alerts for this customer (most recent first).
    Used by TemporalAnalyser to detect escalation trends and typology persistence.
    """
    conn = get_db_connection()
    if not conn:
        raise RuntimeError("Database connection error.")
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT
                id, risk_score, ml_score, rag_score,
                decision, typology_code, anomaly_flags,
                disagreement, cold_start_profile,
                fallback_mode, low_confidence_fallback,
                created_at
            FROM fraud_alerts
            WHERE customer_id = %s
            ORDER BY created_at DESC
            LIMIT %s
        """, (customer_id, limit))
        rows = cursor.fetchall()
        for row in rows:
            for f in ('risk_score', 'ml_score'):
                if row[f] is not None:
                    row[f] = int(row[f])
            if row.get('rag_score') is not None:
                row['rag_score'] = int(row['rag_score'])
        return rows
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


def get_network_alerts(recipient_account: str, hours: int = 24) -> list[dict]:
    """
    Returns fraud_alerts for OTHER customers who sent to the same
    recipient_account in the last N hours.
    Used by NetworkAnalyser to detect fan-out fraud patterns.
    """
    conn = get_db_connection()
    if not conn:
        raise RuntimeError("Database connection error.")
    try:
        cursor = conn.cursor(dictionary=True)
        since = datetime.now() - timedelta(hours=hours)
        cursor.execute("""
            SELECT
                fa.customer_id,
                fa.risk_score,
                fa.decision,
                fa.typology_code,
                fa.created_at
            FROM fraud_alerts fa
            JOIN transactions t
              ON fa.transaction_id = t.transaction_id
            WHERE t.recipient_account = %s
              AND fa.created_at >= %s
            ORDER BY fa.created_at DESC
            LIMIT 50
        """, (recipient_account, since))
        rows = cursor.fetchall()
        for row in rows:
            if row.get('risk_score') is not None:
                row['risk_score'] = int(row['risk_score'])
        return rows
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


# ── Pattern alert writes ───────────────────────────────────────────────────────

def save_pattern_alert(alert: dict) -> int:
    """
    Inserts a pattern alert record into the pattern_alerts table.
    Returns the inserted row ID.
    """
    conn = get_db_connection()
    if not conn:
        raise RuntimeError("Database connection error.")
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO pattern_alerts (
                payment_id, customer_id,
                pattern_score, temporal_score, network_score, rag_adjustment,
                decision, pattern_types, network_flags,
                agent_reasoning, typology_code,
                tma_risk_score, tma_decision
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
        """, (
            alert['payment_id'],
            alert['customer_id'],
            alert['pattern_score'],
            alert.get('temporal_score', 0),
            alert.get('network_score', 0),
            alert.get('rag_adjustment', 0),
            alert['decision'],
            alert.get('pattern_types'),
            alert.get('network_flags'),
            alert.get('agent_reasoning'),
            alert.get('typology_code'),
            alert.get('tma_risk_score'),
            alert.get('tma_decision'),
        ))
        conn.commit()
        return cursor.lastrowid
    except Error as e:
        conn.rollback()
        raise RuntimeError(f"Database error saving pattern alert: {e}")
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


def link_pattern_alert_to_payment(payment_id: str, pattern_alert_id: int):
    """Links the pattern alert back to the payment_transactions record."""
    conn = get_db_connection()
    if not conn:
        raise RuntimeError("Database connection error.")
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE payment_transactions
            SET pattern_alert_id = %s
            WHERE payment_id = %s
        """, (pattern_alert_id, payment_id))
        conn.commit()
    except Error as e:
        conn.rollback()
        raise RuntimeError(f"Database error linking pattern alert: {e}")
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


def backfill_tma_result(payment_id: str, tma_risk_score: int, tma_decision: str):
    """
    [FIX-3] Backfill the TMA results into the pattern_alerts row after MonitoringAgent completes.
    
    Called from monitoring_agent.response_executor after fraud_alert is saved.
    If pattern_alerts exists for this payment_id but has tma_risk_score=0 or tma_decision=NULL,
    update it with the actual TMA results.
    
    Returns True if backfill was performed, False otherwise.
    """
    conn = get_db_connection()
    if not conn:
        raise RuntimeError("Database connection error.")
    try:
        cursor = conn.cursor(dictionary=True)
        
        # Check if pattern_alerts exists for this payment and has NULL/0 TMA results
        cursor.execute("""
            SELECT id, tma_risk_score, tma_decision
            FROM pattern_alerts
            WHERE payment_id = %s
            LIMIT 1
        """, (payment_id,))
        row = cursor.fetchone()
        
        if not row:
            # No pattern alert yet (PRA may not have started)
            return False
        
        # Check if TMA results are already populated
        if row.get('tma_risk_score') and row.get('tma_decision') and row['tma_decision'] != 'N/A':
            # Already backfilled or populated during PRA execution
            return False
        
        # Backfill the TMA results
        cursor.execute("""
            UPDATE pattern_alerts
            SET tma_risk_score = %s, tma_decision = %s
            WHERE payment_id = %s
        """, (tma_risk_score, tma_decision, payment_id))
        conn.commit()
        
        return True
        
    except Error as e:
        conn.rollback()
        raise RuntimeError(f"Database error backfilling TMA result: {e}")
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


def get_pattern_alert_by_payment(payment_id: str,
                                  customer_id: str) -> dict | None:
    """
    Retrieves the pattern alert associated with a specific payment.
    Verifies customer ownership.
    """
    conn = get_db_connection()
    if not conn:
        raise RuntimeError("Database connection error.")
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT
                pa.id as alert_id,
                pa.pattern_score,
                pa.temporal_score,
                pa.network_score,
                pa.rag_adjustment,
                pa.decision,
                pa.pattern_types,
                pa.network_flags,
                pa.agent_reasoning,
                pa.typology_code,
                pa.tma_risk_score,
                pa.tma_decision,
                pa.created_at
            FROM pattern_alerts pa
            WHERE pa.payment_id = %s
              AND pa.customer_id = %s
            ORDER BY pa.created_at DESC
            LIMIT 1
        """, (payment_id, customer_id))
        row = cursor.fetchone()
        if row:
            for f in ('pattern_score', 'temporal_score', 'network_score',
                      'rag_adjustment', 'tma_risk_score'):
                if row.get(f) is not None:
                    row[f] = int(row[f])
        return row
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


# ── Customer pattern profile ───────────────────────────────────────────────────

def get_pattern_profile(customer_id: str) -> dict | None:
    """Returns the customer's cached pattern profile, or None if not found."""
    conn = get_db_connection()
    if not conn:
        raise RuntimeError("Database connection error.")
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT
                customer_id, rolling_avg_risk, trend_direction,
                escalation_count, consecutive_blocks,
                last_pattern_alert_at, last_updated
            FROM customer_pattern_profiles
            WHERE customer_id = %s
        """, (customer_id,))
        row = cursor.fetchone()
        if row and row.get('rolling_avg_risk') is not None:
            row['rolling_avg_risk'] = float(row['rolling_avg_risk'])
        return row
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


def upsert_pattern_profile(customer_id: str, profile: dict):
    """Inserts or updates the rolling pattern profile for a customer."""
    conn = get_db_connection()
    if not conn:
        raise RuntimeError("Database connection error.")
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO customer_pattern_profiles (
                customer_id, rolling_avg_risk, trend_direction,
                escalation_count, consecutive_blocks,
                last_pattern_alert_at
            ) VALUES (%s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                rolling_avg_risk       = VALUES(rolling_avg_risk),
                trend_direction        = VALUES(trend_direction),
                escalation_count       = VALUES(escalation_count),
                consecutive_blocks     = VALUES(consecutive_blocks),
                last_pattern_alert_at  = VALUES(last_pattern_alert_at)
        """, (
            customer_id,
            profile['rolling_avg_risk'],
            profile['trend_direction'],
            profile['escalation_count'],
            profile['consecutive_blocks'],
            profile.get('last_pattern_alert_at') or datetime.now(),
        ))
        conn.commit()
    except Error as e:
        conn.rollback()
        raise RuntimeError(f"Database error upserting pattern profile: {e}")
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


# ══════════════════════════════════════════════════════════════════════════════
# NEW PRA PIPELINE FUNCTIONS (required by pra_agent.py, sequence_builder.py,
# pra_feedback_writer.py) — added for Phase 2 BiLSTM implementation.
# All existing functions above are unchanged.
# ══════════════════════════════════════════════════════════════════════════════

def get_unprocessed_alerts(batch_size: int = 20) -> list[dict]:
    """
    Atomically claims a batch of unprocessed FLAG/ALERT/BLOCK fraud_alert
    rows for the PRA poller, preventing concurrent workers from picking up
    the same alert.

    Uses a two-step pattern:
      1. UPDATE fraud_alerts SET pra_processed = 2 WHERE pra_processed = 0
         AND decision IN (...) LIMIT N   -- pra_processed=2 = "claimed"
      2. SELECT the rows we just claimed (pra_processed = 2 AND just updated)

    pra_processed states:
      0 = unprocessed (poller picks this up)
      2 = claimed     (being processed by a worker — transient state)
      1 = done        (write_pra_result sets this when complete)

    If a worker crashes mid-flight, rows stay at 2 permanently.
    A recovery sweep (not shown here) can reset stale 2→0 rows after
    a configurable timeout (e.g. 60 seconds).
    """
    conn = get_db_connection()
    if not conn:
        raise RuntimeError("Database connection error.")
    try:
        cursor = conn.cursor(dictionary=True)

        # Step 1: Atomically claim up to batch_size rows.
        # The UPDATE is atomic — only one worker can claim any given row.
        #
        # [FIX-5] TMA completion guard:
        #   risk_score IS NOT NULL       -- TMA Stage 3 (ML) written
        #   ml_score IS NOT NULL         -- TMA Stage 3 confirmed
        #   feature_snapshot IS NOT NULL -- TMA Stage 2 (extractor) written
        #
        # Without this guard the poller claimed rows the instant TMA created
        # them. PRA ran on an incomplete row, pra_processed went 0->2->1, and
        # every subsequent PRA call got "already claimed — skipping". RAA never
        # fired. Frontend polled /api/raa/alerts/ returning 202 indefinitely.
        cursor.execute("""
            UPDATE fraud_alerts
            SET pra_processed = 2
            WHERE pra_processed = 0
              AND decision IN ('FLAG', 'ALERT', 'BLOCK')
              AND risk_score       IS NOT NULL
              AND ml_score         IS NOT NULL
              AND feature_snapshot IS NOT NULL
            ORDER BY created_at ASC
            LIMIT %s
        """, (batch_size,))
        claimed = cursor.rowcount
        conn.commit()

        if claimed == 0:
            return []

        # Step 2: Fetch the rows we just claimed
        # Use ROW_NUMBER workaround — we need the IDs of what we just updated.
        # The safest cross-version approach: fetch by pra_processed=2 with
        # the same ordering, limited to what we claimed.
        cursor.execute("""
            SELECT
                id,
                transaction_id,
                customer_id,
                decision,
                risk_score,
                ml_score,
                typology_code,
                anomaly_flags,
                feature_snapshot,
                created_at
            FROM fraud_alerts
            WHERE pra_processed = 2
            ORDER BY created_at ASC
            LIMIT %s
        """, (claimed,))
        rows = cursor.fetchall()

        import json
        for row in rows:
            for col in ('risk_score', 'ml_score'):
                if row.get(col) is not None:
                    row[col] = int(row[col])
            for json_col in ('anomaly_flags', 'feature_snapshot'):
                val = row.get(json_col)
                if isinstance(val, str):
                    try:
                        row[json_col] = json.loads(val)
                    except (ValueError, TypeError):
                        row[json_col] = {}
        return rows
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


def get_alert_by_id(alert_id: int) -> dict | None:
    """
    Fetches a single fraud_alert row by primary key.
    Returns None if not found.
    Used by pra_agent.process_alert() as Stage 1.
    """
    conn = get_db_connection()
    if not conn:
        raise RuntimeError("Database connection error.")
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT
                id,
                transaction_id,
                customer_id,
                decision,
                risk_score,
                ml_score,
                typology_code,
                anomaly_flags,
                feature_snapshot,
                created_at
            FROM fraud_alerts
            WHERE id = %s
            LIMIT 1
        """, (alert_id,))
        row = cursor.fetchone()
        if row is None:
            return None
        import json
        for json_col in ('anomaly_flags', 'feature_snapshot'):
            val = row.get(json_col)
            if isinstance(val, str):
                try:
                    row[json_col] = json.loads(val)
                except (ValueError, TypeError):
                    row[json_col] = {}
        # Expose anomaly_features and anomaly_flag_labels as top-level keys
        # so pra_agent.py can access them with .get('anomaly_features')
        # [FIX] Handle both formats:
        #   - New format (TMA writes): ["flag1", "flag2"] (list)
        #   - Old format (legacy):      {'features': {...}, 'active_flags': [...]} (dict)
        flags = row.get('anomaly_flags')
        if isinstance(flags, list):
            # New format — anomaly_flags is a list of flag labels
            row['anomaly_features'] = {}
            row['anomaly_flag_labels'] = flags
        elif isinstance(flags, dict):
            # Old format — anomaly_flags is a dict with features and active_flags
            row['anomaly_features'] = flags.get('features', {})
            row['anomaly_flag_labels'] = flags.get('active_flags', [])
        else:
            # None or invalid format — use empty defaults
            row['anomaly_features'] = {}
            row['anomaly_flag_labels'] = []
        return row
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


def get_last_n_debits(customer_id: str, limit: int = 30) -> list[dict]:
    """
    Returns the last N DEBIT transactions for a customer, oldest first.
    For each transaction also fetches the feature_snapshot from fraud_alerts
    if TMA processed it, so sequence_builder doesn't need a second query.

    Used by sequence_builder.build_sequence() to construct the (30×15) matrix.
    """
    conn = get_db_connection()
    if not conn:
        raise RuntimeError("Database connection error.")
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT
                t.id,
                t.transaction_id,
                t.customer_id,
                t.amount,
                t.recipient_account,
                t.balance_after,
                t.created_at,
                fa.feature_snapshot,
                fa.risk_score  AS tma_risk_score,
                fa.decision    AS tma_decision
            FROM transactions t
            LEFT JOIN fraud_alerts fa
              ON fa.transaction_id = t.transaction_id
            WHERE t.customer_id = %s
              AND t.type = 'DEBIT'
            ORDER BY t.created_at ASC
            LIMIT %s
        """, (customer_id, limit))
        rows = cursor.fetchall()
        import json
        for row in rows:
            val = row.get('feature_snapshot')
            if isinstance(val, str):
                try:
                    row['feature_snapshot'] = json.loads(val)
                except (ValueError, TypeError):
                    row['feature_snapshot'] = None
            if row.get('tma_risk_score') is not None:
                row['tma_risk_score'] = int(row['tma_risk_score'])
        return rows
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


def get_alert_row_by_transaction(transaction_id: str) -> dict | None:
    """
    Fetches the fraud_alert row for a specific transaction_id.
    Returns the feature_snapshot and key TMA outputs.
    Used by sequence_builder for rows that TMA already processed.
    Returns None if TMA did not process this transaction (ALLOW / not yet run).
    """
    conn = get_db_connection()
    if not conn:
        raise RuntimeError("Database connection error.")
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT
                feature_snapshot,
                risk_score,
                decision,
                typology_code
            FROM fraud_alerts
            WHERE transaction_id = %s
            LIMIT 1
        """, (transaction_id,))
        row = cursor.fetchone()
        if row is None:
            return None
        import json
        val = row.get('feature_snapshot')
        if isinstance(val, str):
            try:
                row['feature_snapshot'] = json.loads(val)
            except (ValueError, TypeError):
                row['feature_snapshot'] = None
        return row
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


def write_pra_result(alert_id: int, pra_result: dict) -> None:
    """
    Writes PRA output back to the fraud_alerts row (pra_* columns).
    Called by pra_agent.py at Stage 5 after scoring is complete.

    pra_result keys (all optional except pra_processed):
      pra_processed, pra_verdict, pattern_score, bilstm_score,
      precedent_adj, reg_adj, urgency_multiplier, typology_code,
      sequence_length, pra_reg_citations, agent_reasoning
    """
    import json as _json
    conn = get_db_connection()
    if not conn:
        raise RuntimeError("Database connection error.")
    try:
        cursor = conn.cursor()

        # Serialise JSON fields
        reg_citations = pra_result.get('pra_reg_citations')
        if reg_citations is not None and not isinstance(reg_citations, str):
            reg_citations = _json.dumps(reg_citations)

        cursor.execute("""
            UPDATE fraud_alerts
            SET
                pra_processed      = %s,
                pra_verdict        = %s,
                pattern_score      = %s,
                bilstm_score       = %s,
                precedent_adj      = %s,
                reg_adj            = %s,
                urgency_multiplier = %s,
                typology_code      = COALESCE(%s, typology_code),
                sequence_length    = %s,
                pra_reg_citations  = %s,
                agent_reasoning    = CONCAT(
                    COALESCE(agent_reasoning, ''),
                    CASE WHEN agent_reasoning IS NOT NULL AND agent_reasoning != ''
                         THEN ' | PRA: ' ELSE 'PRA: ' END,
                    COALESCE(%s, '')
                )
            WHERE id = %s
        """, (
            pra_result.get('pra_processed', 1),
            pra_result.get('pra_verdict'),
            pra_result.get('pattern_score'),
            pra_result.get('bilstm_score'),
            pra_result.get('precedent_adj'),
            pra_result.get('reg_adj'),
            pra_result.get('urgency_multiplier'),
            pra_result.get('typology_code'),    # COALESCE keeps TMA's if PRA has None
            pra_result.get('sequence_length'),
            reg_citations,
            pra_result.get('agent_reasoning'),
            alert_id,
        ))
        conn.commit()
    except Error as e:
        conn.rollback()
        raise RuntimeError(f"Database error writing PRA result for alert_id={alert_id}: {e}")
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


def claim_single_alert(alert_id: int) -> bool:
    """
    [FIX-4] Atomically claims a single alert for PRA processing.

    Sets pra_processed = 2 (claimed) WHERE id = alert_id AND pra_processed = 0.
    The WHERE pra_processed = 0 clause is the lock — MySQL guarantees only one
    UPDATE can transition 0→2 for a given row. All subsequent callers see
    pra_processed != 0 and their UPDATE affects 0 rows → returns False.

    Used by process_alert() to prevent triple-processing:
      - Background poller submits _safe_process → calls process_alert
      - payment_routes._fire_pattern_agent() calls process_alert directly
      - OTP verify fires _fire_pattern_agent() again after payment commit
    Whichever thread arrives first at process_alert wins the claim.
    All others see False and skip immediately.

    Returns:
      True  — this thread claimed the alert, proceed with processing
      False — already claimed or processed by another thread, skip
    """
    conn = get_db_connection()
    if not conn:
        raise RuntimeError("Database connection error.")
    try:
        cursor = conn.cursor()
        # [FIX-5] TMA completion guard — same condition as batch claim.
        # Prevents claiming a row before TMA has finished writing its columns.
        # The poller will keep seeing pra_processed=0 until all three columns
        # are populated, then claim on the next 500ms tick.
        cursor.execute(
            "UPDATE fraud_alerts SET pra_processed = 2 "
            "WHERE id = %s "
            "  AND pra_processed = 0 "
            "  AND risk_score       IS NOT NULL "
            "  AND ml_score         IS NOT NULL "
            "  AND feature_snapshot IS NOT NULL",
            (alert_id,)
        )
        claimed = cursor.rowcount == 1
        conn.commit()
        return claimed
    except Error as e:
        conn.rollback()
        raise RuntimeError(f"Database error claiming alert {alert_id}: {e}")
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


def mark_alert_pra_complete(alert_id: int, success: bool = True) -> None:
    """
    Sets pra_processed = 1 (done) or resets to 0 (allow retry) for an alert.

    pra_processed state machine:
      0 → unclaimed  (poller picks up)
      2 → claimed    (worker is processing — transient)
      1 → complete   (done, poller skips permanently)

    Called by pra_agent._safe_process() in both success and failure paths.
    Never leaves a row stuck at pra_processed=2 after a worker exits.
      success=True  → 1  (mark done)
      success=False → 0  (reset so the row can be retried on next poll cycle)
    """
    final_state = 1 if success else 0
    conn = get_db_connection()
    if not conn:
        raise RuntimeError("Database connection error.")
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE fraud_alerts SET pra_processed = %s WHERE id = %s",
            (final_state, alert_id)
        )
        conn.commit()
    except Error as e:
        conn.rollback()
        raise RuntimeError(f"Database error marking alert {alert_id} complete: {e}")
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


def save_novel_pattern_candidate(candidate: dict) -> int:
    """
    Inserts a novel pattern candidate into the staging table.
    Called by pra_feedback_writer.py when BiLSTM score >= 70
    but no matching L3 typology was found (l3_similarity < 0.40).

    Returns the inserted row ID.
    """
    import json as _json
    conn = get_db_connection()
    if not conn:
        raise RuntimeError("Database connection error.")
    try:
        cursor = conn.cursor()

        # Serialise list/dict fields
        flag_labels  = candidate.get('flag_labels')
        hidden_state = candidate.get('hidden_state')
        if flag_labels is not None and not isinstance(flag_labels, str):
            flag_labels = _json.dumps(flag_labels)
        if hidden_state is not None and not isinstance(hidden_state, str):
            hidden_state = _json.dumps(hidden_state)

        cursor.execute("""
            INSERT INTO novel_pattern_candidates (
                alert_id, customer_id, bilstm_score,
                flag_labels, hidden_state, review_status
            ) VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            candidate['alert_id'],
            candidate['customer_id'],
            candidate['bilstm_score'],
            flag_labels,
            hidden_state,
            candidate.get('review_status', 'PENDING'),
        ))
        conn.commit()
        return cursor.lastrowid
    except Error as e:
        conn.rollback()
        raise RuntimeError(f"Database error saving novel pattern candidate: {e}")
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()