"""
pra_rag_layer.py  (pra)
─────────────────────────
Module 3 of the PRA pipeline — 3-layer RAG retrieval.

This is NOT a wrapper around the shared TMA RAG. The PRA's RAG is
different in three ways:

  1. L3 query vector is the 128-d BiLSTM hidden state projected to 256-d
     (pattern library uses 256-d SignalSequenceEncoder space).
  2. L2 query vector is the same 128-d hidden state, passed directly
     to the FraudFeatureEncoder space (both are 128-d).
  3. L1 uses the same active-flag NL query as TMA, but is conditioned
     on the PRA's detected typology, not TMA's.

Retrieval steps and their effect on pattern_score:
  ┌──────┬─────────────────────────────┬─────────────────────────────────────┐
  │ Step │ Layer                       │ Effect                              │
  ├──────┼─────────────────────────────┼─────────────────────────────────────┤
  │ 4a   │ L3 Pattern Library (K=1)    │ urgency_multiplier, reg_action      │
  │      │ query: hidden_state→proj    │ final_score × urgency if sim>0.60   │
  ├──────┼─────────────────────────────┼─────────────────────────────────────┤
  │ 4b   │ L2 Fraud Cases (K=5)        │ precedent_adj                       │
  │      │ query: hidden_state (128-d) │ sim-weighted avg confirmed severity │
  ├──────┼─────────────────────────────┼─────────────────────────────────────┤
  │ 4c   │ L1 Regulatory (K=3)         │ reg_adj (additive)                  │
  │      │ query: active flags NL      │ citations forwarded to RAA           │
  └──────┴─────────────────────────────┴─────────────────────────────────────┘
"""

from __future__ import annotations
import asyncio
import numpy as np

from et_service.shared_rag.vector_store import (
    query_by_vector, query_by_text, COLLECTIONS
)
from et_service.pattern_agent.constants import (
    RAG_L3_K, RAG_L2_K, RAG_L1_K,
    RAG_L3_SIM_THRESHOLD,
    RAG_L3_HIDDEN_PROJ_DIM,
    RAG_L2_ENCODER_DIM,
)


# ── Low-level search helpers ───────────────────────────────────────────────────

def _search_vector(collection_name: str, vec: np.ndarray, k: int):
    """
    Queries a vector collection and returns (records, sims).
    records — list of metadata dicts
    sims    — np.ndarray of cosine similarities (1 - ChromaDB cosine distance)
    """
    result = query_by_vector(collection_name, vec.tolist(), n_results=k)
    metadatas = result.get('metadatas', [[]])[0]
    distances = result.get('distances', [[]])[0]
    sims      = np.array([1.0 - d for d in distances], dtype=np.float32)
    return metadatas, sims


def _search_text(collection_name: str, text: str, k: int):
    """
    Queries a text collection (L1) and returns (records, sims).
    Chroma's SentenceTransformer embedding function handles the text encoding.
    """
    result = query_by_text(collection_name, text, n_results=k)
    metadatas = result.get('metadatas', [[]])[0]
    distances = result.get('distances', [[]])[0]
    sims      = np.array([1.0 - d for d in distances], dtype=np.float32)
    return metadatas, sims


# ── Public entry point ─────────────────────────────────────────────────────────

def retrieve_pra_rag(
    hidden_state:      np.ndarray,
    anomaly_features:  dict,
    anomaly_flag_labels: list[str],
) -> dict:
    """
    Runs all three RAG retrieval steps for the PRA.

    Parameters:
      hidden_state       — (128,) BiLSTM last-step hidden vector
      anomaly_features   — 15-feature dict from TMA anomaly extractor
      anomaly_flag_labels— active flag names (e.g. ['is_near_threshold', ...])

    Returns dict with:
      typology_code      : str | None
      urgency_multiplier : float          (default 1.0 if L3 miss)
      regulatory_action  : str | None
      precedent_adj      : float          (L2 contribution to pattern score)
      reg_adj            : float          (L1 contribution to pattern score)
      reg_citations      : list[dict]     (forwarded to RAA as pra_reg_citations)
      l3_similarity      : float
      rag_reasoning      : str
    """
    try:
        # Run L3 and L2 in parallel (asyncio), then L1 sequentially
        l3_result, l2_result = asyncio.run(_parallel_l3_l2(hidden_state))
    except RuntimeError:
        # Already inside an event loop (e.g. Flask with async)
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            l3_fut = pool.submit(_step_l3, hidden_state)
            l2_fut = pool.submit(_step_l2, hidden_state)
            l3_result = l3_fut.result()
            l2_result = l2_fut.result()

    l1_result = _step_l1(anomaly_flag_labels)

    # ── Assemble reasoning ────────────────────────────────────────────
    reasoning_parts = []

    if l3_result['typology_code']:
        reasoning_parts.append(
            f"L3 match: typology={l3_result['typology_code']} "
            f"(sim={l3_result['l3_similarity']:.2f}, "
            f"urgency×{l3_result['urgency_multiplier']:.2f})."
        )
    else:
        reasoning_parts.append("L3: no typology match above threshold.")

    reasoning_parts.append(
        f"L2: precedent_adj={l2_result['precedent_adj']:.1f} "
        f"from {l2_result['n_cases']} case(s)."
    )
    reasoning_parts.append(
        f"L1: reg_adj={l1_result['reg_adj']:.1f} "
        f"from {len(l1_result['citations'])} citation(s)."
    )

    return {
        'typology_code':      l3_result['typology_code'],
        'urgency_multiplier': l3_result['urgency_multiplier'],
        'regulatory_action':  l3_result['regulatory_action'],
        'precedent_adj':      l2_result['precedent_adj'],
        'reg_adj':            l1_result['reg_adj'],
        'reg_citations':      l1_result['citations'],
        'l3_similarity':      l3_result['l3_similarity'],
        'rag_reasoning':      ' '.join(reasoning_parts),
    }


