"""
encoders.py  (shared_rag)
──────────────────────────
Encodes transaction data into the correct format per ChromaDB collection.
Moved from et_service/monitoring_agent/rag/encoders.py.

  L1  → natural-language text  (SentenceTransformer embeds it)
  L2  → 128-d float vector     (FraudFeatureEncoder / bootstrap projection)
  L3  → 256-d float vector     (SignalSequenceEncoder / bootstrap projection)
  L4  → 128-d float vector     (same as L2 — FraudFeatureEncoder)
"""

import math
import math

from et_service.monitoring_agent.constants import (
    FEATURE_NAMES,
    STRUCTURING_BANDS,
    CTR_THRESHOLD,
    EDD_THRESHOLD,
    KYC_THRESHOLD,
)

# ── Bootstrap projection matrices ─────────────────────────────────────────────
_RNG_SEED = 0x4A415441 # "JATA" in hex

def _make_projection_matrix(in_dim: int, out_dim: int, seed: int):
    """Creates a fixed random projection matrix (Gaussian, not orthogonalised)."""
    import numpy as np
    rng = np.random.default_rng(seed)
    M   = rng.standard_normal((in_dim, out_dim)).astype(np.float32)
    # L2-normalise columns for unit-norm projection
    norms = np.linalg.norm(M, axis=0, keepdims=True)
    norms[norms == 0] = 1.0
    return M / norms

_PROJ_15_TO_128  = _make_projection_matrix(15, 128, _RNG_SEED)
_PROJ_128_TO_256 = _make_projection_matrix(128, 256, _RNG_SEED + 1)

# Known unique signal labels (for consistent one-hot encoding of flag sets)
_ALL_FLAG_KEYS = [
    'EXTREME_AMOUNT_DEVIATION', 'HIGH_AMOUNT_DEVIATION', 'EXCEEDS_PERSONAL_MAX',
    'EXCEEDS_DAILY_VOLUME_THRESHOLD', 'LARGE_AMOUNT_10X_AVERAGE',
    'STRUCTURING_SIGNAL_NEAR_THRESHOLD', 'NEW_RECIPIENT_NEVER_TRANSACTED',
    'UNUSUAL_HOUR', 'LATE_NIGHT_TRANSACTION', 'VELOCITY_BURST',
    'HIGH_DAILY_FREQUENCY', 'HIGH_RISK_COMPOSITE: large_amount + new_recipient',
    'HIGH_RISK_COMPOSITE: late_night + new_recipient', 'ROUND_NUMBER_AMOUNT',
]
_FLAG_INDEX = {k: i for i, k in enumerate(_ALL_FLAG_KEYS)}


# ══════════════════════════════════════════════════════════════════════════════
# L2 / L4  — FraudFeatureEncoder (128-d)
# ══════════════════════════════════════════════════════════════════════════════

def encode_features_for_l2(anomaly_features: dict) -> list[float]:
    """
    Encodes the 15 anomaly features into a 128-d vector for
    L2_fraud_cases and L4_dynamic_weights queries.
    """
    import numpy as np
    global _PROJ_15_TO_128
    raw = np.array(
        [float(anomaly_features.get(f, 0.0)) for f in FEATURE_NAMES],
        dtype=np.float32,
    )
    projected = raw @ _PROJ_15_TO_128           # (128,)
    norm = np.linalg.norm(projected)
    if norm > 0:
        projected = projected / norm
    return projected.tolist()


# ══════════════════════════════════════════════════════════════════════════════
# L3  — SignalSequenceEncoder (256-d)
# ══════════════════════════════════════════════════════════════════════════════

def encode_flags_for_l3(anomaly_flag_labels: list[str]) -> list[float]:
    """
    Encodes the ordered list of active signal flags into a
    256-d vector for L3_typologies queries.
    """
    import numpy as np
    global _PROJ_15_TO_128, _PROJ_128_TO_256
    
    presence = np.zeros(len(_ALL_FLAG_KEYS), dtype=np.float32)

    n_flags = len(anomaly_flag_labels)
    for position, label in enumerate(anomaly_flag_labels):
        for key in _ALL_FLAG_KEYS:
            if label.startswith(key):
                idx = _FLAG_INDEX[key]
                weight = 1.0 - (position / max(n_flags, 1)) * 0.5
                presence[idx] = max(presence[idx], weight)
                break

    # Pad/project to 128-d then 256-d
    padded = np.zeros(15, dtype=np.float32)
    padded[:len(presence)] = presence

    v128 = padded @ _PROJ_15_TO_128           # (128,)
    v256 = v128   @ _PROJ_128_TO_256          # (256,)

    norm = np.linalg.norm(v256)
    if norm > 0:
        v256 = v256 / norm
    return v256.tolist()


