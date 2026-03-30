"""
anomaly_extractor.py
────────────────────
Derives 15 anomaly signals from a transaction + behavioural profile.

These features feed:
  - ml_layer.py   → Isolation Forest feature vector (exact FEATURE_NAMES order)
  - rag_layer.py  → query text builders for ChromaDB retrieval

Key fixes vs original:
  [FIX-1] current_hour replaced by hour_sin + hour_cos (cyclical encoding).
          is_late_night removed (redundant). Count stays at exactly 15.
  [FIX-2] Regulatory threshold bands imported from constants.py — no magic numbers.
  [FIX-3] Unusual-hour check handles midnight wrap-around correctly.
  [FIX-4] Velocity count comment clarifies +1 intent to prevent "fixes".
  [FIX-5] Removed stale llm_layer.py reference.
"""

import math
from datetime import datetime

from et_dao.monitoring_dao import (
    get_transactions_last_n_hours,
    get_known_recipients,
    get_daily_volume,
)
from et_service.monitoring_agent.constants import (
    STRUCTURING_BANDS,
    LARGE_AMOUNT_MULTIPLIER,
    DAILY_VOLUME_SPIKE_MULTIPLIER,
    LATE_NIGHT_START,
    LATE_NIGHT_END,
    VELOCITY_BURST_THRESHOLD,
    HIGH_DAILY_FREQUENCY_THRESHOLD,
    Z_SCORE_HIGH,
    Z_SCORE_EXTREME,
    ROUND_NUMBER_MIN_AMOUNT,
    ROUND_NUMBER_MODULUS,
)


def extract_anomaly_features(transaction: dict, profile: dict) -> dict:
    """
    Derives the 15 anomaly feature signals from the current transaction
    and the customer's behavioural profile.

    Returns a flat dict keyed by FEATURE_NAMES (see constants.py).
    All binary signals are int (0 or 1) for numpy compatibility.
    """
    customer_id = transaction.get('sender_customer_id') or transaction['customer_id']
    amount      = float(transaction['amount'])
    now         = datetime.now()
    current_hour = now.hour

    # ── Pull velocity data from DB ─────────────────────────────────────
    txns_last_1h        = get_transactions_last_n_hours(customer_id, hours=1)
    txns_last_24h       = get_transactions_last_n_hours(customer_id, hours=24)
    known_recipients    = get_known_recipients(customer_id)
    daily_volume_so_far = get_daily_volume(customer_id)
    recipient_account   = transaction.get('recipient_account', '')

    # ── Amount anomaly features ────────────────────────────────────────
    avg   = profile['avg_amount']
    std   = profile['std_amount']
    max_h = profile['max_single_amount']

    # Z-score: guard against std=0 (single prior transaction)
    amount_z_score = round(
        (amount - avg) / std if std > 0 else (amount - avg) / max(avg, 1),
        3
    )

    # Ratio to personal historical maximum
    amount_vs_max = round(amount / max_h if max_h > 0 else 1.0, 3)

    # Does today's total (including this txn) exceed N× the 90-day avg?
    exceeds_daily_volume = int(
        (daily_volume_so_far + amount) >
        (profile['avg_daily_volume'] * DAILY_VOLUME_SPIKE_MULTIPLIER)
    )

    is_large_amount  = int(amount > avg * LARGE_AMOUNT_MULTIPLIER)

    # Structuring: amount inside any regulatory threshold band
    is_near_threshold = int(
        any(lo <= amount <= hi for lo, hi in STRUCTURING_BANDS)
    )

    is_round_number = int(
        (amount % ROUND_NUMBER_MODULUS == 0) and amount >= ROUND_NUMBER_MIN_AMOUNT
    )

    # ── [FIX-1] Cyclical hour encoding ────────────────────────────────
    # Raw current_hour (0-23) is a LINEAR feature in sklearn — hour 23 and
    # hour 0 would appear maximally distant despite being 1 minute apart.
    # Sin/cos encoding makes the hour space circular and continuous.
    hour_sin = round(math.sin(2 * math.pi * current_hour / 24), 6)
    hour_cos = round(math.cos(2 * math.pi * current_hour / 24), 6)

    # is_late_night is computed for FLAG LABELS only (not a model feature).
    is_late_night_bool = LATE_NIGHT_START <= current_hour <= LATE_NIGHT_END

    # ── [FIX-3] Unusual hour — wrap-around safe comparison ────────────
    h_start = profile['usual_hour_start']
    h_end   = profile['usual_hour_end']

    if h_start <= h_end:
        # Normal window e.g. 9 → 21
        in_usual_window = h_start <= current_hour <= h_end
    else:
        # Wrap-around window e.g. 22 → 5 (night shift customer)
        in_usual_window = current_hour >= h_start or current_hour <= h_end

    is_unusual_hour = int(not in_usual_window)

    # ── Recipient features ─────────────────────────────────────────────
    is_new_recipient = int(recipient_account not in known_recipients)

    # ── Velocity features ──────────────────────────────────────────────
    # +1 includes the current transaction (not yet committed to the DB
    # query window, but it IS happening now).
    transactions_last_1h  = len(txns_last_1h) + 1
    transactions_last_24h = len(txns_last_24h) + 1

    is_velocity_burst = int(transactions_last_1h > VELOCITY_BURST_THRESHOLD)

    # ── Composite signals ──────────────────────────────────────────────
    high_z_new_recipient     = int(amount_z_score > Z_SCORE_HIGH and is_new_recipient)
    late_night_new_recipient = int(is_late_night_bool and is_new_recipient)

    return {
        # ── 15 model features (order matches FEATURE_NAMES in constants.py) ──
        'amount_z_score':           amount_z_score,
        'amount_vs_max':            amount_vs_max,
        'exceeds_daily_volume':     exceeds_daily_volume,
        'is_large_amount':          is_large_amount,
        'is_near_threshold':        is_near_threshold,
        'is_round_number':          is_round_number,
        'is_unusual_hour':          is_unusual_hour,
        'hour_sin':                 hour_sin,
        'hour_cos':                 hour_cos,
        'is_new_recipient':         is_new_recipient,
        'transactions_last_1h':     transactions_last_1h,
        'transactions_last_24h':    transactions_last_24h,
        'is_velocity_burst':        is_velocity_burst,
        'high_z_new_recipient':     high_z_new_recipient,
        'late_night_new_recipient': late_night_new_recipient,

        # ── Ancillary fields (not model features, used by encoders/labels) ──
        'current_hour':   current_hour,      # Raw hour for human-readable labels
        'is_late_night':  int(is_late_night_bool),  # For flag labels and regulatory query
    }


