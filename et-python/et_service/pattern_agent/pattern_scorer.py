"""
pattern_scorer.py  (pra)
──────────────────────────
Module 4 of the PRA pipeline — score fusion and verdict mapping.

Implements the exact formula from the PDF implementation guide (Section 4):

  rag_pattern_score = precedent_adj + reg_adj          [0, ~60]

  combined_raw = (BILSTM_WEIGHT × bilstm_score)
               + (RAG_PATTERN_WEIGHT × rag_pattern_score)

  final_pattern_score = clip(combined_raw × urgency_multiplier, 0, 100)

Verdict mapping:
  [0,  35] → DE-ESCALATE
  [36, 60] → MAINTAIN
  [61, 80] → ESCALATE
  [81, 100]→ CRITICAL  ← RAA activates T1 + STR auto-draft

Note: 'CRITICAL' is the token RAA checks for. Do NOT change this label.
"""

from et_service.pattern_agent.constants import (
    BILSTM_WEIGHT,
    RAG_PATTERN_WEIGHT,
    DECISION_TIERS,
)


def compute_pattern_score(
    bilstm_score:      float,
    precedent_adj:     float,
    reg_adj:           float,
    urgency_multiplier: float,
) -> dict:
    """
    Fuses BiLSTM and RAG signals into the final PRA pattern score.

    Parameters:
      bilstm_score       — raw BiLSTM output [0, 100]
      precedent_adj      — L2 similarity-weighted severity [0, ~40]
      reg_adj            — L1 additive regulatory adjustment [0, ~20]
      urgency_multiplier — L3 typology urgency factor (e.g. 1.8 for TY-19)

    Returns dict with:
      final_pattern_score : int    0–100
      pra_verdict         : str    DE-ESCALATE / MAINTAIN / ESCALATE / CRITICAL
      rag_pattern_score   : float  combined RAG contribution
      combined_raw        : float  before urgency multiplier clamping
    """
    # Step 1: combine RAG contributions
    rag_pattern_score = precedent_adj + reg_adj              # [0, ~60]

    # Step 2: weighted sum
    combined_raw = (
        BILSTM_WEIGHT      * bilstm_score
      + RAG_PATTERN_WEIGHT * rag_pattern_score
    )

    # Step 3: apply urgency multiplier, then clamp to [0, 100]
    # urgency_multiplier of 1.0 = no effect
    # urgency_multiplier of 1.8 (TY-19) amplifies by 80%
    final_pattern_score = max(0.0, min(100.0, combined_raw * urgency_multiplier))
    final_pattern_score = int(round(final_pattern_score))

    pra_verdict = _score_to_verdict(final_pattern_score)

    return {
        'final_pattern_score': final_pattern_score,
        'pra_verdict':         pra_verdict,
        'rag_pattern_score':   round(rag_pattern_score, 2),
        'combined_raw':        round(combined_raw, 2),
    }


def build_agent_reasoning(
    bilstm_score:       float,
    precedent_adj:      float,
    reg_adj:            float,
    urgency_multiplier: float,
    typology_code:      str | None,
    l3_similarity:      float,
    n_cases:            int,
    final_pattern_score: int,
    pra_verdict:        str,
    reg_citations:      list[dict],
) -> str:
    """
    Builds the human-readable agent_reasoning string written to fraud_alerts.
    This is forwarded to RAA and forms part of the compliance audit trail.
    """
    parts = [
        f"PRA Score: {final_pattern_score}/100 → {pra_verdict}.",
        f"BiLSTM: {bilstm_score:.1f} (weight={BILSTM_WEIGHT}).",
        f"RAG: precedent_adj={precedent_adj:.1f} ({n_cases} cases) + "
        f"reg_adj={reg_adj:.1f} = {precedent_adj + reg_adj:.1f} "
        f"(weight={RAG_PATTERN_WEIGHT}).",
    ]

    if typology_code:
        parts.append(
            f"Typology: {typology_code} (L3 sim={l3_similarity:.2f}, "
            f"urgency×{urgency_multiplier:.2f})."
        )
    else:
        parts.append("No typology match above threshold.")

    if reg_citations:
        citation_refs = [c.get('pmla_section', '') for c in reg_citations if c.get('pmla_section')]
        if citation_refs:
            parts.append(f"Regulatory citations: {', '.join(citation_refs)}.")

    return ' '.join(parts)


def _score_to_verdict(score: int) -> str:
    """Maps a 0–100 score to a PRA verdict label."""
    for lo, hi, label in DECISION_TIERS:
        if lo <= score <= hi:
            return label
    return 'CRITICAL'   # score > 100 safety net
