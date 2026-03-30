"""
response_executor.py
────────────────────
Layer 6 (final) of the Monitoring Agent pipeline.

Receives the populated FraudAlert from the Decision Engine and:
  1. Saves the fraud alert to the fraud_alerts table
  2. Updates the transaction row (risk_score, fraud_flag, agent_status)
  3. Links the fraud alert back to payment_transactions
  4. Backfills TMA results to pattern_alerts if PRA already created it [FIX-3]
  5. Executes the appropriate action based on decision tier

Decision tier actions:
  ALLOW : Silent log only — no customer-facing action
  FLAG  : Log + mark for human review queue
  ALERT : Log + console alert (customer notification placeholder)
  BLOCK : Log + console alert + mark for reversal (reversal engine placeholder)
"""

import json
from et_model.fraud_alert import FraudAlert
from et_dao.monitoring_dao import (
    save_fraud_alert,
    update_transaction_after_evaluation,
    update_payment_fraud_result,
)
from et_dao.pattern_dao import backfill_tma_result


def execute_response(alert: FraudAlert, payment_id: str) -> dict:
    """
    Main entry point for the Response Executor.

    Persists the FraudAlert and executes the appropriate action
    based on the decision tier.

    Returns a summary dict for logging in agent.py.
    """

    # ── Step 1: Save fraud alert to DB ────────────────────────────────
    alert_id = _save_alert(alert)
    alert.alert_id = alert_id

    # ── Step 2: Update transaction row ────────────────────────────────
    _update_transaction(alert)

    # ── Step 3: Link fraud alert back to payment record ───────────────
    _update_payment(payment_id, alert)

    # ── Step 4: Backfill TMA results to pattern_alerts if PRA started [FIX-3] ──
    try:
        backfilled = backfill_tma_result(payment_id, alert.risk_score, alert.decision)
        if backfilled:
            _log(alert, f"[MonitoringAgent] TMA backfill complete — pattern_alert updated for payment={payment_id}")
    except Exception as e:
        _log(alert, f"[MonitoringAgent] TMA backfill warning (non-fatal): {e}")

    # ── Step 5: Execute action based on decision tier ─────────────────
    action_result = _execute_action(alert)

    # ── Step 6 [FIX-1]: Fire Pattern Recognition Agent after TMA completes ────
    # This ensures PRA runs AFTER TMA has written fraud_alerts row
    # (fixes the 12-second race condition where PRA would timeout and run anyway)
    try:
        _fire_pattern_agent_for_alert(
            alert_id=alert_id,
            payment_id=payment_id,
        )
    except Exception as e:
        _log(alert, f"[MonitoringAgent] Warning: Could not fire PRA: {e}")

    return {
        'alert_id':     alert_id,
        'transaction_id': alert.transaction_id,
        'decision':     alert.decision,
        'risk_score':   alert.risk_score,
        'action_taken': action_result,
    }


# ── Internal helpers ───────────────────────────────────────────────────────────

def _save_alert(alert: FraudAlert) -> int:
    """Persists the FraudAlert to fraud_alerts table, returns the row ID."""
    return save_fraud_alert(alert.to_db_dict())


def _update_transaction(alert: FraudAlert):
    """
    Writes risk_score, fraud_flag, and agent_status=EVALUATED
    back to the transactions row.
    """
    update_transaction_after_evaluation(
        transaction_id=alert.transaction_id,
        risk_score=alert.risk_score,
        fraud_flag=alert.fraud_flag,
        agent_status=alert.agent_status,
    )


def _update_payment(payment_id: str, alert: FraudAlert):
    """
    Links the fraud_alert_id back to payment_transactions.
    Also flips payment status to PENDING_REVIEW for FLAG/ALERT/BLOCK.
    """
    update_payment_fraud_result(
        payment_id=payment_id,
        fraud_alert_id=alert.alert_id,
        risk_score=alert.risk_score,
        decision=alert.decision,
    )


def _execute_action(alert: FraudAlert) -> str:
    """
    Executes the appropriate action based on decision tier.
    Returns a short string describing what was done.
    """

    decision = alert.decision

    if decision == 'ALLOW':
        return _action_allow(alert)

    elif decision == 'FLAG':
        return _action_flag(alert)

    elif decision == 'ALERT':
        return _action_alert(alert)

    elif decision == 'BLOCK':
        return _action_block(alert)

    return 'UNKNOWN_DECISION'


def _action_allow(alert: FraudAlert) -> str:
    """
    ALLOW (score 0-30): Low risk.
    Silent log only — no customer-facing action needed.
    """
    _log(alert, "ALLOW — transaction cleared.")
    return 'SILENT_LOG'


