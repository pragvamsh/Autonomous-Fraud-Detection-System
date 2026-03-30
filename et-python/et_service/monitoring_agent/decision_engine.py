"""
decision_engine.py
──────────────────
Score fusion engine — Layer 5 of the Monitoring Agent pipeline.

Fuses ML and RAG scores into a single 0-100 risk score and decision.

Fusion modes (in order of priority):
  1. RAG unavailable           → ML score only
  2. Confidence < 0.65         → ML score only, floor at FLAG (31) [spec]
  3. |ml - rag| > 30           → Conservative (higher) score
  4. Normal                    → Weighted average using L4-derived weights

Key fixes vs original:
  [FIX-1] Default weights 40/60 (was 50/50) — spec: ml=0.40, rag=0.60.
  [FIX-2] Confidence-based fallback implemented (spec core conditional).
          confidence < 0.65 → discard RAG, use IF-only, floor at FLAG.
  [FIX-3] L4 dynamic weights (ml_weight, rag_weight) consumed from
          rag_result — passed through from rag_layer.py's L4 retrieval.
  [FIX-4] _fuse_scores is now a pure function — returns (score, flags dict)
          instead of mutating the alert object as a side effect.
  [FIX-5] Decision thresholds stored as ordered list of tuples — not a
          plain dict whose iteration order must be relied upon.
  [FIX-6] Cold start penalty interacts with confidence floor correctly.
"""

from et_model.fraud_alert import FraudAlert
from et_service.monitoring_agent.constants import (
    DEFAULT_ML_WEIGHT,
    DEFAULT_RAG_WEIGHT,
    DISAGREEMENT_THRESHOLD,
    COLD_START_PENALTY,
    LOW_CONFIDENCE_FLAG_FLOOR,
    RAG_CONFIDENCE_THRESHOLD_DIST,
    DECISION_TIERS,
    FEATURE_NAMES,
)

# Confidence threshold in similarity terms (spec: 0.65)
# RAG_CONFIDENCE_THRESHOLD_DIST is the distance equivalent (0.35)
# Similarity = 1 - distance, so threshold = 1 - 0.35 = 0.65
_CONFIDENCE_SIM_THRESHOLD = 1.0 - RAG_CONFIDENCE_THRESHOLD_DIST  # 0.65


def make_decision(transaction: dict,
                  profile: dict,
                  anomaly_features: dict,
                  anomaly_flag_labels: list[str],
                  ml_result: dict,
                  rag_result: dict) -> FraudAlert:
    """
    Fuses ML and RAG scores, applies spec-mandated fusion logic,
    and returns a populated FraudAlert.
    """
    alert = FraudAlert(
        transaction_id=transaction['debit_transaction_id'],
        customer_id=transaction['sender_customer_id'],
    )
    # Store only the 15 model features in the snapshot — ancillary fields
    # (current_hour, is_late_night) are excluded so the snapshot length
    # matches FEATURE_DIM=15 expected by PRA's sequence_builder.
    alert.anomaly_features = {k: anomaly_features[k] for k in FEATURE_NAMES}

    # ── ML result ─────────────────────────────────────────────────────
    alert.ml_score = ml_result['ml_score']

    # ── RAG result ────────────────────────────────────────────────────
    rag_available = rag_result.get('rag_available', False)
    alert.rag_available = rag_available

    if rag_available:
        alert.rag_score       = rag_result['rag_score']
        alert.rag_citations   = rag_result.get('citations', [])
        alert.agent_reasoning = rag_result.get('reasoning', '')
        alert.typology_code   = rag_result.get('typology_code')

        combined_flags = list(anomaly_flag_labels)
        for pattern in rag_result.get('matched_patterns', []):
            flag = f"RAG_PATTERN_MATCH: {pattern}"
            if flag not in combined_flags:
                combined_flags.append(flag)
        for rule in rag_result.get('matched_rules', []):
            flag = f"RAG_RULE_MATCH: {rule}"
            if flag not in combined_flags:
                combined_flags.append(flag)
        alert.anomaly_flags_list = combined_flags

    else:
        alert.rag_score          = None
        alert.rag_citations      = []
        alert.agent_reasoning    = rag_result.get(
            'reasoning', 'RAG unavailable — ML-only mode.'
        )
        alert.anomaly_flags_list = anomaly_flag_labels
        alert.fallback_mode      = True

    alert.cold_start_profile = bool(profile.get('cold_start', False))

    # ── [FIX-4] Pure score fusion — no alert mutation inside ──────────
    final_score, fusion_flags = _fuse_scores(
        ml_score     = alert.ml_score,
        rag_score    = alert.rag_score,
        rag_available= rag_available,
        confidence   = float(rag_result.get('confidence', 0.0)),
        ml_weight    = float(rag_result.get('ml_weight', DEFAULT_ML_WEIGHT)),
        rag_weight   = float(rag_result.get('rag_weight', DEFAULT_RAG_WEIGHT)),
        cold_start   = alert.cold_start_profile,
    )

    # Apply fusion flags to alert (pure assignment, not mutation inside helper)
    alert.disagreement            = fusion_flags.get('disagreement', False)
    alert.low_confidence_fallback = fusion_flags.get('low_confidence_fallback', False)

    alert.risk_score = final_score
    alert.decision   = _score_to_decision(final_score)

    return alert


