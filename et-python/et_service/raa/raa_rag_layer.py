"""
raa_rag_layer.py  (Module 5 — Most Important)
──────────────────────────────────────────────
Three ChromaDB retrievals that replace all hardcoded constants in RAA.

Retrieval 1 — L2_fraud_cases (K=15):
  Query vector: 128-d from FraudFeatureEncoder (encode_features_for_l2)
  Returns: pattern_mult (1.1–2.1), coldstart_adj (+8 to +14), network_adj, age_adj

Retrieval 2 — L1_regulatory (K=3):
  Query: specific natural-language strings targeting CTR/STR threshold chunks
  Returns: regulatory_adj, live ctr_single_threshold, ctr_aggregate_threshold

Retrieval 3 — L3_typologies:
  Query: typology_code from the fraud_alerts row
  Returns: full typology document for STR evidence + investigation notes

All retrievals reuse the existing vector_store.py public API.
ChromaDB dimension check is performed before the first query.

⚠  Collection dims:
   L2 → 128-d  (FraudFeatureEncoder)
   L1 → 384-d  (SentenceTransformer — text query)
   L3 → 256-d  (SignalSequenceEncoder)
"""

from et_service.monitoring_agent.rag.vector_store import (
    query_by_text,
    query_by_vector,
    collection_count,
    COLLECTIONS,
)
from et_service.shared_rag.encoders import encode_features_for_l2

# ── RAG default fallbacks ──────────────────────────────────────────────────────
_DEFAULT_PATTERN_MULT      = 1.5
_DEFAULT_COLDSTART_ADJ     = 10.0
_DEFAULT_NETWORK_ADJ       = 1.0
_DEFAULT_AGE_ADJ           = 0.0
_DEFAULT_REGULATORY_ADJ    = 0.0
_DEFAULT_CTR_SINGLE        = 1_000_000      # Rs. 10L (used ONLY as safety fallback)
_DEFAULT_CTR_AGGREGATE     = 500_000        # Rs. 5L  (used ONLY as safety fallback)

# L1 query strings (specific enough to retrieve CTR/STR threshold chunks)
_L1_CTR_QUERY = (
    "Cash Transaction Report threshold single transaction RBI "
    "reporting obligation amount limit rupees"
)
_L1_STR_QUERY = (
    "Suspicious Transaction Report PMLA structuring obligation "
    "FIU-IND filing requirement Enhanced Due Diligence threshold"
)
_L1_REGULATORY_QUERY = (
    "Enhanced Due Diligence threshold amount RBI Master Direction "
    "high risk customer enhanced monitoring"
)


def retrieve(data: dict, dims: dict) -> dict:
    """
    Main entry point for the RAA RAG layer.

    data   : full fraud_alerts row (from intelligence_aggregator)
    dims   : output of dimension_scorer (D1-D5, score_a)

    Returns a dict with:
      pattern_mult, coldstart_adj, network_adj, age_adj,
      regulatory_adj, ctr_single_threshold, ctr_aggregate_threshold,
      l3_typology_doc, str_obligation,
      l2_citations, l1_citations, l3_citations
    """
    feature_snapshot = data.get('feature_snapshot') or {}
    typology_code    = data.get('typology_code') or ''
    tier             = data.get('_tier', 'T2')   # injected by orchestrator
    customer_id      = data.get('customer_id', '')

    # ── Check ChromaDB availability ────────────────────────────────────────────
    l2_count = collection_count(COLLECTIONS['L2'])
    l1_count = collection_count(COLLECTIONS['L1'])
    l3_count = collection_count(COLLECTIONS['L3'])

    _log(f"KB check | L2={l2_count} L1={l1_count} L3={l3_count} docs")

    if l2_count == 0:
        _log("WARN: L2_fraud_cases is empty — bootstrap may not have run. Using defaults.")

    if l1_count == 0:
        _log("WARN: L1_regulatory is empty — CTR/STR thresholds will use fallback values.")

    # ── Retrieval 1: L2 fraud cases (K=15) ────────────────────────────────────
    l2_result = _retrieve_l2(feature_snapshot, tier, customer_id)

    # ── Retrieval 2: L1 regulatory (K=3) ──────────────────────────────────────
    l1_result = _retrieve_l1(data)

    # ── Retrieval 3: L3 typologies ─────────────────────────────────────────────
    l3_result = _retrieve_l3(typology_code, feature_snapshot)

    _log(
        f"RAG complete | customer={customer_id} | "
        f"pattern_mult={l2_result['pattern_mult']:.2f} | "
        f"coldstart_adj={l2_result['coldstart_adj']:+.1f} | "
        f"regulatory_adj={l1_result['regulatory_adj']:+.1f} | "
        f"ctr_threshold={l1_result['ctr_single_threshold']:,.0f} | "
        f"l3_typology={l3_result.get('typology_code', 'none')}"
    )

    return {
        # L2 outputs
        'pattern_mult':         l2_result['pattern_mult'],
        'coldstart_adj':        l2_result['coldstart_adj'],
        'network_adj':          l2_result['network_adj'],
        'age_adj':              l2_result['age_adj'],
        'l2_citations':         l2_result['citations'],

        # L1 outputs
        'regulatory_adj':       l1_result['regulatory_adj'],
        'ctr_single_threshold': l1_result['ctr_single_threshold'],
        'ctr_aggregate_threshold': l1_result['ctr_aggregate_threshold'],
        'l1_citations':         l1_result['citations'],

        # L3 outputs
        'l3_typology_doc':      l3_result.get('typology_doc'),
        'str_obligation':       l3_result.get('str_obligation', ''),
        'l3_typology_code':     l3_result.get('typology_code', typology_code),
        'l3_citations':         l3_result.get('citations', []),
    }


