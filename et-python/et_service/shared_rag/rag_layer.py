"""
rag_layer.py  (shared_rag)
──────────────────────────
The 4-layer RAG pipeline shared across all Jatayu agents.
Moved from et_service/monitoring_agent/rag/rag_layer.py.

Queries ChromaDB across four collections to build a knowledge-backed
risk score. Used by TMA directly; used by PRA via rag_scorer.py wrapper.

  Layer 2 → L2_fraud_cases     : similarity-weighted confirmed fraud risk score
  Layer 1 → L1_regulatory      : regulatory adjustment from RBI/PMLA rules
  Layer 3 → L3_typologies      : FIU-IND typology pattern adjustment
  Layer 4 → L4_dynamic_weights : dynamic ml_weight / rag_weight from accuracy history
"""

from et_service.shared_rag.vector_store import (
    query_by_text, query_by_vector, collection_count, COLLECTIONS
)
from et_service.shared_rag.encoders import (
    encode_features_for_l2,
    encode_flags_for_l3,
    encode_transaction_for_regulatory,
)
from et_service.monitoring_agent.constants import (
    DIST_HIGH, DIST_MEDIUM, DIST_LOW,
    RAG_CONFIDENCE_THRESHOLD_DIST,
    DEFAULT_ML_WEIGHT, DEFAULT_RAG_WEIGHT,
    L4_MIN_RECORDS_FOR_DYNAMIC_WEIGHTS, L4_QUERY_K,
    L2_MAX_SCORE, L1_MAX_ADJ, L3_MAX_ADJ, L4_MAX_ADJ,
)


def get_rag_assessment(transaction: dict,
                       anomaly_features: dict,
                       anomaly_flag_labels: list[str],
                       ml_result: dict,
                       profile: dict | None = None) -> dict:
    """
    Main entry point for the RAG Layer.
    Used by TMA (Stage 4) and PRA (via rag_scorer.py).

    Returns:
      rag_score       : int 0-100
      confidence      : float 0-1  — max L2 cosine similarity
      ml_weight       : float      — to be used by Decision Engine
      rag_weight      : float      — to be used by Decision Engine
      citations       : list[dict]
      reasoning       : str
      matched_rules   : list[str]
      matched_patterns: list[str]
      rag_available   : bool
    """
    try:
        if not _kb_is_available():
            return _unavailable_result(
                "Knowledge base empty — run kb_ingest scripts first"
            )

        # ── Build query vectors / texts ────────────────────────────────
        feature_vec = encode_features_for_l2(anomaly_features)
        signal_vec  = encode_flags_for_l3(anomaly_flag_labels)
        reg_text    = encode_transaction_for_regulatory(
            transaction, anomaly_features, profile
        )

        # ── Layer 2: Historical fraud cases ────────────────────────────
        l2_result = query_by_vector(COLLECTIONS['L2'], feature_vec, n_results=10)
        l2_score, l2_citations, l2_reasoning, confidence = _score_l2(l2_result)

        # ── Layer 1: Regulatory rules ──────────────────────────────────
        l1_result = query_by_text(COLLECTIONS['L1'], reg_text, n_results=5)
        l1_adj, l1_citations, l1_rules = _score_l1(l1_result)

        # ── Layer 3: Fraud typologies ──────────────────────────────────
        l3_result = query_by_vector(COLLECTIONS['L3'], signal_vec, n_results=3)
        l3_adj, l3_citations, l3_patterns, l3_typology = _score_l3(l3_result)

        # ── Layer 4: Dynamic weights ───────────────────────────────────
        ml_weight, rag_weight = _get_l4_weights(feature_vec)

        # ── Assemble RAG score ─────────────────────────────────────────
        raw_rag = l2_score + l1_adj + l3_adj
        rag_score = int(max(0, min(100, round(raw_rag))))

        all_citations = l2_citations + l1_citations + l3_citations

        reasoning = _build_reasoning(
            rag_score, confidence, l2_score, l1_adj, l3_adj,
            l2_reasoning, l1_rules, l3_patterns, ml_result,
            ml_weight, rag_weight,
        )

        return {
            'rag_score':        rag_score,
            'confidence':       round(confidence, 4),
            'ml_weight':        ml_weight,
            'rag_weight':       rag_weight,
            'citations':        all_citations,
            'reasoning':        reasoning,
            'matched_rules':    l1_rules,
            'matched_patterns': l3_patterns,
            'typology_code':    l3_typology,
            'rag_available':    True,
        }

    except Exception as e:
        print(f"[RAGLayer] Error: {e}")
        return _unavailable_result(f"RAG layer error: {e}")


