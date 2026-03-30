"""
sequence_builder.py  (pra)
───────────────────────────
Module 1 of the PRA pipeline.

Builds the (30 × 15) input matrix for the BiLSTM from MySQL.

Strategy per row (transaction):
  - If TMA already wrote a fraud_alert for this transaction:
      use the feature_snapshot stored in that row (ground truth).
  - If TMA did NOT process this transaction (it was ALLOW and skipped):
      re-extract the 15 anomaly features on the fly using
      anomaly_extractor.extract(txn).

Rows are left-padded with zeros if the customer has fewer than 30
debit transactions in history. This is the standard approach for
variable-length sequence padding in BiLSTM models.

Output shape: np.ndarray of dtype float32, shape (30, 15)
"""

import numpy as np

from et_dao.pattern_dao import get_last_n_debits, get_alert_row_by_transaction
from et_service.monitoring_agent.anomaly_extractor import extract_anomaly_features
from et_service.monitoring_agent.constants import FEATURE_NAMES
from et_service.pattern_agent.constants import SEQUENCE_LENGTH, FEATURE_DIM


def build_sequence(customer_id: str, current_alert_id: int) -> tuple[np.ndarray, int]:
    """
    Constructs the (30 × 15) input matrix for the BiLSTM.

    Parameters:
      customer_id       — the customer whose history to load
      current_alert_id  — the fraud_alert row for the triggering transaction
                          (excluded from the history to avoid data leakage)

    Returns:
      matrix         — np.ndarray shape (SEQUENCE_LENGTH, FEATURE_DIM), float32
      sequence_length— actual number of non-zero rows (≤ 30)
    """
    # Fetch last N debit transactions, ordered ASC (oldest first)
    # The current triggering transaction is included at the end
    txns = get_last_n_debits(customer_id, limit=SEQUENCE_LENGTH)

    # Initialise with zeros — padding for sequences shorter than 30
    matrix = np.zeros((SEQUENCE_LENGTH, FEATURE_DIM), dtype=np.float32)

    # Take only the last SEQUENCE_LENGTH txns to avoid overfitting on full history
    sliced_txns = txns[-SEQUENCE_LENGTH:]
    num_filled_total = len(sliced_txns)
    padding_count = SEQUENCE_LENGTH - num_filled_total

    # Fill from the bottom of the matrix (most recent at row 29)
    # so that the BiLSTM always sees the current transaction at the last step
    filled_count = 0
    for i, txn in enumerate(sliced_txns):
        row_idx = padding_count + i

        # Prefer TMA's stored feature snapshot (already normalised by TMA)
        alert_row = _safe_get_alert_row(txn['transaction_id'])
        if alert_row and alert_row.get('feature_snapshot'):
            features = _parse_feature_snapshot(alert_row['feature_snapshot'])
        else:
            # TMA did not process this txn (was ALLOW) — re-extract features
            features = _safe_extract_features(txn)

        if features is not None:
            feat_len = len(features)
            if feat_len == FEATURE_DIM:
                # Perfect match — use directly
                matrix[row_idx] = features
                filled_count += 1
            elif feat_len > FEATURE_DIM:
                # [FIX-1] TMA stores 17 features but FEATURE_DIM was 15.
                # Now FEATURE_DIM=17, so this branch handles any future mismatch.
                # Truncate to FEATURE_DIM rather than discarding the entire row.
                matrix[row_idx] = features[:FEATURE_DIM]
                filled_count += 1
            elif feat_len > 0:
                # Shorter than expected — zero-pad the tail rather than discard
                matrix[row_idx, :feat_len] = features
                filled_count += 1
            # feat_len == 0: leave as zeros (empty padding row)

    sequence_length = filled_count
    return matrix, sequence_length


# ── Helpers ────────────────────────────────────────────────────────────────────

def _safe_get_alert_row(transaction_id: str) -> dict | None:
    """Fetches the fraud_alert row for a transaction; returns None on error."""
    try:
        return get_alert_row_by_transaction(transaction_id)
    except Exception as e:
        print(f"[SequenceBuilder] WARN — could not fetch alert for txn={transaction_id}: {e}")
        return None