# ── Internal retrievals ────────────────────────────────────────────────────────

def _retrieve_l2(feature_snapshot: dict, tier: str, customer_id: str) -> dict:
    """
    L2 fraud cases K=15.
    Returns pattern_mult (1.1–2.1), coldstart_adj, network_adj, age_adj, citations.
    """
    try:
        query_vec = encode_features_for_l2(feature_snapshot)
        result    = query_by_vector(COLLECTIONS['L2'], query_vec, n_results=15)

        metadatas = result['metadatas'][0] if result['metadatas'] else []
        distances = result['distances'][0] if result['distances'] else []

        if not metadatas:
            _log(f"L2 K=0 retrieved | customer={customer_id} — using defaults")
            return _l2_defaults()

        _log(f"L2 K={len(metadatas)} retrieved | customer={customer_id}")

        # ── pattern_mult: similarity-weighted average of confirmed_risk_score / 100 ──
        sim_total      = 0.0
        weighted_risk  = 0.0
        mule_probs     = []
        cold_adj_vals  = []
        age_adj_vals   = []
        citations      = []

        for meta, dist in zip(metadatas, distances):
            sim = max(0.0, 1.0 - dist)
            sim_total += sim

            risk_score = float(meta.get('confirmed_risk_score', 60))
            outcome    = meta.get('outcome', '')
            pattern    = meta.get('pattern', 'unknown')

            citations.append({
                'source':     'L2_fraud_cases',
                'id':         pattern,
                'distance':   round(dist, 4),
                'similarity': round(sim, 4),
                'outcome':    outcome,
            })

            if outcome in ('confirmed_fraud', 'confirmed_suspicious'):
                weighted_risk += risk_score * sim

            # Extract optional mult fields if present
            if 'mule_probability' in meta:
                mule_probs.append(float(meta['mule_probability']) * sim)
            if 'coldstart_risk_adj' in meta and tier == 'T1':
                cold_adj_vals.append(float(meta['coldstart_risk_adj']) * sim)
            if 'age_risk_adj' in meta and tier in ('T1', 'T2'):
                age_adj_vals.append(float(meta['age_risk_adj']) * sim)

        if sim_total > 0:
            base_risk = weighted_risk / sim_total
        else:
            base_risk = 60.0

        # pattern_mult: map base_risk 0-100 → 1.1-2.1
        pattern_mult = 1.1 + (base_risk / 100.0) * 1.0
        pattern_mult = max(1.1, min(2.1, pattern_mult))

        # coldstart_adj: +8 to +14 for T1, else 0
        if tier == 'T1' and cold_adj_vals:
            coldstart_adj = sum(cold_adj_vals) / sim_total
            coldstart_adj = max(8.0, min(14.0, coldstart_adj))
        elif tier == 'T1':
            coldstart_adj = _DEFAULT_COLDSTART_ADJ
        else:
            coldstart_adj = 0.0

        # network_adj: mule_probability weighted average
        if mule_probs:
            network_adj = sum(mule_probs) / sim_total
        else:
            network_adj = _DEFAULT_NETWORK_ADJ

        # age_adj
        if age_adj_vals:
            age_adj = sum(age_adj_vals) / sim_total
        else:
            age_adj = _DEFAULT_AGE_ADJ

        return {
            'pattern_mult':  round(pattern_mult, 4),
            'coldstart_adj': round(coldstart_adj, 2),
            'network_adj':   round(network_adj, 4),
            'age_adj':       round(age_adj, 2),
            'citations':     citations,
        }

    except Exception as e:
        _log(f"L2 retrieval error: {e}. Using defaults.")
        return _l2_defaults()