# ── Pure score fusion ──────────────────────────────────────────────────────────

def _fuse_scores(ml_score: int,
                 rag_score: int | None,
                 rag_available: bool,
                 confidence: float,
                 ml_weight: float,
                 rag_weight: float,
                 cold_start: bool) -> tuple[int, dict]:
    """
    [FIX-4] Pure function — takes values, returns (score, flags_dict).
    Does not touch the alert object.

    Fusion logic (in priority order):
      1. RAG unavailable         → ML only
      2. confidence < 0.65       → ML only, floor at FLAG (spec mandatory)
      3. |ml - rag| > threshold  → conservative max
      4. Normal                  → weighted average with L4 weights
      5. Cold start penalty      → applied after all fusion
    """
    flags = {
        'disagreement':            False,
        'low_confidence_fallback': False,
    }

    if not rag_available or rag_score is None:
        # Mode 1: RAG unavailable
        base = float(ml_score)

    elif confidence < _CONFIDENCE_SIM_THRESHOLD:
        # Mode 2: [FIX-2] Low retrieval confidence — spec mandates IF-only
        # and a minimum FLAG verdict (score floored at 31).
        base = float(ml_score)
        flags['low_confidence_fallback'] = True
        # Floor applied AFTER cold start penalty below

    else:
        gap = abs(ml_score - rag_score)

        if gap > DISAGREEMENT_THRESHOLD:
            # Mode 3: Significant disagreement — be conservative
            base = float(max(ml_score, rag_score))
            flags['disagreement'] = True
        else:
            # Mode 4: [FIX-1][FIX-3] Normal weighted fusion with L4 weights
            # Weights come from L4 accuracy history (default 0.40/0.60)
            base = (ml_weight * ml_score) + (rag_weight * rag_score)

    # Cold start penalty
    if cold_start:
        base += COLD_START_PENALTY

    # [FIX-2] Apply FLAG floor for low-confidence mode
    if flags['low_confidence_fallback']:
        base = max(base, float(LOW_CONFIDENCE_FLAG_FLOOR))

    final = int(min(100, max(0, round(base))))
    return final, flags


def _score_to_decision(score: int) -> str:
    """
    [FIX-5] Maps 0-100 score to decision string.
    Uses ordered list of tuples — not a dict whose order could be changed.
    """
    for low, high, decision in DECISION_TIERS:
        if low <= score <= high:
            return decision
    return 'BLOCK'   # Safety net for score > 100