# ── Async parallel wrapper ─────────────────────────────────────────────────────

async def _parallel_l3_l2(hidden_state: np.ndarray):
    """Runs L3 and L2 concurrently to stay within the 3ms budget."""
    loop = asyncio.get_event_loop()
    l3 = loop.run_in_executor(None, _step_l3, hidden_state)
    l2 = loop.run_in_executor(None, _step_l2, hidden_state)
    return await asyncio.gather(l3, l2)


# ── Step 4a: L3 Pattern Library ────────────────────────────────────────────────

def _step_l3(hidden_state: np.ndarray) -> dict:
    """
    Queries the L3 pattern library using the BiLSTM hidden state.

    The hidden state is 128-d (BiLSTM output); L3 embeddings were stored
    using SignalSequenceEncoder which produces 256-d vectors. We project
    the 128-d hidden to 256-d with a learned linear projection stored
    alongside the BiLSTM model weights.

    Returns: typology_code, urgency_multiplier, regulatory_action,
             l3_similarity
    """
    defaults = {
        'typology_code':      None,
        'urgency_multiplier': 1.0,
        'regulatory_action':  None,
        'l3_similarity':      0.0,
    }

    try:
        query_vec = _project_hidden_to_l3(hidden_state)   # (256,)
        records, sims = _search_vector(COLLECTIONS['L3'], query_vec, RAG_L3_K)

        if not records or len(sims) == 0:
            return defaults

        best     = records[0]
        best_sim = float(sims[0])

        defaults['l3_similarity'] = best_sim
        defaults['typology_code'] = best.get('fiu_ind_code') or best.get('typology_code')

        if best_sim >= RAG_L3_SIM_THRESHOLD:
            defaults['urgency_multiplier'] = float(best.get('urgency_multiplier', 1.0))
            defaults['regulatory_action']  = (
                best.get('regulatory_action') or best.get('recommended_action')
            )
        else:
            # Typology identified but similarity below threshold — no multiplier
            defaults['urgency_multiplier'] = 1.0

        return defaults

    except Exception as e:
        print(f"[PRA-RAG] L3 error: {e}")
        return defaults


def _project_hidden_to_l3(hidden: np.ndarray) -> np.ndarray:
    """
    Projects the 128-d BiLSTM hidden state for L3 search.

    [FIX-2-CORRECTED] Target dimension reverted from 384 to 256.
    The L3 ChromaDB collection is populated by ingest_patterns.py using
    encode_flags_for_l3(), which generates 256-d SignalSequenceEncoder vectors.
    Previous [FIX-2] incorrectly assumed L3 used 384-d SentenceTransformer.

    Strategy:
      1. Try learned linear projection stored in bilstm_v1.pt under key
         'l3_projection' — shape (RAG_L3_HIDDEN_PROJ_DIM, 128) = (256, 128).
         This gives the best retrieval quality.
      2. Fall back to zero-padding 128 → 256. Less accurate but functional —
         the first 128 dimensions carry the BiLSTM signal; the rest are 0.
         Retrieval still works, just with lower precision.
    """
    import torch
    from et_service.pattern_agent.constants import BILSTM_MODEL_PATH, RAG_L3_HIDDEN_PROJ_DIM

    target_dim = RAG_L3_HIDDEN_PROJ_DIM  # 256

    try:
        state = torch.load(BILSTM_MODEL_PATH, map_location='cpu')
        if 'l3_projection' in state:
            W = state['l3_projection'].numpy()   # expected shape: (256, 128)
            if W.shape == (target_dim, len(hidden)):
                return (W @ hidden).astype(np.float32)
            # Shape mismatch — projection was trained for wrong target dim
            print(f"[PRA-RAG] l3_projection shape {W.shape} doesn't match "
                  f"({target_dim}, {len(hidden)}) — using zero-pad fallback")
    except Exception:
        pass

    # Zero-pad fallback: 128 → 256
    projected = np.zeros(target_dim, dtype=np.float32)
    projected[:len(hidden)] = hidden
    return projected


