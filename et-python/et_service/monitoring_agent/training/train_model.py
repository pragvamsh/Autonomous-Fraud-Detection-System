"""
train_model.py
──────────────
Trains the Isolation Forest model for the Monitoring Agent ML Layer.

Run once from the project root:
    python et_service/monitoring_agent/training/train_model.py

Output:
    models/isolation_forest.pkl
    
    Saved as a dict:
      {
        'model':       sklearn Pipeline (StandardScaler + IsolationForest),
        'calibration': {'score_min': float, 'score_max': float, ...}
      }

Key fixes vs original:
  [FIX-1] contamination=0.01 (spec mandated — was incorrectly 0.05).
  [FIX-2] Persists score_min/score_max calibration alongside model.
          ml_layer.py uses these for correct 0-100 normalisation.
  [FIX-3] current_hour replaced by hour_sin + hour_cos everywhere.
          is_late_night removed from FEATURE_NAMES (now an ancillary field).
  [FIX-4] Composite features derived from components — never hardcoded.
  [FIX-5] All hyperparameters imported from constants.py.
"""

import os
import math
import joblib
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline

# ── Import canonical config ────────────────────────────────────────────────────
import sys
SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '..', '..', '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from et_service.monitoring_agent.constants import (
    FEATURE_NAMES,
    IF_N_ESTIMATORS,
    IF_CONTAMINATION,
    IF_RANDOM_STATE,
    IF_MAX_SAMPLES,
    LATE_NIGHT_START,
    LATE_NIGHT_END,
    VELOCITY_BURST_THRESHOLD,
    Z_SCORE_HIGH,
)

# ── Output path ────────────────────────────────────────────────────────────────
OUTPUT_DIR  = os.path.join(PROJECT_ROOT, 'models')
OUTPUT_PATH = os.path.join(OUTPUT_DIR, 'isolation_forest.pkl')

N_LEGITIMATE = 8_000
N_FRAUD      = 2_000


# ── Helper: cyclical hour encoding ────────────────────────────────────────────

def _hour_to_sin_cos(hour: int) -> tuple[float, float]:
    """Converts 0-23 hour to (sin, cos) cyclical pair."""
    angle = 2 * math.pi * hour / 24
    return math.sin(angle), math.cos(angle)


# ── Sample generators ──────────────────────────────────────────────────────────

def _make_row(
    amount_z_score: float,
    amount_vs_max: float,
    exceeds_daily_volume: int,
    is_large_amount: int,
    is_near_threshold: int,
    is_round_number: int,
    is_unusual_hour: int,
    current_hour: int,
    is_new_recipient: int,
    transactions_last_1h: int,
    transactions_last_24h: int,
) -> list:
    """
    Assembles a feature row. Derives all composite and cyclical fields
    from primitives — composites are NEVER hardcoded.
    """
    hour_sin, hour_cos = _hour_to_sin_cos(current_hour)

    is_late_night        = int(LATE_NIGHT_START <= current_hour <= LATE_NIGHT_END)
    is_velocity_burst    = int(transactions_last_1h > VELOCITY_BURST_THRESHOLD)
    high_z_new_recip     = int(amount_z_score > Z_SCORE_HIGH and is_new_recipient)
    late_night_new_recip = int(is_late_night and is_new_recipient)

    # Row order MUST match FEATURE_NAMES in constants.py
    return [
        amount_z_score,
        amount_vs_max,
        exceeds_daily_volume,
        is_large_amount,
        is_near_threshold,
        is_round_number,
        is_unusual_hour,
        hour_sin,                # [FIX-3] replaces raw current_hour
        hour_cos,                # [FIX-3]
        is_new_recipient,
        transactions_last_1h,
        transactions_last_24h,
        is_velocity_burst,       # [FIX-4] derived
        high_z_new_recip,        # [FIX-4] derived
        late_night_new_recip,    # [FIX-4] derived
    ]


