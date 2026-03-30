"""
ml_layer.py
───────────
ML Layer of the Monitoring Agent pipeline.

Loads the pre-trained Isolation Forest pipeline and converts the
15 anomaly features into a 0-100 risk score.

Key fixes vs original:
  [FIX-1] Score normalisation uses training-derived min/max from the
          persisted calibration dict — not hardcoded ±0.30 bounds.
  [FIX-2] Asserts loaded object is {'model': Pipeline, 'calibration': dict}.
          Prevents silent scaler-bypass if a bare model is accidentally saved.
  [FIX-3] FEATURE_ORDER imported from constants.py — single source of truth.
  [FIX-4] Fallback base score raised to FLAG floor (31) — unknown-model state
          should never silently ALLOW transactions.
  [FIX-5] Removed stale llm_layer reference.
"""

import os
import os
import joblib
from sklearn.pipeline import Pipeline

from et_service.monitoring_agent.constants import (
    FEATURE_NAMES,
    LOW_CONFIDENCE_FLAG_FLOOR,
)

# ── Model path ─────────────────────────────────────────────────────────────────
_SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_SCRIPT_DIR, '..', '..'))
_MODEL_PATH   = os.path.join(_PROJECT_ROOT, 'models', 'isolation_forest.pkl')

# ── Singleton ──────────────────────────────────────────────────────────────────
_payload = None     # {'model': Pipeline, 'calibration': dict}


def _load_payload() -> dict:
    """
    Loads the model payload from disk on first call.
    Validates structure — both 'model' and 'calibration' must be present.
    """
    global _payload
    if _payload is None:
        if not os.path.exists(_MODEL_PATH):
            raise FileNotFoundError(
                f"Isolation Forest model not found at: {_MODEL_PATH}\n"
                f"Run: python et_service/monitoring_agent/training/train_model.py"
            )

        loaded = joblib.load(_MODEL_PATH)

        # [FIX-2] Validate the saved structure
        if not isinstance(loaded, dict):
            raise TypeError(
                f"Model file must contain a dict with 'model' and 'calibration' keys. "
                f"Got {type(loaded).__name__}. Re-run train_model.py."
            )
        if 'model' not in loaded or 'calibration' not in loaded:
            raise KeyError(
                "Model payload missing 'model' or 'calibration' key. "
                "Re-run train_model.py."
            )
        if not isinstance(loaded['model'], Pipeline):
            raise TypeError(
                f"'model' must be a sklearn Pipeline (StandardScaler + IsolationForest). "
                f"Got {type(loaded['model']).__name__}. Re-run train_model.py."
            )

        _payload = loaded

    return _payload


def encode_features(anomaly_features: dict):
    """
    Converts the anomaly feature dict into a numpy array in the exact
    order FEATURE_NAMES specifies. Missing features default to 0.

    Returns shape (1, 15).
    """
    import numpy as np
    vector = [float(anomaly_features.get(f, 0)) for f in FEATURE_NAMES]
    return np.array(vector).reshape(1, -1)


def get_ml_risk_score(anomaly_features: dict) -> dict:
    """
    Main entry point for the ML Layer.

    Returns:
      ml_score    : int 0-100
      raw_score   : float (IF decision_function output)
      is_anomaly  : bool
      model_loaded: bool
    """
    try:
        payload     = _load_payload()
        model       = payload['model']
        calibration = payload['calibration']

        feature_vec = encode_features(anomaly_features)

        raw_score  = float(model.decision_function(feature_vec)[0])
        prediction = int(model.predict(feature_vec)[0])
        is_anomaly = prediction == -1

        ml_score = _raw_to_score(raw_score, calibration)

        return {
            'ml_score':    ml_score,
            'raw_score':   round(raw_score, 6),
            'is_anomaly':  is_anomaly,
            'model_loaded': True,
        }

    except (FileNotFoundError, TypeError, KeyError) as e:
        print(f"[MLLayer] Model load error: {e}")
        return _fallback_score(anomaly_features)

    except Exception as e:
        print(f"[MLLayer] Unexpected error: {e}")
        return _fallback_score(anomaly_features)


def _raw_to_score(raw: float, calibration: dict) -> int:
    """
    [FIX-1] Maps IF decision_function output to 0-100 using
    training-derived min/max — not hardcoded bounds.

    Higher raw score = more normal = lower risk.
    score_max (most normal) → 0 risk
    score_min (most anomalous) → 100 risk
    """
    s_min = calibration['score_min']
    s_max = calibration['score_max']

    score_range = s_max - s_min
    if score_range == 0:
        return 50   # Degenerate model — neutral score

    # Linear inversion: anomalous (near s_min) → high risk score
    risk = (s_max - raw) / score_range * 100
    return int(round(max(0.0, min(100.0, risk))))


def _fallback_score(anomaly_features: dict) -> dict:
    """
    Rule-based fallback when the model is unavailable.

    [FIX-4] Base score is FLAG floor (31), not 20 (ALLOW).
    In an unknown-model state, every transaction should receive
    at minimum a FLAG for human review — never silent ALLOW.
    """
    score = LOW_CONFIDENCE_FLAG_FLOOR   # 31 — FLAG minimum

    z = anomaly_features.get('amount_z_score', 0)
    if z > 3:
        score += 30
    elif z > 2:
        score += 20
    elif z > 1:
        score += 10

    if anomaly_features.get('is_new_recipient'):
        score += 15
    if anomaly_features.get('is_unusual_hour'):
        score += 10
    if anomaly_features.get('is_velocity_burst'):
        score += 15
    if anomaly_features.get('exceeds_daily_volume'):
        score += 10
    if anomaly_features.get('is_near_threshold'):
        score += 10
    if anomaly_features.get('high_z_new_recipient'):
        score += 10

    return {
        'ml_score':     min(score, 100),
        'raw_score':    0.0,
        'is_anomaly':   score >= 50,
        'model_loaded': False,
    }