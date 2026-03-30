"""
pra_feedback_writer.py  (pra)
───────────────────────────────
Module 6 of the PRA pipeline — novel pattern feedback to L3.

When the BiLSTM detects a high-risk sequence (score ≥ 70) but the L3
pattern library has no matching typology (cosine similarity < 0.40),
this is evidence of a potentially novel fraud pattern.

This module:
  1. Saves the hidden state + metadata to a staging table
     (novel_pattern_candidates) for human review.
  2. After human analyst confirms it as a new typology, the record
     is ingested into ChromaDB L3 via ingest_patterns.py.
  3. Future BiLSTM runs will match against this new typology,
     closing the self-learning loop.

The write is best-effort — a failure here never blocks the pipeline.
"""

from __future__ import annotations
import json
import numpy as np

from et_dao.pattern_dao import save_novel_pattern_candidate


def write_novel_pattern_to_l3(
    alert_id:    int,
    hidden_state: np.ndarray,
    bilstm_score: float,
    customer_id:  str,
    flag_labels:  list[str],
) -> None:
    """
    Stages a novel pattern candidate for human review and eventual L3 ingestion.

    Parameters:
      alert_id      — fraud_alert row that triggered this (for traceability)
      hidden_state  — (128,) BiLSTM hidden vector; stored as JSON for later
                      L3 ingestion with SignalSequenceEncoder
      bilstm_score  — raw BiLSTM output (≥70 guaranteed by caller)
      customer_id   — for analyst context
      flag_labels   — active anomaly flags from TMA
    """
    candidate = {
        'alert_id':        alert_id,
        'customer_id':     customer_id,
        'bilstm_score':    round(bilstm_score, 2),
        'flag_labels':     json.dumps(flag_labels),
        'hidden_state':    json.dumps(hidden_state.tolist()),
        # Analyst fills these after review:
        'review_status':   'PENDING',   # PENDING → CONFIRMED / REJECTED
        'assigned_typology': None,
        'urgency_multiplier': None,
        'regulatory_action':  None,
    }
    save_novel_pattern_candidate(candidate)
    print(
        f"[FeedbackWriter] Novel pattern staged — alert_id={alert_id}, "
        f"bilstm_score={bilstm_score:.1f}, flags={flag_labels}"
    )
