"""
constants.py
────────────
Central configuration for the Monitoring Agent.

ALL magic numbers live here — never inline in business logic.
When RBI changes thresholds, update this file only.

Covers:
  - Regulatory thresholds (RBI / PMLA)
  - Feature engineering parameters
  - Model hyperparameters
  - RAG scoring caps and similarity thresholds
  - Decision tier boundaries
  - Score fusion weights
"""

# ══════════════════════════════════════════════════════════════════════════════
# REGULATORY THRESHOLDS  (RBI / PMLA 2002 / FIU-IND)
# ══════════════════════════════════════════════════════════════════════════════

# Cash Transaction Report (CTR) — must be reported to FIU-IND
CTR_THRESHOLD = 1_000_000          # Rs 10,00,000 (10 lakh)

# Enhanced Due Diligence threshold
EDD_THRESHOLD = 50_000             # Rs 50,000

# KYC re-verification trigger
KYC_THRESHOLD = 10_000             # Rs 10,000

# Structuring detection bands — amounts suspiciously close to but below thresholds
# Format: (lower_bound_inclusive, upper_bound_inclusive)
# Note: PAYMENT_MAX in payment_service.py is Rs 1,00,000 — bands above that are
# unreachable for single payments and are therefore omitted.
STRUCTURING_BANDS = [
    (9_000,  9_999),    # Just below Rs 10,000 KYC trigger
    (49_000, 49_999),   # Just below Rs 50,000 EDD trigger
    (99_000, 99_999),   # Just below Rs 1,00,000 payment cap (psychological threshold)
]

# Large transaction multiplier: flag if amount > N × customer avg
LARGE_AMOUNT_MULTIPLIER = 10

# Daily volume spike: flag if today's total > N × 90-day average daily volume
DAILY_VOLUME_SPIKE_MULTIPLIER = 2

# ══════════════════════════════════════════════════════════════════════════════
# FEATURE ENGINEERING
# ══════════════════════════════════════════════════════════════════════════════

# Late night window (inclusive) — high-risk hour range
LATE_NIGHT_START = 0    # midnight
LATE_NIGHT_END   = 5    # 5am

# Velocity burst threshold — more than this many txns in 1 hour is suspicious
VELOCITY_BURST_THRESHOLD = 3

# High daily frequency threshold
HIGH_DAILY_FREQUENCY_THRESHOLD = 10

# Z-score thresholds for flag labels
Z_SCORE_HIGH    = 2.0
Z_SCORE_EXTREME = 3.0

# Round number minimum amount to flag
ROUND_NUMBER_MIN_AMOUNT = 5_000
ROUND_NUMBER_MODULUS    = 1_000   # amount % MODULUS == 0

# ══════════════════════════════════════════════════════════════════════════════
# FEATURE VECTOR
# ══════════════════════════════════════════════════════════════════════════════

# The 15 features fed to Isolation Forest — ORDER IS CANONICAL.
# Must be identical in: anomaly_extractor.py, ml_layer.py, train_model.py
# Note: current_hour replaced by hour_sin + hour_cos (cyclical encoding).
#       is_late_night removed (redundant with cyclical encoding).
#       This keeps the count at exactly 15.
FEATURE_NAMES = [
    'amount_z_score',           # Numeric  — std deviations from personal mean
    'amount_vs_max',            # Numeric  — ratio to personal maximum
    'exceeds_daily_volume',     # Binary   — today's total > 2× 90-day avg
    'is_large_amount',          # Binary   — amount > 10× personal avg
    'is_near_threshold',        # Binary   — within structuring band
    'is_round_number',          # Binary   — round amount ≥ Rs 5k
    'is_unusual_hour',          # Binary   — outside 80% usual-hour window
    'hour_sin',                 # Numeric  — sin(2π × hour / 24) cyclical
    'hour_cos',                 # Numeric  — cos(2π × hour / 24) cyclical
    'is_new_recipient',         # Binary   — recipient never seen before
    'transactions_last_1h',     # Count    — txns in past 60 minutes
    'transactions_last_24h',    # Count    — txns in past 24 hours
    'is_velocity_burst',        # Binary   — > 3 txns in last hour
    'high_z_new_recipient',     # Binary   — composite: z>2 AND new recipient
    'late_night_new_recipient', # Binary   — composite: late night AND new recipient
]

assert len(FEATURE_NAMES) == 15, "FEATURE_NAMES must have exactly 15 entries"