# ══════════════════════════════════════════════════════════════════════════════
# L1  — Natural language text for SentenceTransformer
# ══════════════════════════════════════════════════════════════════════════════

def encode_transaction_for_regulatory(transaction: dict,
                                      anomaly_features: dict,
                                      profile: dict | None = None) -> str:
    """
    Builds a regulatory-focused query string for L1_regulatory retrieval.
    """
    amount = float(transaction.get('amount', 0))
    parts  = [f"Transaction in {_amount_band(amount)} range"]

    if amount >= CTR_THRESHOLD:
        parts.append("At or above CTR reporting threshold Rs 10,00,000")
    elif amount >= EDD_THRESHOLD:
        parts.append("Above enhanced due diligence threshold Rs 50,000")
    elif amount >= KYC_THRESHOLD:
        parts.append("Above KYC verification threshold Rs 10,000")

    if anomaly_features.get('is_near_threshold'):
        parts.append(
            "Amount just below regulatory reporting threshold — possible structuring"
        )

    if anomaly_features.get('is_velocity_burst'):
        txns = anomaly_features.get('transactions_last_1h', 0)
        parts.append(f"Rapid multiple transactions: {txns} in 1 hour")

    if anomaly_features.get('exceeds_daily_volume'):
        parts.append("Daily volume exceeds 2x 90-day average")

    if anomaly_features.get('is_new_recipient'):
        parts.append("Payment to previously unknown recipient")

    if profile:
        if profile.get('cold_start'):
            parts.append("Cold start customer — minimal transaction history")
        strength = profile.get('profile_strength', 1.0)
        if strength < 0.2:
            parts.append("Very limited behavioural baseline available")

    return ". ".join(parts) + "."


def encode_transaction_for_general_query(transaction: dict,
                                         anomaly_features: dict,
                                         anomaly_flag_labels: list[str]) -> str:
    """Builds a general natural-language description of the transaction."""
    amount = float(transaction.get('amount', 0))
    hour   = anomaly_features.get('current_hour', 0)

    parts = [f"Transaction in {_amount_band(amount)} range at {hour:02d}:00"]

    if anomaly_features.get('is_new_recipient'):
        parts.append("to new recipient (never transacted before)")
    else:
        parts.append("to known recipient")

    z = anomaly_features.get('amount_z_score', 0)
    if abs(z) > 0.5:
        parts.append(f"Amount z-score: {z:.1f}")

    if anomaly_features.get('amount_vs_max', 0) > 1.0:
        parts.append(f"Exceeds personal maximum")

    if anomaly_features.get('is_velocity_burst'):
        txns = anomaly_features.get('transactions_last_1h', 0)
        parts.append(f"Velocity burst: {txns} transactions in 1 hour")

    if anomaly_features.get('is_near_threshold'):
        parts.append("Near regulatory reporting threshold (possible structuring)")

    if anomaly_features.get('high_z_new_recipient'):
        parts.append("High-risk composite: large deviation to new recipient")

    if anomaly_features.get('late_night_new_recipient'):
        parts.append("High-risk composite: late night to new recipient")

    if anomaly_flag_labels:
        clean_flags = [label.split(' (')[0].split(':')[0].strip()
                       for label in anomaly_flag_labels[:5]]
        parts.append(f"Signals: {', '.join(clean_flags)}")

    return ". ".join(parts) + "."


# ── Internal helpers ───────────────────────────────────────────────────────────

def _amount_band(amount: float) -> str:
    """Converts a raw amount to a band string for text embedding."""
    bands = [
        (0,         1_000,     "under-1k"),
        (1_000,     5_000,     "1k-5k"),
        (5_000,     10_000,    "5k-10k"),
        (10_000,    25_000,    "10k-25k"),
        (25_000,    50_000,    "25k-50k"),
        (50_000,    100_000,   "50k-1L"),
        (100_000,   500_000,   "1L-5L"),
        (500_000,   1_000_000, "5L-10L"),
        (1_000_000, float('inf'), "above-10L"),
    ]
    for lo, hi, label in bands:
        if lo <= amount < hi:
            return label
    return "above-10L"