def _safe_extract_features(txn: dict) -> np.ndarray | None:
    """
    Re-extracts the 15 TMA anomaly features for a transaction that was
    originally ALLOWed (no stored feature_snapshot in fraud_alerts).

    TMA's extract_features() requires a customer behaviour profile
    (avg_amount, std_amount, etc.) alongside the transaction. When called
    from the PRA fallback path, that profile isn't in the txn dict.

    Strategy:
      1. Try to load the customer's behaviour profile from the DB.
      2. If unavailable (new customer / cold-start), build a minimal stub
         using only the transaction's own values so extraction doesn't crash.
         The resulting features will be less accurate but won't block the
         sequence matrix from being built — the row simply carries less signal.

    Returns None on error — the matrix row stays as zeros (zero-padding).
    """
    try:
        customer_id = txn.get('customer_id')

        # Attempt to fetch the real behaviour profile
        profile = _get_behaviour_profile(customer_id)

        if profile is None:
            # Cold-start / new customer — build a minimal stub so
            # extract_features doesn't crash on missing 'avg_amount' etc.
            amount = float(txn.get('amount', 0))
            profile = {
                'avg_amount':             amount,
                'std_amount':             0.0,
                'max_single_amount':      amount,
                'avg_daily_volume':       amount,
                'transaction_frequency':  1.0,
                'usual_hour_start':       9,
                'usual_hour_end':         18,
                'known_recipients_count': 0,
                'total_data_points':      0,
                'cold_start':             True,
                'profile_strength':       0.0,
            }

        features_dict = extract_anomaly_features(txn, profile)
        arr = np.array([features_dict.get(f, 0.0) for f in FEATURE_NAMES], dtype=np.float32)
        return arr

    except Exception as e:
        print(f"[SequenceBuilder] WARN — feature extraction failed for "
              f"txn={txn.get('transaction_id')}: {e}")
        return None


def _get_behaviour_profile(customer_id: str) -> dict | None:
    """
    Loads the customer behaviour profile from customer_behaviour_profiles.
    Returns None if not found or on DB error.
    """
    if not customer_id:
        return None
    try:
        from et_dao.monitoring_dao import get_behaviour_profile
        return get_behaviour_profile(customer_id)
    except Exception:
        pass
    # Fallback: try direct DB query
    try:
        from db import get_db_connection
        conn = get_db_connection()
        if not conn:
            return None
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT * FROM customer_behaviour_profiles WHERE customer_id = %s",
            (customer_id,)
        )
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        return row
    except Exception:
        return None


def _parse_feature_snapshot(snapshot) -> np.ndarray | None:
    """
    Converts the stored feature_snapshot into a float32 numpy array of
    length FEATURE_DIM.

    Handles all forms MySQL connector may return it as:
      - Already a Python dict  {'0': 0.3, '1': 0.1, ...}  — dict keyed by index
      - Already a Python list  [0.3, 0.1, ...]
      - JSON string            "[0.3, 0.1, ...]"
      - numpy ndarray          (if passed directly from TMA)
    """
    import json
    try:
        if isinstance(snapshot, np.ndarray):
            return snapshot.astype(np.float32)

        if isinstance(snapshot, (list, tuple)):
            arr = np.array(snapshot, dtype=np.float32)
            # Always return the array - build_sequence handles truncation/padding
            return arr

        # Dict — could be keyed by feature names or by string index
        if isinstance(snapshot, dict):
            # Try feature-name-keyed dict first (canonical format from TMA)
            if all(f in snapshot for f in FEATURE_NAMES):
                arr = np.array(
                    [float(snapshot[f]) for f in FEATURE_NAMES],
                    dtype=np.float32,
                )
                return arr
            # Fallback: string-index-keyed dict e.g. {"0": 0.31, ..., "14": 0.05}
            try:
                arr = np.array(
                    [float(snapshot[str(i)]) for i in range(FEATURE_DIM)],
                    dtype=np.float32,
                )
                return arr
            except (KeyError, ValueError):
                # Last resort: values() in insertion order
                vals = list(snapshot.values())
                if len(vals) == FEATURE_DIM:
                    return np.array(vals, dtype=np.float32)
                print(f"[SequenceBuilder] WARN — feature_snapshot dict has wrong length {len(vals)}")
                return None

        # JSON string (older rows or non-connector paths)
        if isinstance(snapshot, str):
            parsed = json.loads(snapshot)
            # Recurse once to handle the parsed form
            return _parse_feature_snapshot(parsed)

        print(f"[SequenceBuilder] WARN — feature_snapshot has unexpected type {type(snapshot)}")
        return None

    except Exception as e:
        print(f"[SequenceBuilder] WARN — could not parse feature_snapshot: {e}")
        return None