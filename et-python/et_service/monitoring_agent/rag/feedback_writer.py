"""
feedback_writer.py
──────────────────
Self-improvement engine — writes investigation outcomes back into
the ChromaDB knowledge base so all three RAG layers improve over time.

Writes to three collections:
  L2_fraud_cases     — confirmed case with feature vector embedding
  L4_dynamic_weights — performance record (ml_score, rag_score, correct_score)
  L5_feedback_log    — audit log (key-value, no embedding)

This is the ONLY writer to ChromaDB. All agents are read-only at runtime.

Usage:
  from et_service.monitoring_agent.rag.feedback_writer import write_feedback

  write_feedback(
      alert_id          = 42,
      transaction_id    = "TX20240301...",
      outcome           = "confirmed_fraud",
      investigator_notes= "Account takeover via SIM swap",
      anomaly_features  = {...},     # original 15-feature dict from extractor
      ml_score_at_time  = 72,        # ml_score stored in fraud_alert
      rag_score_at_time = 65,        # rag_score stored in fraud_alert
      pattern           = "account_takeover",
      amount            = 48000.0,
      signals           = ["late_night", "new_recipient", "velocity_burst"],
  )

Key fixes vs original:
  [FIX-1] L2 writes use upsert_vector_documents() with FraudFeatureEncoder
          vectors — NOT text documents embedded by SentenceTransformer.
  [FIX-2] L2 metadata includes confirmed_risk_score (numeric) so
          rag_layer._score_l2() can compute the similarity-weighted average.
  [FIX-3] L4 writes use the correct schema: ml_score, rag_score, correct_score.
          _get_l4_weights() in rag_layer.py reads these fields.
          The old weight_adjustment: ±5.0 scalar is removed entirely.
  [FIX-4] write_feedback() accepts anomaly_features, ml_score_at_time,
          rag_score_at_time — required for [FIX-1] and [FIX-3].
  [FIX-5] L5 uses upsert_keyvalue() — no embedding, no HNSW.
  [FIX-6] Best-effort atomicity: if L4 or L5 fail after L2 succeeds,
          errors are logged individually rather than leaving the caller
          unaware of partial writes.
"""

from datetime import datetime

from et_service.monitoring_agent.rag.vector_store import (
    upsert_vector_documents,
    upsert_keyvalue,
    COLLECTIONS,
)
from et_service.monitoring_agent.rag.encoders import encode_features_for_l2


def write_feedback(alert_id: int,
                   transaction_id: str,
                   outcome: str,
                   investigator_notes: str,
                   anomaly_features: dict,        # [FIX-4]
                   ml_score_at_time: int,          # [FIX-4]
                   rag_score_at_time: int | None,  # [FIX-4]
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

    # Derive the ground-truth correct score from the investigation outcome
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


# ── Internal writers ───────────────────────────────────────────────────────────

def _write_l2_case(alert_id, transaction_id, outcome, notes,
                   pattern, amount, signals_str, correct_score, severity,
                   anomaly_features, timestamp):
    """
    [FIX-1] Upserts a confirmed case into L2_fraud_cases using the
    FraudFeatureEncoder (bootstrap) vector — NOT a text embedding.

    [FIX-2] confirmed_risk_score stored in metadata for rag_layer._score_l2().
    """
    # Encode the original feature vector
    feature_vector = encode_features_for_l2(anomaly_features)

    outcome_label = {
        'confirmed_fraud':       'Confirmed Fraud',
        'confirmed_suspicious':  'Confirmed Suspicious Activity',
        'false_positive':        'False Positive — Legitimate',
    }.get(outcome, outcome)

    # Human-readable document stored alongside the vector (for debugging)
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
            'confirmed_risk_score': str(correct_score),   # [FIX-2] numeric
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
    """
    [FIX-3] Writes a performance record to L4_dynamic_weights.

    Schema: ml_score, rag_score, correct_score — the three values that
    _get_l4_weights() in rag_layer.py uses to compute accuracy:
      ml_acc  = 1 / (1 + |ml_score  - correct_score|)
      rag_acc = 1 / (1 + |rag_score - correct_score|)

    The old weight_adjustment scalar is removed entirely.
    """
    feature_vector = encode_features_for_l2(anomaly_features)

    # rag_score may be None if RAG was unavailable at decision time
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
    """
    [FIX-5] Audit log using upsert_keyvalue() — no vector embedding.
    Retrievable by alert_id only, never by similarity.
    """
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


# ── Mapping helpers ────────────────────────────────────────────────────────────

def _outcome_to_correct_score(outcome: str) -> float:
    """
    Maps investigation outcome to the ground-truth risk score.
    This is what the Decision Engine SHOULD have produced.
    Used as 'correct_score' in L4 performance records.
    """
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