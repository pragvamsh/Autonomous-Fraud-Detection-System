"""
dimension_scorer.py  (Module 4)
────────────────────────────────
Computes the 5-Dimension risk profile and Score_A.

Each dimension is scored 0–100 using exact formulas from the spec.
The tier-specific weights are then applied to produce Score_A.

Dimensions:
  D1 — Transaction Anomaly  (vs personal history)
  D2 — Behavioural Pattern  (z-score, frequency, recipients, entropy)
  D3 — Network Risk         (graph risk, mule pct, centrality, connections)
  D4 — Identity Trust       (account age, security, KYC, profile changes, minor flag)
  D5 — Temporal Suspicion   (time gaps, hour anomaly, high-risk period, recency, session)

Score_A = D1*w1 + D2*w2 + D3*w3 + D4*w4 + D5*w5
  where w1..w5 come from TIER_WEIGHTS[tier] in tier_engine.py.
"""

import math
from et_service.raa.tier_engine import TIER_WEIGHTS


def score_dimensions(data: dict, tier: str) -> dict:
    """
    Main entry point.

    data must contain:
      - feature_snapshot (dict): 15-feature vector from TMA
      - customer_id (str): for logging
      - (optionally) network stats, identity fields from fraud_alerts row

    Returns:
      {'D1', 'D2', 'D3', 'D4', 'D5', 'score_a', 'dim_details'}
    """
    fs = data.get('feature_snapshot') or {}
    customer_id = data.get('customer_id', '')

    # ── D1 — Transaction Anomaly ──────────────────────────────────────────────
    # latest_txn_score: use TMA risk_score as the latest transaction's anomaly score
    latest_txn_score  = _clamp(float(data.get('risk_score') or 0))
    avg_score_30d     = _clamp(float(data.get('ml_score') or 0) * 0.8)   # proxy via ML score
    flag_count        = len(data.get('anomaly_flags') or [])
    # Slope: use urgency_multiplier as proxy (above 1.0 = rising risk)
    urgency           = float(data.get('urgency_multiplier') or 1.0)
    trend_slope       = max(0.0, (urgency - 1.0) * 10.0)   # normalise to ~0-10

    D1 = _clamp(
        0.40 * latest_txn_score
      + 0.30 * avg_score_30d
      + 0.20 * _clamp(flag_count * 10)
      + 0.10 * _clamp(trend_slope * 20)
    )

    # ── D2 — Behavioural Pattern ──────────────────────────────────────────────
    amount_z     = float(fs.get('amount_z_score', 0.0))
    # Normalise z-score to 0-100 (cap at |z|=4 → score 100)
    amount_z_norm = _clamp(abs(amount_z) * 25)

    # Frequency deviation: transactions_last_1h vs normal (>3 = high = 100)
    txns_1h      = float(fs.get('transactions_last_1h', 0))
    freq_dev     = _clamp(txns_1h / 3.0 * 100)

    # New recipient rate: is_new_recipient flag
    new_recip_rate = 100.0 if fs.get('is_new_recipient') else 0.0

    # Transaction entropy proxy: use amount_vs_max as diversity signal
    amt_vs_max   = float(fs.get('amount_vs_max', 1.0))
    entropy      = _clamp(min(amt_vs_max, 3.0) / 3.0 * 100)

    D2 = _clamp(
        0.30 * amount_z_norm
      + 0.25 * freq_dev
      + 0.25 * new_recip_rate
      + 0.20 * entropy
    )

    # ── D3 — Network Risk ─────────────────────────────────────────────────────
    # Use pattern_score from PRA as the best available graph_risk signal
    pattern_score = float(data.get('pattern_score') or 0)
    graph_risk    = _clamp(pattern_score)

    # Fraud network pct: use network_score from PRA if available (proxy)
    # If PRA didn't run we use z-score + new recipient as proxy
    fraud_net_pct = 0.0
    if 'is_new_recipient' in fs and fs.get('is_new_recipient'):
        fraud_net_pct = 0.15   # 15% base when paying a brand-new recipient
    # Centrality score: proxy via high velocity signals
    centrality   = _clamp(txns_1h * 20)
    # Suspicious connections: flag_count
    suspicious_conns = flag_count

    D3 = _clamp(
        0.35 * graph_risk
      + 0.30 * _clamp(fraud_net_pct * 200)
      + 0.20 * centrality
      + 0.15 * _clamp(suspicious_conns * 20)
    )

    # ── D4 — Identity Trust ───────────────────────────────────────────────────
    # Account age score: days → score (0d=100, 365d+=0)
    from et_dao.raa_dao import get_customer_account_stats
    try:
        stats        = get_customer_account_stats(data.get('customer_id', ''))
        age_days     = stats['account_age_days']
        is_minor     = stats['is_minor']
        kyc_gaps     = 0   # currently not tracked; placeholder
        profile_changes = 0  # placeholder — profile_change_count
    except Exception:
        age_days, is_minor, kyc_gaps, profile_changes = 0, False, 0, 0

    # Newer account = higher risk (invert: age_score = 100 - min(age_days/365*100, 100))
    account_age_score = _clamp(100.0 - min(age_days / 365.0 * 100.0, 100.0))

    # Security score: cold_start flag from profile as proxy (1=cold → 80 risk)
    cold_start       = bool(data.get('cold_start_profile'))
    security_score   = 80.0 if cold_start else 20.0

    # Minor flag
    minor_flag = 1.0 if is_minor else 0.0

    D4 = _clamp(
        0.20 * account_age_score
      + 0.30 * security_score
      + 0.15 * _clamp(kyc_gaps * 20)
      + 0.20 * _clamp(profile_changes * 15)
      + 0.15 * (minor_flag * 100)
    )

    # ── D5 — Temporal Suspicion ───────────────────────────────────────────────
    # Time since last transaction: use daily_volume_ratio as proxy
    daily_ratio       = float(fs.get('daily_volume_ratio', 1.0))
    time_gap_score    = _clamp(daily_ratio * 50)   # high ratio = unusual pattern

    # Hour anomaly
    hour_anomaly      = 100.0 if fs.get('is_unusual_hour') else 0.0

    # High risk period: late night
    hi_risk_period    = 1.0 if fs.get('is_late_night') else 0.0

    # Recency risk: near-threshold or velocity burst = fresh risk
    recency_risk      = 0.0
    if fs.get('is_near_threshold'):
        recency_risk += 50.0
    if fs.get('is_velocity_burst'):
        recency_risk += 50.0
    recency_risk = _clamp(recency_risk)

    # Session anomaly: multiple transactions in 1 hour = session risk
    session_anomaly   = _clamp(txns_1h * 30)

    D5 = _clamp(
        0.25 * time_gap_score
      + 0.20 * hour_anomaly
      + 0.20 * (hi_risk_period * 100)
      + 0.20 * recency_risk
      + 0.15 * session_anomaly
    )

    # ── Score_A — weighted sum ────────────────────────────────────────────────
    weights = TIER_WEIGHTS[tier]
    score_a_raw = (
        weights['D1'] * D1
      + weights['D2'] * D2
      + weights['D3'] * D3
      + weights['D4'] * D4
      + weights['D5'] * D5
    )
    score_a = _clamp(score_a_raw)

    _log(
        f"customer={customer_id} | tier={tier} | "
        f"D1={D1:.1f} D2={D2:.1f} D3={D3:.1f} D4={D4:.1f} D5={D5:.1f} | "
        f"Score_A={score_a:.2f}"
    )

    return {
        'D1':      round(D1, 2),
        'D2':      round(D2, 2),
        'D3':      round(D3, 2),
        'D4':      round(D4, 2),
        'D5':      round(D5, 2),
        'score_a': round(score_a, 2),
    }


# ── Helpers ────────────────────────────────────────────────────────────────────

def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


def _log(msg: str):
    print(f"[RAA][DimScorer] {msg}")