def _retrieve_l1(data: dict) -> dict:
    """
    L1 regulatory K=3 per query.
    Returns regulatory_adj, CTR/STR thresholds, citations.
    """
    try:
        citations      = []
        regulatory_adj = 0.0
        ctr_single     = None
        ctr_aggregate  = None

        # Run three targeted L1 queries
        for query_str in [_L1_CTR_QUERY, _L1_STR_QUERY, _L1_REGULATORY_QUERY]:
            result    = query_by_text(COLLECTIONS['L1'], query_str, n_results=3)
            docs      = result['documents'][0] if result['documents'] else []
            dists     = result['distances'][0] if result['distances'] else []
            metas     = result['metadatas'][0] if result['metadatas'] else []

            for doc, dist, meta in zip(docs, dists, metas):
                rule_type = meta.get('rule_type', '')
                severity  = meta.get('severity', 'MEDIUM')

                citations.append({
                    'source':    'L1_regulatory',
                    'id':        rule_type,
                    'distance':  round(dist, 4),
                    'severity':  severity,
                })

                if dist > 0.5:    # not relevant enough
                    continue

                # Extract live thresholds from metadata
                if 'ctr_threshold' in meta and ctr_single is None:
                    try:
                        ctr_single = float(meta['ctr_threshold'])
                    except (ValueError, TypeError):
                        pass
                if 'ctr_aggregate_threshold' in meta and ctr_aggregate is None:
                    try:
                        ctr_aggregate = float(meta['ctr_aggregate_threshold'])
                    except (ValueError, TypeError):
                        pass

                # Accumulate regulatory risk adjustment
                if severity == 'CRITICAL':
                    regulatory_adj += 20
                elif severity == 'HIGH':
                    regulatory_adj += 15
                elif severity == 'MEDIUM':
                    regulatory_adj += 8

        # Cap adjustment and apply fallbacks for thresholds if L1 returned nothing
        regulatory_adj = min(40.0, regulatory_adj)

        if ctr_single is None:
            _log(
                f"WARN: L1 did not return ctr_threshold — "
                f"using fallback {_DEFAULT_CTR_SINGLE:,.0f}"
            )
            ctr_single = _DEFAULT_CTR_SINGLE

        if ctr_aggregate is None:
            ctr_aggregate = _DEFAULT_CTR_AGGREGATE

        _log(
            f"L1 retrieved | regulatory_adj={regulatory_adj:+.1f} | "
            f"ctr_single={ctr_single:,.0f} | ctr_aggregate={ctr_aggregate:,.0f}"
        )

        return {
            'regulatory_adj':          regulatory_adj,
            'ctr_single_threshold':    ctr_single,
            'ctr_aggregate_threshold': ctr_aggregate,
            'citations':               citations,
        }

    except Exception as e:
        _log(f"L1 retrieval error: {e}. Using defaults.")
        return {
            'regulatory_adj':          _DEFAULT_REGULATORY_ADJ,
            'ctr_single_threshold':    _DEFAULT_CTR_SINGLE,
            'ctr_aggregate_threshold': _DEFAULT_CTR_AGGREGATE,
            'citations':               [],
        }


def _retrieve_l3(typology_code: str, feature_snapshot: dict) -> dict:
    """
    L3 typologies: retrieve full typology document for STR evidence.
    """
    try:
        if not typology_code:
            return {'typology_doc': None, 'str_obligation': '', 'citations': []}

        # Use flag-based vector if typology code is available
        from et_service.shared_rag.encoders import encode_flags_for_l3
        # Build a simple flag list from typology code
        flag_list = [f'TYPOLOGY_{typology_code}']
        signal_vec = encode_flags_for_l3(flag_list)

        result = query_by_vector(COLLECTIONS['L3'], signal_vec, n_results=3)
        docs   = result['documents'][0] if result['documents'] else []
        dists  = result['distances'][0] if result['distances'] else []
        metas  = result['metadatas'][0] if result['metadatas'] else []

        citations = []
        best_doc  = None
        best_sim  = 0.0
        str_obligation = ''

        for doc, dist, meta in zip(docs, dists, metas):
            sim = 1.0 - dist
            typology = meta.get('typology', meta.get('typology_code', ''))
            citations.append({
                'source':    'L3_typologies',
                'id':        typology,
                'distance':  round(dist, 4),
                'similarity': round(sim, 4),
            })

            if sim > best_sim:
                best_sim  = sim
                best_doc  = {
                    'typology_code':     typology,
                    'description':       meta.get('description', doc),
                    'decisive_signals':  meta.get('decisive_signals', ''),
                    'regulatory_obligation': meta.get('regulatory_obligation', ''),
                    'text':              doc,
                }
                str_obligation = meta.get('regulatory_obligation', '')

        _log(
            f"L3 typology={typology_code} | "
            f"best_sim={best_sim:.2f} | str_obligation={str_obligation}"
        )

        return {
            'typology_doc':  best_doc,
            'str_obligation': str_obligation,
            'typology_code': typology_code,
            'citations':     citations,
        }

    except Exception as e:
        _log(f"L3 retrieval error: {e}")
        return {'typology_doc': None, 'str_obligation': '', 'citations': []}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _l2_defaults() -> dict:
    return {
        'pattern_mult':  _DEFAULT_PATTERN_MULT,
        'coldstart_adj': _DEFAULT_COLDSTART_ADJ,
        'network_adj':   _DEFAULT_NETWORK_ADJ,
        'age_adj':       _DEFAULT_AGE_ADJ,
        'citations':     [],
    }


def _log(msg: str):
    print(f"[RAA][RAGLayer] {msg}")