def _action_flag(alert: FraudAlert) -> str:
    """
    FLAG (score 31-55): Medium risk.
    Transaction processed. Added to human review queue.
    Customer not notified — no reason to alarm them for medium risk.
    """
    _log(alert, "FLAG — added to human review queue.")

    # TODO Phase 4: insert into human_review_queue table
    # For now, the PENDING_REVIEW status on payment_transactions
    # serves as the review queue — admin dashboard will query it.

    return 'ADDED_TO_REVIEW_QUEUE'


def _action_alert(alert: FraudAlert) -> str:
    """
    ALERT (score 56-80): High risk.
    Transaction processed. Customer should be notified.
    Account not frozen — transaction was legitimate enough to allow through.
    """
    _log(alert, "ALERT — high risk detected. Customer notification triggered.")
    _log_flags(alert)

    # TODO Phase 4 (Alert/Block Agent): send push notification + email
    # For now, log to console so the team can see it during development.
    print(
        f"\n{'='*60}\n"
        f"  ⚠️  FRAUD ALERT — HIGH RISK\n"
        f"  Transaction : {alert.transaction_id}\n"
        f"  Risk Score  : {alert.risk_score}/100\n"
        f"  Decision    : {alert.decision}\n"
        f"  Reasoning   : {alert.agent_reasoning[:120] if alert.agent_reasoning else 'N/A'}...\n"
        f"{'='*60}\n"
    )

    return 'CUSTOMER_ALERT_TRIGGERED'


def _action_block(alert: FraudAlert) -> str:
    """
    BLOCK (score 81-100): Critical risk.
    Transaction already processed (async agent — cannot prevent it).
    Initiate reversal + notify customer + restrict account.
    """
    _log(alert, "BLOCK — critical risk. Reversal and restriction initiated.")
    _log_flags(alert)

    print(
        f"\n{'='*60}\n"
        f"  🚨 FRAUD BLOCK — CRITICAL RISK\n"
        f"  Transaction : {alert.transaction_id}\n"
        f"  Risk Score  : {alert.risk_score}/100\n"
        f"  Decision    : {alert.decision}\n"
        f"  ML Score    : {alert.ml_score}\n"
        f"  RAG Score   : {alert.rag_score}\n"
        f"  Disagreement: {alert.disagreement}\n"
        f"  Flags       : {', '.join(alert.anomaly_flags_list[:3])}\n"
        f"  Reasoning   : {alert.agent_reasoning[:120] if alert.agent_reasoning else 'N/A'}...\n"
        f"{'='*60}\n"
    )

    # TODO Phase 4 (Alert/Block Agent):
    #   - attempt_reversal(alert.transaction_id)
    #   - freeze_account(alert.customer_id)
    #   - send_block_notification(alert.customer_id)
    # These are handled by the Alert/Block Agent in the full pipeline.

    return 'BLOCK_AND_REVERSAL_INITIATED'


# ── Logging helpers ────────────────────────────────────────────────────────────

def _log(alert: FraudAlert, message: str):
    print(
        f"[MonitoringAgent] {message} | "
        f"txn={alert.transaction_id} | "
        f"score={alert.risk_score} | "
        f"ml={alert.ml_score} | "
        f"rag={alert.rag_score} | "
        f"fallback={alert.fallback_mode} | "
        f"cold_start={alert.cold_start_profile}"
    )


def _log_flags(alert: FraudAlert):
    if alert.anomaly_flags_list:
        flags_str = ' | '.join(alert.anomaly_flags_list[:5])
        print(f"[MonitoringAgent] Flags: {flags_str}")


def _fire_pattern_agent_for_alert(alert_id: int, payment_id: str):
    """
    [FIX-1] Fires the Pattern Recognition Agent after TMA completes.

    This is called from execute_response() AFTER the fraud_alert has been
    written to the database. This ensures PRA has the TMA result available
    immediately, without the 12-second timeout race condition.

    PRA processes:
      - TMA result (score, decision, anomalies)
      - Historical TMA alerts (last 10 per customer)
      - Network alerts (cross-customer recipient analysis)
      - RAG adjustment (pattern context from KB)
      - Final pattern verdict
    """
    import threading

    def _run():
        try:
            from et_service.pattern_agent.pra_agent import process_alert
            process_alert(alert_id)
        except Exception as e:
            print(f"[MonitoringAgent→PRA] Unhandled error firing PRA: {e}")
            import traceback
            traceback.print_exc()

    thread = threading.Thread(target=_run, daemon=True, name=f"pattern-agent-{payment_id}")
    thread.start()