def generate_legitimate_samples(n: int) -> np.ndarray:
    """
    Synthetic feature vectors representing normal legitimate transactions.
    Isolation Forest is trained on this data ONLY.
    """
    rng = np.random.default_rng(IF_RANDOM_STATE)
    rows = []

    for _ in range(n):
        z_score   = float(rng.normal(0.0, 0.8))
        vs_max    = float(rng.uniform(0.1, 0.9))
        exc_vol   = int(rng.random() < 0.05)
        large     = int(rng.random() < 0.02)
        near_thr  = int(rng.random() < 0.03)
        round_num = int(rng.random() < 0.15)
        hour      = int(rng.integers(8, 22))          # Daytime
        un_hour   = int(rng.random() < 0.10)
        new_recip = int(rng.random() < 0.15)
        txn_1h    = int(rng.integers(1, 3))
        txn_24h   = int(rng.integers(1, 6))

        rows.append(_make_row(
            z_score, vs_max, exc_vol, large, near_thr,
            round_num, un_hour, hour, new_recip, txn_1h, txn_24h
        ))

    return np.array(rows, dtype=float)


def generate_fraud_samples(n: int) -> np.ndarray:
    """
    Synthetic fraud feature vectors — used for VALIDATION ONLY.
    Covers the four primary fraud patterns.
    """
    rng = np.random.default_rng(IF_RANDOM_STATE + 1)
    rows = []

    patterns = [_probe_strike, _late_night_burst, _structuring, _account_takeover]

    for i in range(n):
        rows.append(patterns[i % len(patterns)](rng))

    return np.array(rows, dtype=float)


def _probe_strike(rng) -> list:
    """Large amount to new recipient — probe-then-strike pattern."""
    z_score   = float(rng.uniform(3.0, 8.0))
    vs_max    = float(rng.uniform(1.0, 3.0))
    exc_vol   = 1
    large     = 1
    near_thr  = 0
    round_num = int(rng.random() < 0.3)
    hour      = int(rng.integers(0, 24))
    un_hour   = int(rng.random() < 0.4)
    new_recip = 1
    txn_1h    = int(rng.integers(1, 4))
    txn_24h   = int(rng.integers(1, 8))
    return _make_row(z_score, vs_max, exc_vol, large, near_thr,
                     round_num, un_hour, hour, new_recip, txn_1h, txn_24h)


def _late_night_burst(rng) -> list:
    """Account draining — late night velocity burst."""
    z_score   = float(rng.uniform(1.5, 4.0))
    vs_max    = float(rng.uniform(0.5, 2.0))
    exc_vol   = 1
    large     = 0
    near_thr  = 0
    round_num = int(rng.random() < 0.4)
    hour      = int(rng.integers(0, 5))   # 0-4am
    un_hour   = 1
    new_recip = int(rng.random() < 0.7)
    txn_1h    = int(rng.integers(4, 10))  # Burst (> VELOCITY_BURST_THRESHOLD=3)
    txn_24h   = int(rng.integers(5, 15))
    return _make_row(z_score, vs_max, exc_vol, large, near_thr,
                     round_num, un_hour, hour, new_recip, txn_1h, txn_24h)


def _structuring(rng) -> list:
    """Amounts just below reporting thresholds — smurfing."""
    z_score   = float(rng.uniform(-0.5, 1.0))   # Looks normal per-transaction
    vs_max    = float(rng.uniform(0.3, 0.8))
    exc_vol   = 0
    large     = 0
    near_thr  = 1                                 # KEY signal
    round_num = 1
    hour      = int(rng.integers(9, 18))
    un_hour   = int(rng.random() < 0.2)
    new_recip = int(rng.random() < 0.5)
    txn_1h    = int(rng.integers(1, 4))
    txn_24h   = int(rng.integers(3, 12))
    return _make_row(z_score, vs_max, exc_vol, large, near_thr,
                     round_num, un_hour, hour, new_recip, txn_1h, txn_24h)


def _account_takeover(rng) -> list:
    """Attacker using compromised credentials — unusual hour + new recipient."""
    z_score   = float(rng.uniform(2.0, 6.0))
    vs_max    = float(rng.uniform(0.8, 2.5))
    exc_vol   = 1
    large     = 1
    near_thr  = 0
    round_num = 0
    hour      = int(rng.integers(0, 24))
    un_hour   = 1
    new_recip = 1    # Always new recipient in ATO
    txn_1h    = int(rng.integers(1, 3))
    txn_24h   = int(rng.integers(1, 5))
    return _make_row(z_score, vs_max, exc_vol, large, near_thr,
                     round_num, un_hour, hour, new_recip, txn_1h, txn_24h)


