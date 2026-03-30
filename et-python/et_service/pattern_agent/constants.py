"""
constants.py  (pra)
────────────────────
Single source of truth for all PRA configuration.

[FIX-1] FEATURE_DIM: PDF spec says 15 but the actual TMA anomaly_extractor
        produces 17 features. Changed to 17 to match the real feature_snapshot
        length stored in fraud_alerts. Mismatching caused every stored snapshot
        to be silently rejected as "wrong length", forcing the slower fallback
        re-extraction path on every historical transaction row.

[FIX-2] RAG_L3_HIDDEN_PROJ_DIM: Reverted from 384 to 256.
        The L3 collection is ingested via et_service/shared_rag/kb_ingest/ingest_patterns.py
        which uses encode_flags_for_l3() to generate 256-d vectors (SignalSequenceEncoder).
        Previous [FIX-2] incorrectly assumed L3 used 384-d SentenceTransformer embeddings.
        Corrected to match actual ingest dimension.

[FIX-3] BILSTM_MODEL_PATH: relative path 'models/bilstm_v1.pt' resolves
        correctly from the main Flask process CWD but fails in background
        worker threads which inherit a different CWD. Changed to absolute path
        anchored at this file's location.
"""

import os as _os

# ── Pipeline ────────────────────────────────────────────────────────────────────
SEQUENCE_LENGTH          = 30    # transactions per sequence matrix
FEATURE_DIM              = 17    # [FIX-1] TMA actually produces 17 features
                                  # (was 15 per PDF spec — spec is wrong)

# ── BiLSTM architecture ────────────────────────────────────────────────────────
BILSTM_HIDDEN_SIZE       = 64    # hidden units per direction
BILSTM_OUTPUT_SIZE       = 128   # 2 × BILSTM_HIDDEN_SIZE (bidirectional)
BILSTM_DROPOUT           = 0.3
BILSTM_FC1_SIZE          = 64

# [FIX-3] Absolute path — resolves correctly from any CWD including bg threads
# This file lives at: et_service/pattern_agent/constants.py
# Model lives at:     models/bilstm_v1.pt  (project root)
BILSTM_MODEL_PATH        = _os.path.abspath(
    _os.path.join(_os.path.dirname(__file__), '..', '..', '..', 'models', 'bilstm_v1.pt')
)

# ── RAG retrieval ──────────────────────────────────────────────────────────────
RAG_L3_K                 = 1     # pattern library — top-1 typology
RAG_L2_K                 = 5     # fraud cases — top-5 precedents
RAG_L1_K                 = 3     # regulatory docs — top-3 chunks

RAG_L3_SIM_THRESHOLD     = 0.60  # minimum cosine sim for urgency multiplier
RAG_L3_HIDDEN_PROJ_DIM   = 256   # [FIX-2] Corrected: L3 uses 256-d signal vectors
RAG_L2_ENCODER_DIM       = 128   # FraudFeatureEncoder output dimension
RAG_L1_ENCODER_DIM       = 384   # SentenceEncoder output dimension

# ── Pattern score fusion (Section 4, pattern_scorer.py) ───────────────────────
BILSTM_WEIGHT            = 0.55
RAG_PATTERN_WEIGHT       = 0.45

# ── PRA verdict thresholds (inclusive upper bound) ────────────────────────────
# Maps to DE-ESCALATE / MAINTAIN / ESCALATE / CRITICAL
# RAA looks specifically for 'CRITICAL' to activate T1 + STR auto-draft
DECISION_TIERS = [
    (0,  35, 'DE-ESCALATE'),
    (36, 60, 'MAINTAIN'),
    (61, 80, 'ESCALATE'),
    (81, 100, 'CRITICAL'),
]

# ── TMA poller ─────────────────────────────────────────────────────────────────
POLLER_INTERVAL_MS       = 500   # ms between DB polls for unprocessed alerts
POLLER_MAX_WORKERS       = 4     # concurrent worker threads
POLLER_BATCH_SIZE        = 20    # alerts fetched per poll cycle

# ── Latency budget (ms) ───────────────────────────────────────────────────────
LATENCY_BILSTM_MS        = 2
LATENCY_RAG_L3_L2_MS     = 3    # L3+L2 run in parallel (asyncio)
LATENCY_RAG_L1_MS        = 2
LATENCY_SEQUENCE_FETCH_MS= 1
LATENCY_P99_BUDGET_MS    = 8    # total p99 target

# L2 fallback: reduce K when latency exceeds budget
RAG_L2_K_FALLBACK        = 3
RAG_L2_HNSW_EF_SEARCH    = 30   # increase if accuracy drops

# ── Training ───────────────────────────────────────────────────────────────────
BOOTSTRAP_SYNTHETIC_CASES = 240  # seed cases from L2 ingest_cases.py
BOOTSTRAP_EXPECTED_ACC    = 0.68 # adequate for soft escalation signal
PRODUCTION_EXPECTED_ACC   = 0.87 # after 90 days live data
RETRAIN_MIN_CASES         = 50   # trigger retrain when N new confirmed cases
RETRAIN_PRECISION_DROP    = 0.05 # trigger retrain on >5% precision drop