# ── Layer scoring functions ────────────────────────────────────────────────────

def _score_l2(result: dict) -> tuple[float, list[dict], list[str], float]:
    """L2 scoring: similarity-weighted average of confirmed_risk_score."""
    documents = result['documents'][0] if result['documents'] else []
    distances = result['distances'][0] if result['distances'] else []
    metadatas = result['metadatas'][0] if result['metadatas'] else []

    citations      = []
    reasoning_parts = []

    if distances:
        confidence = float(1.0 - min(distances))
    else:
        confidence = 0.0

    relevant = [
        (doc, dist, meta)
        for doc, dist, meta in zip(documents, distances, metadatas)
        if dist <= DIST_LOW
    ]

    if not relevant:
        return 0.0, citations, reasoning_parts, confidence

    similarities = [1.0 - d for _, d, _ in relevant]
    sim_total    = sum(similarities)

    weighted_risk = 0.0
    for (doc, dist, meta), sim in zip(relevant, similarities):
        outcome   = meta.get('outcome', 'unknown')
        severity  = meta.get('severity', 'MEDIUM')
        pattern   = meta.get('pattern', 'unknown')
        risk_score = float(meta.get('confirmed_risk_score', _severity_to_risk(severity)))

        citations.append({
            'source':     'L2_fraud_cases',
            'id':         pattern,
            'distance':   round(dist, 4),
            'similarity': round(1 - dist, 4),
            'severity':   severity,
            'outcome':    outcome,
        })

        if outcome in ('confirmed_fraud', 'confirmed_suspicious'):
            weighted_risk += risk_score * (sim / sim_total)
            if dist <= DIST_HIGH:
                reasoning_parts.append(
                    f"Strong match ({1-dist:.0%} similarity) to confirmed "
                    f"{pattern} case (risk score: {risk_score:.0f})"
                )
            elif dist <= DIST_MEDIUM:
                reasoning_parts.append(
                    f"Moderate match ({1-dist:.0%}) to {pattern} case"
                )
        elif outcome == 'false_positive':
            weighted_risk -= (risk_score * 0.3) * (sim / sim_total)
            if dist <= DIST_MEDIUM:
                reasoning_parts.append(
                    f"Matches known false positive ({pattern}) — tempering score"
                )

    base_score = max(0.0, min(float(L2_MAX_SCORE), weighted_risk))
    return base_score, citations, reasoning_parts, confidence


def _score_l1(result: dict) -> tuple[float, list[dict], list[str]]:
    """L1 regulatory adjustment."""
    adj       = 0.0
    citations = []
    rules     = []

    documents = result['documents'][0] if result['documents'] else []
    distances = result['distances'][0] if result['distances'] else []
    metadatas = result['metadatas'][0] if result['metadatas'] else []

    for doc, dist, meta in zip(documents, distances, metadatas):
        citations.append({
            'source':   'L1_regulatory',
            'id':       meta.get('rule_type', 'unknown'),
            'distance': round(dist, 4),
            'severity': meta.get('severity', 'MEDIUM'),
        })

        if dist > DIST_MEDIUM:
            continue

        rule_type = meta.get('rule_type', '')
        severity  = meta.get('severity', 'MEDIUM')
        rules.append(f"{rule_type} ({severity})")

        if severity == 'CRITICAL':
            adj += 20
        elif severity == 'HIGH':
            adj += 15
        elif severity == 'MEDIUM':
            adj += 8

    return min(float(L1_MAX_ADJ), adj), citations, rules


def _score_l3(result: dict) -> tuple[float, list[dict], list[str], str | None]:
    """L3 typology match."""
    adj        = 0.0
    citations  = []
    patterns   = []
    best_typology = None
    best_sim      = 0.0

    documents = result['documents'][0] if result['documents'] else []
    distances = result['distances'][0] if result['distances'] else []
    metadatas = result['metadatas'][0] if result['metadatas'] else []

    for doc, dist, meta in zip(documents, distances, metadatas):
        typology   = meta.get('typology', 'unknown')
        risk_level = meta.get('risk_level', 'MEDIUM')
        base_risk  = float(meta.get('base_risk_score', _risk_level_to_score(risk_level)))
        sim        = 1.0 - dist

        citations.append({
            'source':     'L3_typologies',
            'id':         typology,
            'distance':   round(dist, 4),
            'similarity': round(sim, 4),
            'risk_level': risk_level,
        })

        if dist > DIST_MEDIUM:
            continue

        if sim > (1.0 - RAG_CONFIDENCE_THRESHOLD_DIST):
            adj += base_risk * sim
            patterns.append(f"{typology} ({risk_level})")
            if sim > best_sim:
                best_sim      = sim
                best_typology = typology

    return min(float(L3_MAX_ADJ), adj), citations, patterns, best_typology


