"""
feedback_writer.py  (shared_rag)
─────────────────────────────────
Self-improvement engine — writes investigation outcomes back into
the ChromaDB knowledge base so all three RAG layers improve over time.
Moved from et_service/monitoring_agent/rag/feedback_writer.py.
"""

from datetime import datetime

from et_service.shared_rag.vector_store import (
    upsert_vector_documents,
    upsert_keyvalue,
    COLLECTIONS,
)
from et_service.shared_rag.encoders import encode_features_for_l2


def write_feedback(alert_id: int,
                   transaction_id: str,
                   outcome: str,
                   investigator_notes: str,
                   anomaly_features: dict,
                   ml_score_at_time: int,
                   rag_score_at_time: int | None,
                   pattern: str = "unknown",
                   amount: float = 0.0,
                   signals: list[str] | None = None):
    """
    Writes investigation results to L2, L4, and L5.

    Parameters:
      alert_id          — fraud_alerts.id (primary key)
      transaction_id    — the evaluated transaction
      outcome           — "confirmed_fraud" | "confirmed_suspicious" | "false_positive"
      investigator_notes— human investigator's summary
      anomaly_features  — original 15-feature dict from anomaly_extractor
      ml_score_at_time  — ml_score field from the fraud_alert record
      rag_score_at_time — rag_score field from the fraud_alert record (may be None)
      pattern           — fraud typology if known
      amount            — transaction amount
      signals           — list of triggered signal names
    """
    timestamp   = datetime.now().isoformat()
    signals     = signals or []
    signals_str = ", ".join(signals) if signals else "none"

    correct_score = _outcome_to_correct_score(outcome)
    severity      = _outcome_to_severity(outcome)

    errors = []

    # ── L2: Add confirmed case with feature vector embedding ──────────
    try:
        _write_l2_case(
            alert_id, transaction_id, outcome, investigator_notes,
            pattern, amount, signals_str, correct_score, severity,
            anomaly_features, timestamp,
        )
    except Exception as e:
        errors.append(f"L2 write failed: {e}")
        print(f"[FeedbackWriter] ERROR — {errors[-1]}")

    # ── L4: Write performance record ──────────────────────────────────
    try:
        _write_l4_performance(
            alert_id, outcome, pattern, signals_str,
            ml_score_at_time, rag_score_at_time, correct_score,
            anomaly_features, timestamp,
        )
    except Exception as e:
        errors.append(f"L4 write failed: {e}")
        print(f"[FeedbackWriter] ERROR — {errors[-1]}")

    # ── L5: Audit log ─────────────────────────────────────────────────
    try:
        _write_l5_log(alert_id, transaction_id, outcome,
                      investigator_notes, timestamp)
    except Exception as e:
        errors.append(f"L5 write failed: {e}")
        print(f"[FeedbackWriter] ERROR — {errors[-1]}")

    if errors:
        print(
            f"[FeedbackWriter] Partial write for alert {alert_id} | "
            f"errors={len(errors)} | outcome={outcome} | pattern={pattern}"
        )
    else:
        print(
            f"[FeedbackWriter] Feedback written for alert {alert_id} | "
            f"outcome={outcome} | pattern={pattern} | "
            f"correct_score={correct_score}"
        )


def _write_l2_case(alert_id, transaction_id, outcome, notes,
                   pattern, amount, signals_str, correct_score, severity,
                   anomaly_features, timestamp):
    feature_vector = encode_features_for_l2(anomaly_features)

    outcome_label = {
        'confirmed_fraud':       'Confirmed Fraud',
        'confirmed_suspicious':  'Confirmed Suspicious Activity',
        'false_positive':        'False Positive — Legitimate',
    }.get(outcome, outcome)

    document = (
        f"{outcome_label}. Pattern: {pattern}. "
        f"Signals: {signals_str}. Notes: {notes}. "
        f"Alert: {alert_id}. Date: {timestamp[:10]}."
    )

    doc_id = f"FEEDBACK-L2-{alert_id}"

    upsert_vector_documents(
        collection_name=COLLECTIONS['L2'],
        ids=[doc_id],
        embeddings=[feature_vector],
        documents=[document],
        metadatas=[{
            'pattern':              pattern,
            'outcome':              outcome,
            'confirmed_risk_score': str(correct_score),
            'decisive_signals':     signals_str,
            'severity':             severity,
            'source':               'feedback',
            'alert_id':             str(alert_id),
            'timestamp':            timestamp,
        }],
    )


def _write_l4_performance(alert_id, outcome, pattern, signals_str,
                           ml_score, rag_score, correct_score,
                           anomaly_features, timestamp):
    feature_vector = encode_features_for_l2(anomaly_features)
    rag_score_val = rag_score if rag_score is not None else correct_score

    document = (
        f"Performance record: pattern={pattern}. "
        f"ML={ml_score}, RAG={rag_score_val}, Correct={correct_score:.0f}. "
        f"Outcome={outcome}. Signals={signals_str}."
    )

    doc_id = f"PERF-L4-{alert_id}"

    upsert_vector_documents(
        collection_name=COLLECTIONS['L4'],
        ids=[doc_id],
        embeddings=[feature_vector],
        documents=[document],
        metadatas=[{
            'ml_score':      str(ml_score),
            'rag_score':     str(rag_score_val),
            'correct_score': str(correct_score),
            'pattern':       pattern,
            'outcome':       outcome,
            'alert_id':      str(alert_id),
            'timestamp':     timestamp,
        }],
    )


def _write_l5_log(alert_id, transaction_id, outcome, notes, timestamp):
    document = (
        f"Feedback log | alert={alert_id} | txn={transaction_id} | "
        f"outcome={outcome} | ts={timestamp} | notes={notes}"
    )
    doc_id = f"LOG-L5-{alert_id}"

    upsert_keyvalue(
        collection_name=COLLECTIONS['L5'],
        ids=[doc_id],
        documents=[document],
        metadatas=[{
            'alert_id':       str(alert_id),
            'transaction_id': transaction_id,
            'outcome':        outcome,
            'timestamp':      timestamp,
        }],
    )


def _outcome_to_correct_score(outcome: str) -> float:
    return {
        'confirmed_fraud':       88.0,
        'confirmed_suspicious':  65.0,
        'false_positive':        15.0,
    }.get(outcome, 50.0)


def _outcome_to_severity(outcome: str) -> str:
    return {
        'confirmed_fraud':      'CRITICAL',
        'confirmed_suspicious': 'HIGH',
        'false_positive':       'LOW',
    }.get(outcome, 'MEDIUM')