# ── Training ───────────────────────────────────────────────────────────────────

def train_and_save():
    assert len(FEATURE_NAMES) == 15, "FEATURE_NAMES must be 15 entries"

    print(f"Feature vector: {FEATURE_NAMES}")
    print(f"Contamination : {IF_CONTAMINATION}  (spec: 0.01)")
    print(f"n_estimators  : {IF_N_ESTIMATORS}")

    print("\nGenerating synthetic training data...")
    X_legit = generate_legitimate_samples(N_LEGITIMATE)
    X_fraud = generate_fraud_samples(N_FRAUD)

    assert X_legit.shape[1] == 15, f"Expected 15 features, got {X_legit.shape[1]}"
    assert X_fraud.shape[1] == 15, f"Expected 15 features, got {X_fraud.shape[1]}"
    print(f"  Legitimate : {X_legit.shape}  (training)")
    print(f"  Fraud      : {X_fraud.shape}  (validation only)")

    print("\nTraining Isolation Forest pipeline (Scaler + IF)...")
    model = Pipeline([
        ('scaler',  StandardScaler()),
        ('iforest', IsolationForest(
            n_estimators=IF_N_ESTIMATORS,
            max_samples=IF_MAX_SAMPLES,
            contamination=IF_CONTAMINATION,   # [FIX-1] spec: 0.01
            random_state=IF_RANDOM_STATE,
            n_jobs=-1,
        )),
    ])
    model.fit(X_legit)
    print("Training complete.")

    # ── [FIX-2] Compute and persist score calibration ─────────────────
    # decision_function on the TRAINING set gives the true score range.
    # ml_layer.py uses these values for normalisation — not hardcoded bounds.
    train_scores = model.decision_function(X_legit)
    calibration = {
        'score_min':  float(train_scores.min()),
        'score_max':  float(train_scores.max()),
        'score_mean': float(train_scores.mean()),
        'score_std':  float(train_scores.std()),
    }
    print(f"\nCalibration:")
    print(f"  score_min  = {calibration['score_min']:.6f}")
    print(f"  score_max  = {calibration['score_max']:.6f}")
    print(f"  score_mean = {calibration['score_mean']:.6f}")
    print(f"  score_std  = {calibration['score_std']:.6f}")

    # ── Validation ────────────────────────────────────────────────────
    legit_preds = model.predict(X_legit)
    fraud_preds = model.predict(X_fraud)

    legit_correct = int(np.sum(legit_preds == 1))
    fraud_caught  = int(np.sum(fraud_preds == -1))
    fraud_scores  = model.decision_function(X_fraud)

    print(f"\nValidation results:")
    print(f"  Legitimate correctly classified : "
          f"{legit_correct}/{N_LEGITIMATE} ({legit_correct/N_LEGITIMATE*100:.1f}%)")
    print(f"  Fraud correctly detected        : "
          f"{fraud_caught}/{N_FRAUD} ({fraud_caught/N_FRAUD*100:.1f}%)")
    print(f"  Avg score (legit) : {train_scores.mean():.4f}")
    print(f"  Avg score (fraud) : {fraud_scores.mean():.4f}")

    if fraud_caught / N_FRAUD < 0.60:
        print("\n⚠️  WARNING: Fraud detection rate below 60%. "
              "Consider adjusting contamination or training data.")

    # ── Save ──────────────────────────────────────────────────────────
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    payload = {'model': model, 'calibration': calibration}
    joblib.dump(payload, OUTPUT_PATH)
    size_kb = os.path.getsize(OUTPUT_PATH) / 1024
    print(f"\n✅ Saved to: {OUTPUT_PATH}  ({size_kb:.1f} KB)")
    print("   Contains: 'model' (Pipeline) + 'calibration' (dict)")


if __name__ == '__main__':
    train_and_save()