def get_anomaly_flag_labels(features: dict) -> list[str]:
    """
    Converts the feature dict into a human-readable list of triggered
    anomaly labels.

    Used by the RAG layer to construct ChromaDB query strings and
    stored in fraud_alerts.anomaly_flags as a JSON array.

    Note: uses ancillary fields (current_hour, is_late_night) that are
    in the features dict but are NOT model features.
    """
    flags = []
    hour = features.get('current_hour', 0)

    z = features['amount_z_score']
    if z > Z_SCORE_EXTREME:
        flags.append(f"EXTREME_AMOUNT_DEVIATION (z={z})")
    elif z > Z_SCORE_HIGH:
        flags.append(f"HIGH_AMOUNT_DEVIATION (z={z})")

    if features['amount_vs_max'] > 1.0:
        flags.append(f"EXCEEDS_PERSONAL_MAX (ratio={features['amount_vs_max']})")

    if features['exceeds_daily_volume']:
        flags.append("EXCEEDS_DAILY_VOLUME_THRESHOLD")

    if features['is_large_amount']:
        flags.append("LARGE_AMOUNT_10X_AVERAGE")

    if features['is_near_threshold']:
        flags.append("STRUCTURING_SIGNAL_NEAR_THRESHOLD")

    if features['is_new_recipient']:
        flags.append("NEW_RECIPIENT_NEVER_TRANSACTED")

    if features['is_unusual_hour']:
        flags.append(f"UNUSUAL_HOUR (hour={hour:02d}:00)")

    if features.get('is_late_night'):
        flags.append(f"LATE_NIGHT_TRANSACTION (hour={hour:02d}:00)")

    if features['is_velocity_burst']:
        flags.append(
            f"VELOCITY_BURST ({features['transactions_last_1h']} txns in 1h)"
        )

    if features['transactions_last_24h'] > HIGH_DAILY_FREQUENCY_THRESHOLD:
        flags.append(
            f"HIGH_DAILY_FREQUENCY ({features['transactions_last_24h']} txns today)"
        )

    if features['high_z_new_recipient']:
        flags.append("HIGH_RISK_COMPOSITE: large_amount + new_recipient")

    if features['late_night_new_recipient']:
        flags.append("HIGH_RISK_COMPOSITE: late_night + new_recipient")

    if features['is_round_number']:
        flags.append("ROUND_NUMBER_AMOUNT")

    return flags