def _get_l4_weights(feature_vec: list[float]) -> tuple[float, float]:
    """Queries L4 for agent performance history and derives ml_weight / rag_weight."""
    try:
        count = collection_count(COLLECTIONS['L4'])
        if count < L4_MIN_RECORDS_FOR_DYNAMIC_WEIGHTS:
            return DEFAULT_ML_WEIGHT, DEFAULT_RAG_WEIGHT

        result = query_by_vector(
            COLLECTIONS['L4'], feature_vec, n_results=L4_QUERY_K
        )
        metadatas = result['metadatas'][0] if result['metadatas'] else []
        distances = result['distances'][0] if result['distances'] else []

        ml_acc_sum  = 0.0
        rag_acc_sum = 0.0
        used        = 0

        for meta, dist in zip(metadatas, distances):
            if dist > DIST_MEDIUM:
                continue
            try:
                ml_s     = float(meta['ml_score'])
                rag_s    = float(meta['rag_score'])
                correct  = float(meta['correct_score'])
            except (KeyError, ValueError):
                continue

            ml_acc_sum  += 1.0 / (1.0 + abs(ml_s  - correct))
            rag_acc_sum += 1.0 / (1.0 + abs(rag_s - correct))
            used += 1

        if used == 0 or (ml_acc_sum + rag_acc_sum) == 0:
            return DEFAULT_ML_WEIGHT, DEFAULT_RAG_WEIGHT

        total = ml_acc_sum + rag_acc_sum
        return round(ml_acc_sum / total, 4), round(rag_acc_sum / total, 4)

    except Exception as e:
        print(f"[RAGLayer] L4 weight retrieval failed: {e}. Using defaults.")
        return DEFAULT_ML_WEIGHT, DEFAULT_RAG_WEIGHT


# ── Reasoning builder ──────────────────────────────────────────────────────────

def _build_reasoning(rag_score, confidence, l2_score, l1_adj, l3_adj,
                     l2_reasoning, l1_rules, l3_patterns,
                     ml_result, ml_weight, rag_weight) -> str:
    parts = []

    conf_label = "high" if confidence >= 0.65 else "low"
    parts.append(
        f"RAG score: {rag_score}/100 "
        f"(cases: {l2_score:.0f} + regulatory: {l1_adj:.0f} + patterns: {l3_adj:.0f}). "
        f"Retrieval confidence: {confidence:.2f} ({conf_label}). "
        f"Fusion weights — ML: {ml_weight:.2f}, RAG: {rag_weight:.2f}."
    )

    ml_score   = ml_result.get('ml_score', 0)
    is_anomaly = ml_result.get('is_anomaly', False)
    parts.append(
        f"ML model: {ml_score}/100 "
        f"({'anomaly detected' if is_anomaly else 'normal pattern'})."
    )

    if l2_reasoning:
        parts.append("Case matches: " + "; ".join(l2_reasoning) + ".")
    if l1_rules:
        parts.append("Regulatory rules: " + ", ".join(l1_rules) + ".")
    if l3_patterns:
        parts.append("Typology matches: " + ", ".join(l3_patterns) + ".")

    if not l2_reasoning and not l1_rules and not l3_patterns:
        parts.append(
            "No significant KB matches found — pattern does not closely resemble "
            "known fraud cases, regulatory violations, or established typologies."
        )

    return " ".join(parts)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _kb_is_available() -> bool:
    return any(
        collection_count(COLLECTIONS[k]) > 0
        for k in ('L1', 'L2', 'L3')
    )


def _unavailable_result(reason: str) -> dict:
    return {
        'rag_score':        None,
        'confidence':       0.0,
        'ml_weight':        DEFAULT_ML_WEIGHT,
        'rag_weight':       DEFAULT_RAG_WEIGHT,
        'citations':        [],
        'reasoning':        f'RAG unavailable: {reason}',
        'matched_rules':    [],
        'matched_patterns': [],
        'typology_code':    None,
        'rag_available':    False,
    }


def _severity_to_risk(severity: str) -> float:
    return {'CRITICAL': 85.0, 'HIGH': 70.0, 'MEDIUM': 50.0, 'LOW': 25.0}.get(
        severity, 50.0
    )


def _risk_level_to_score(risk_level: str) -> float:
    return {
        'CRITICAL': 85.0,
        'HIGH': 70.0,
        'MEDIUM-HIGH': 62.0,
        'MEDIUM': 50.0,
        'LOW': 25.0,
    }.get(risk_level, 50.0)