# ══════════════════════════════════════════════════════════════════════════════
# ISOLATION FOREST HYPERPARAMETERS  (must match train_model.py exactly)
# ══════════════════════════════════════════════════════════════════════════════

IF_N_ESTIMATORS  = 200
IF_CONTAMINATION = 0.01    # Spec: 0.01 — expect ~1% anomalies in real traffic
IF_RANDOM_STATE  = 42
IF_MAX_SAMPLES   = 'auto'

# ══════════════════════════════════════════════════════════════════════════════
# PROFILE BUILDER
# ══════════════════════════════════════════════════════════════════════════════

COLD_START_THRESHOLD   = 10    # spec: tx_count < 10 = cold start customer
HISTORY_WINDOW_DAYS    = 90    # Days of history for behavioural baseline
PROFILE_CACHE_MAX_AGE_HOURS = 4  # Rebuild profile if older than this

# Cold start synthetic baseline — calibrated to median Indian retail banking
# customer (not Rs 500 which forces extreme z-scores on first real transactions)
COLD_START_AVG_AMOUNT       = 5_000.0
COLD_START_STD_AMOUNT       = 3_000.0
COLD_START_MAX_AMOUNT       = 10_000.0
COLD_START_AVG_DAILY_VOLUME = 5_000.0
COLD_START_HOUR_START       = 9
COLD_START_HOUR_END         = 21

# ══════════════════════════════════════════════════════════════════════════════
# CHROMADB / RAG
# ══════════════════════════════════════════════════════════════════════════════

# HNSW index parameters (spec mandated)
HNSW_SPACE            = "cosine"
HNSW_EF_SEARCH        = 50
HNSW_CONSTRUCTION_EF  = 200
HNSW_M                = 16

# Embedding dimensions per collection
DIM_L1_REGULATORY  = 384    # SentenceTransformer all-MiniLM-L6-v2
DIM_L2_FRAUD_CASES = 128    # FraudFeatureEncoder (custom / bootstrap)
DIM_L3_TYPOLOGIES  = 256    # SignalSequenceEncoder (custom / bootstrap)
DIM_L4_WEIGHTS     = 128    # Same as FraudFeatureEncoder

# Cosine DISTANCE thresholds (ChromaDB returns distance, not similarity)
# distance = 1 - cosine_similarity  →  0 = identical, 1 = orthogonal
DIST_HIGH   = 0.25    # distance ≤ 0.25  →  similarity ≥ 0.75  (strong match)
DIST_MEDIUM = 0.45    # distance ≤ 0.45  →  similarity ≥ 0.55  (moderate match)
DIST_LOW    = 0.65    # distance ≤ 0.65  →  similarity ≥ 0.35  (weak match)

# Confidence threshold for RAG fusion (spec: 0.65 cosine similarity)
# In distance terms: similarity 0.65 → distance 0.35
RAG_CONFIDENCE_THRESHOLD_DIST = 0.35   # distance ≤ this → high confidence

# Minimum L4 records before dynamic weights are used (spec: 10)
L4_MIN_RECORDS_FOR_DYNAMIC_WEIGHTS = 10
L4_QUERY_K = 20    # Spec: k=20 for L4 weight retrieval

# Default fusion weights when L4 has < 10 records (spec: ml=0.40, rag=0.60)
DEFAULT_ML_WEIGHT  = 0.40
DEFAULT_RAG_WEIGHT = 0.60

# RAG score layer caps
L2_MAX_SCORE   = 40     # Historical case similarity — anchor score
L1_MAX_ADJ     = 25     # Regulatory adjustment
L3_MAX_ADJ     = 25     # Typology adjustment
L4_MAX_ADJ     = 10     # Dynamic weight fine-tuning (±)

# ══════════════════════════════════════════════════════════════════════════════
# DECISION ENGINE
# ══════════════════════════════════════════════════════════════════════════════

# Score disagreement threshold — if |ml - rag| > this, take conservative score
DISAGREEMENT_THRESHOLD = 30

# Cold start risk penalty added to final score
COLD_START_PENALTY = 10

# Low-confidence RAG fallback floor — when confidence < threshold,
# discard RAG and floor verdict at FLAG minimum (spec requirement)
LOW_CONFIDENCE_FLAG_FLOOR = 31

# Decision tier boundaries (inclusive ranges)
# Decision tier boundaries — spec-aligned (0-25 ALLOW, 26-50 FLAG, etc.)
DECISION_TIERS = [
    (0,   25, 'ALLOW'),
    (26,  50, 'FLAG'),
    (51,  75, 'ALERT'),
    (76, 100, 'BLOCK'),
]