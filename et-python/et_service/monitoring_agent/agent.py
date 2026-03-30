"""
agent.py
────────
The Monitoring Agent orchestrator — single entry point for every payment.

Called by payment_routes._fire_monitoring_agent() in a background daemon
thread after the payment has already been committed and returned to the user.

Pipeline stages:
  Stage 1 : Build behavioural profile
  Stage 2 : Extract anomaly features (15 signals)
  Stage 3 : ML Layer  (Isolation Forest — fallback to rule-based on failure)
  Stage 4 : RAG Layer (ChromaDB 4-layer retrieval)
  Stage 5 : Decision Engine (score fusion)
  Stage 6 : Response Executor (DB writes + actions)

Key fixes vs original:
  [FIX-1] Stage 3 ML failure no longer aborts the pipeline.
          A synthetic fallback ml_result is constructed and the pipeline
          continues in RAG-only mode. Aborting on a missing model file
          would leave all transactions unscored — a compliance gap.
  [FIX-2] profile is now passed to get_rag_assessment() so the regulatory
          query encoder has customer context (cold_start, profile_strength).
  [FIX-3] Removed stale llm_layer references from comments.
"""

from et_service.monitoring_agent.profile_builder   import get_or_build_profile
from et_service.monitoring_agent.anomaly_extractor import (
    extract_anomaly_features,
    get_anomaly_flag_labels,
)
from et_service.monitoring_agent.ml_layer          import get_ml_risk_score
from et_service.monitoring_agent.rag.rag_layer     import get_rag_assessment
from et_service.monitoring_agent.decision_engine   import make_decision
from et_service.monitoring_agent.response_executor import execute_response


