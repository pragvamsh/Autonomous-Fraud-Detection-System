"""
tier_engine.py  (Module 3 — Build First)
─────────────────────────────────────────
Classifies a customer into T1/T2/T3/T4 using AND logic.

⚠  CRITICAL DEMOTION RULE — implemented first, checked first:
   If pra_verdict == 'CRITICAL', the customer is ALWAYS T1,
   regardless of transaction history or account age.

Tier rules (ALL conditions must be true — AND logic, not OR):
  T1 NEW:     tx_count < 15  AND  account_age_days < 14  AND  any historical fraud flag
  T2 GROWING: tx_count ≥ 15  AND  account_age_days ≥ 14  AND  zero flags ever
  T3 MATURE:  tx_count ≥ 50  AND  account_age_days ≥ 60  AND  zero flags in last 30d
  T4 VETERAN: tx_count ≥ 200 AND  account_age_days ≥ 180 AND  zero flags in last 90d

If no tier conditions are met (e.g., moderate customer with some flags), defaults to T2.
"""

from et_dao.raa_dao import get_customer_account_stats

# ── Tier score floors (applied by score_engine) ────────────────────────────────
TIER_FLOORS = {
    'T1': 25,
    'T2': 20,
    'T3': 10,
    'T4': 0,    # No floor for veterans
}

# ── Tier dimension weights: D1 Txn, D2 Behav, D3 Network, D4 Identity, D5 Temporal ──
TIER_WEIGHTS = {
    'T1': {'D1': 0.10, 'D2': 0.15, 'D3': 0.10, 'D4': 0.45, 'D5': 0.20},
    'T2': {'D1': 0.20, 'D2': 0.35, 'D3': 0.15, 'D4': 0.20, 'D5': 0.10},
    'T3': {'D1': 0.25, 'D2': 0.30, 'D3': 0.20, 'D4': 0.15, 'D5': 0.10},
    'T4': {'D1': 0.30, 'D2': 0.25, 'D3': 0.20, 'D4': 0.10, 'D5': 0.15},
}


def classify_tier(data: dict) -> str:
    """
    Main entry point. Returns 'T1', 'T2', 'T3', or 'T4'.

    data must contain at minimum:
      - customer_id (str)
      - pra_verdict (str)  ← checked first for CRITICAL demotion
    """
    pra_verdict = data.get('pra_verdict') or ''
    customer_id = data.get('customer_id', '')

    # ── CRITICAL DEMOTION — must be checked before anything else ─────────────
    if pra_verdict == 'CRITICAL':
        _log(
            f"CRITICAL DEMOTION APPLIED | customer={customer_id} | "
            f"forced T1 (pra_verdict=CRITICAL)"
        )
        return 'T1'

    # ── Fetch account stats from DB ───────────────────────────────────────────
    try:
        stats = get_customer_account_stats(customer_id)
    except Exception as e:
        _log(f"WARN — could not fetch account stats for {customer_id}: {e}. Defaulting to T1.")
        return 'T1'

    tx_count              = stats['tx_count']
    account_age_days      = stats['account_age_days']
    fraud_flag_total      = stats['fraud_flag_count_total']
    fraud_flag_30d        = stats['fraud_flag_count_30d']
    fraud_flag_90d        = stats['fraud_flag_count_90d']

    # ── T4 VETERAN (highest bar — check first to prevent false T3 assignment) ─
    if (tx_count >= 200
            and account_age_days >= 180
            and fraud_flag_90d == 0):
        tier = 'T4'

    # ── T3 MATURE ─────────────────────────────────────────────────────────────
    elif (tx_count >= 50
          and account_age_days >= 60
          and fraud_flag_30d == 0):
        tier = 'T3'

    # ── T2 GROWING ────────────────────────────────────────────────────────────
    elif (tx_count >= 15
          and account_age_days >= 14
          and fraud_flag_total == 0):
        tier = 'T2'

    # ── T1 NEW ────────────────────────────────────────────────────────────────
    elif (tx_count < 15
          and account_age_days < 14
          and fraud_flag_total > 0):
        tier = 'T1'

    # ── Fallback ──────────────────────────────────────────────────────────────
    # Customer doesn't satisfy any tier's AND conditions cleanly.
    # Default to T2 as a balanced middle ground.
    else:
        tier = 'T2'

    _log(
        f"Tier assigned | customer={customer_id} | tier={tier} | "
        f"tx={tx_count} | age={account_age_days}d | "
        f"flags(total={fraud_flag_total}, 30d={fraud_flag_30d}, 90d={fraud_flag_90d})"
    )
    return tier


def _log(msg: str):
    print(f"[RAA][TierEngine] {msg}")