# ── Step 4b: L2 Fraud Cases ────────────────────────────────────────────────────

def _step_l2(hidden_state: np.ndarray) -> dict:
    """
    Queries L2 fraud cases using the BiLSTM hidden state directly.

    The FraudFeatureEncoder and BiLSTM both produce 128-d representations,
    so no projection is needed — they share the same embedding space.

    precedent_adj = similarity-weighted average of confirmed_pattern_severity
    from the K=5 most similar fraud cases.
    """
    defaults = {'precedent_adj': 0.0, 'n_cases': 0}

    try:
        # hidden_state is already 128-d, matching FraudFeatureEncoder space
        records, sims = _search_vector(COLLECTIONS['L2'], hidden_state.astype(np.float32), RAG_L2_K)

        if not records or len(sims) == 0:
            return defaults

        # Similarity-weighted average severity
        total_weight = sims.sum()
        if total_weight < 1e-9:
            return defaults

        weighted_severity = sum(
            float(r.get('confirmed_pattern_severity', 0)) * float(s)
            for r, s in zip(records, sims)
        )
        precedent_adj = weighted_severity / total_weight

        return {
            'precedent_adj': round(float(precedent_adj), 2),
            'n_cases':       len(records),
        }

    except Exception as e:
        print(f"[PRA-RAG] L2 error: {e}")
        return defaults


# ── Step 4c: L1 Regulatory ────────────────────────────────────────────────────

def _step_l1(flag_labels: list[str]) -> dict:
    """
    Queries L1 regulatory documents using a natural-language query
    constructed from the active anomaly flag labels.

    reg_adj  = sum of risk_adjustment_value from top-K regulatory chunks.
    Citations are stored in pra_reg_citations and forwarded to RAA.
    """
    defaults = {'reg_adj': 0.0, 'citations': []}

    if not flag_labels:
        return defaults

    try:
        query_text = _build_regulatory_query(flag_labels)
        records, sims = _search_text(COLLECTIONS['L1'], query_text, RAG_L1_K)

        if not records:
            return defaults

        reg_adj    = sum(float(r.get('risk_adjustment_value', 0)) for r in records)
        citations  = [
            {
                'pmla_section': r.get('source', ''),
                'text':         r.get('text', '')[:200],   # truncated for DB storage
                'sim':          round(float(s), 3),
            }
            for r, s in zip(records, sims)
        ]

        return {
            'reg_adj':   round(float(reg_adj), 2),
            'citations': citations,
        }

    except Exception as e:
        print(f"[PRA-RAG] L1 error: {e}")
        return defaults


def _build_regulatory_query(flag_labels: list[str]) -> str:
    """
    Maps active flag labels to regulatory language matching PMLA/RBI text.
    Mirrors TMA's approach but is conditioned on PRA-level flag context.
    """
    FLAG_TO_PHRASE = {
        'is_near_threshold':     'structuring near reporting threshold PMLA Rs 10 lakh',
        'is_round_number':       'round number transaction structuring smurfing',
        'is_velocity_burst':     'velocity burst unusual transaction frequency EWS-04 RBI',
        'is_late_night':         'late night transaction monitoring unusual hour',
        'is_new_recipient':      'new beneficiary enhanced due diligence RBI KYC',
        'is_large_amount':       'large value transfer suspicious transaction STR',
        'high_z_new_recipient':  'high value transfer new recipient enhanced monitoring',
        'late_night_new_recipient': 'late night new beneficiary account takeover',
        'exceeds_daily_volume':  'exceeds daily volume unusual debit pattern',
        'is_unusual_hour':       'unusual hour transaction outside normal banking hours',
    }
    parts = [FLAG_TO_PHRASE[f] for f in flag_labels if f in FLAG_TO_PHRASE]
    if not parts:
        return 'suspicious transaction pattern sequence fraud typology'
    return ' | '.join(parts)