def evaluate_transaction(payment_result: dict):
    """
    Full Monitoring Agent pipeline for a single payment.

    payment_result dict (from payment_service.process_payment()):
    {
        payment_id            : str
        debit_transaction_id  : str
        sender_customer_id    : str
        sender_account        : str
        recipient_account     : str
        recipient_customer_id : str
        amount                : float
        description           : str
        new_sender_balance    : float
    }
    """
    customer_id = payment_result['sender_customer_id']
    payment_id  = payment_result['payment_id']

    _log(f"Starting evaluation | payment={payment_id} | customer={customer_id}")

    # ── Stage 1: Build behavioural profile ────────────────────────────
    try:
        profile = get_or_build_profile(customer_id)
        _log(f"Stage 1 complete | cold_start={profile['cold_start']} | "
             f"strength={profile['profile_strength']:.0%}")
    except Exception as e:
        _log(f"Stage 1 FAILED — {e}. Aborting evaluation.")
        _mark_failed(payment_result)
        return {'decision': 'ALLOW', 'risk_score': None, 'error': str(e)}

    # ── Stage 2: Extract anomaly features ─────────────────────────────
    try:
        anomaly_features    = extract_anomaly_features(payment_result, profile)
        anomaly_flag_labels = get_anomaly_flag_labels(anomaly_features)
        _log(f"Stage 2 complete | flags={len(anomaly_flag_labels)} | "
             f"z_score={anomaly_features['amount_z_score']}")
    except Exception as e:
        _log(f"Stage 2 FAILED — {e}. Aborting evaluation.")
        _mark_failed(payment_result)
        return {'decision': 'ALLOW', 'risk_score': None, 'error': str(e)}

    # ── Stage 3: ML Layer ─────────────────────────────────────────────
    # [FIX-1] ML failure does NOT abort. The pipeline continues in
    # RAG-only mode. The Decision Engine will see model_loaded=False
    # and the confidence-based fallback logic in decision_engine.py
    # will handle weighting appropriately.
    try:
        ml_result = get_ml_risk_score(anomaly_features)
        _log(f"Stage 3 complete | ml_score={ml_result['ml_score']} | "
             f"is_anomaly={ml_result['is_anomaly']} | "
             f"model_loaded={ml_result['model_loaded']}")
    except Exception as e:
        _log(f"Stage 3 FAILED — {e}. Continuing in RAG-only mode.")
        # Construct a neutral fallback — RAG layer will carry the full weight
        ml_result = {
            'ml_score':    50,
            'raw_score':   0.0,
            'is_anomaly':  False,
            'model_loaded': False,
        }

    # ── Stage 4: RAG Layer ────────────────────────────────────────────
    # RAG failure is handled gracefully inside rag_layer — it always
    # returns a result dict (with rag_available=False on error).
    # We never abort the pipeline because of a ChromaDB issue.
    try:
        rag_result = get_rag_assessment(
            transaction        = payment_result,
            anomaly_features   = anomaly_features,
            anomaly_flag_labels= anomaly_flag_labels,
            ml_result          = ml_result,
            profile            = profile,   # [FIX-2] regulatory query context
        )
        _log(f"Stage 4 complete | rag_available={rag_result['rag_available']} | "
             f"rag_score={rag_result.get('rag_score')} | "
             f"confidence={rag_result.get('confidence', 0.0):.2f} | "
             f"citations={len(rag_result.get('citations', []))}")
    except Exception as e:
        # Belt-and-suspenders: rag_layer handles its own errors.
        # This catches anything that slips through.
        _log(f"Stage 4 unexpected error — {e}. Continuing in ML-only fallback.")
        from et_service.monitoring_agent.constants import DEFAULT_ML_WEIGHT, DEFAULT_RAG_WEIGHT
        rag_result = {
            'rag_score':        None,
            'confidence':       0.0,
            'ml_weight':        DEFAULT_ML_WEIGHT,
            'rag_weight':       DEFAULT_RAG_WEIGHT,
            'citations':        [],
            'reasoning':        f'RAG layer error: {e}',
            'matched_rules':    [],
            'matched_patterns': [],
            'typology_code':    None,
            'rag_available':    False,
        }

    # ── Stage 5: Decision Engine ──────────────────────────────────────
    try:
        alert = make_decision(
            transaction        = payment_result,
            profile            = profile,
            anomaly_features   = anomaly_features,
            anomaly_flag_labels= anomaly_flag_labels,
            ml_result          = ml_result,
            rag_result         = rag_result,
        )
        _log(f"Stage 5 complete | final_score={alert.risk_score} | "
             f"decision={alert.decision} | "
             f"disagreement={alert.disagreement} | "
             f"low_conf_fallback={getattr(alert, 'low_confidence_fallback', False)}")
    except Exception as e:
        _log(f"Stage 5 FAILED — {e}. Aborting evaluation.")
        _mark_failed(payment_result)
        return {'decision': 'ALLOW', 'risk_score': None, 'error': str(e)}

    # ── Stage 6: Response Executor ────────────────────────────────────
    try:
        result = execute_response(alert, payment_id)
        _log(f"Stage 6 complete | alert_id={result['alert_id']} | "
             f"action={result['action_taken']}")
    except Exception as e:
        _log(f"Stage 6 FAILED — {e}. Alert may not be persisted.")
        # Payment itself succeeded — do not mark transaction FAILED.
        # The missing alert is an audit gap, handled by reconciliation cron.
        return {'decision': alert.decision, 'risk_score': alert.risk_score, 'error': str(e)}

    _log(f"Evaluation complete | decision={alert.decision} | "
         f"score={alert.risk_score} | payment={payment_id}")
    
    return {'decision': alert.decision, 'risk_score': alert.risk_score, 'alert_id': result.get('alert_id')}


# ── Internal helpers ───────────────────────────────────────────────────────────

def _log(message: str):
    print(f"[MonitoringAgent] {message}")


def _mark_failed(payment_result: dict):
    """
    Sets agent_status=FAILED on the transaction row when a pipeline
    stage aborts. The payment itself is unaffected.

    A reconciliation cron job retries FAILED evaluations every 5 minutes.
    TODO: implement the cron in et_service/cron/retry_failed_evaluations.py
    """
    try:
        from et_dao.monitoring_dao import update_transaction_after_evaluation
        update_transaction_after_evaluation(
            transaction_id=payment_result['debit_transaction_id'],
            risk_score=None,
            fraud_flag=0,
            agent_status='FAILED',
        )
        _log(
            f"Marked transaction {payment_result['debit_transaction_id']} "
            f"as agent_status=FAILED."
        )
    except Exception as e:
        _log(f"Could not mark transaction as FAILED: {e}")