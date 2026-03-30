"""
profile_builder.py
──────────────────
Builds and caches the 90-day behavioural baseline for each customer.

Key fixes vs original:
  [FIX-1] get_or_build_profile() checks profile freshness (max 4 hours)
          instead of rebuilding from scratch on every transaction.
          The original rebuilt on every call, which meant 90 days of
          transactions were re-aggregated per payment — too expensive.
  [FIX-2] Cold start defaults raised to realistic median retail banking
          values (avg=Rs 5,000, std=Rs 3,000, max=Rs 10,000).
          The original Rs 500 avg caused z-scores of 15+ for any normal
          first transaction above Rs 800, triggering BLOCK on new customers.
  [FIX-3] _compute_usual_hours returns (start, end) that may wrap midnight
          (e.g. start=22, end=5 for night-shift customers).
          The anomaly extractor now handles wrap-around comparison correctly.
  [FIX-4] All threshold constants imported from constants.py.
"""

import math
from datetime import datetime, timedelta   # datetime: _is_fresh comparison; timedelta: cache age

from et_dao.monitoring_dao import (
    get_recent_transactions,
    get_known_recipients,
    upsert_behaviour_profile,
    get_behaviour_profile,
)
from et_service.monitoring_agent.constants import (
    COLD_START_THRESHOLD,
    HISTORY_WINDOW_DAYS,
    PROFILE_CACHE_MAX_AGE_HOURS,
    COLD_START_AVG_AMOUNT,
    COLD_START_STD_AMOUNT,
    COLD_START_MAX_AMOUNT,
    COLD_START_AVG_DAILY_VOLUME,
    COLD_START_HOUR_START,
    COLD_START_HOUR_END,
)


def get_or_build_profile(customer_id: str) -> dict:
    """
    Returns the cached profile if it is fresh (< PROFILE_CACHE_MAX_AGE_HOURS).
    Builds a new profile from scratch if missing or stale.

    [FIX-1] The original always rebuilt — this hit the DB and recomputed
    statistics for 90 days of transactions on every single payment.
    """
    existing = get_behaviour_profile(customer_id)
    if existing and _is_fresh(existing):
        return existing
    return build_profile(customer_id)


def build_profile(customer_id: str) -> dict:
    """
    Builds (or rebuilds) the behavioural baseline from the last
    HISTORY_WINDOW_DAYS of DEBIT transactions.

    Persists the result via upsert_behaviour_profile() for caching.
    """
    transactions    = get_recent_transactions(customer_id, days=HISTORY_WINDOW_DAYS)
    known_recipients = get_known_recipients(customer_id)
    n = len(transactions)

    if n < COLD_START_THRESHOLD:
        profile = _cold_start_profile(customer_id, n, known_recipients)
    else:
        profile = _compute_profile(customer_id, transactions, known_recipients)

    upsert_behaviour_profile(customer_id, profile)
    return profile


# ── Internal helpers ───────────────────────────────────────────────────────────

def _is_fresh(profile: dict) -> bool:
    """
    Returns True if the profile was computed less than
    PROFILE_CACHE_MAX_AGE_HOURS ago.

    Uses 'last_updated' — the exact column name returned by
    monitoring_dao.get_behaviour_profile(). The DB manages this
    field automatically via ON UPDATE CURRENT_TIMESTAMP.
    """
    last_updated = profile.get('last_updated')   # ← DAO returns this key
    if not last_updated:
        return False
    try:
        if isinstance(last_updated, str):
            last_updated = datetime.fromisoformat(last_updated)
        age = datetime.now() - last_updated
        return age < timedelta(hours=PROFILE_CACHE_MAX_AGE_HOURS)
    except (ValueError, TypeError):
        return False


def _compute_profile(customer_id: str,
                     transactions: list[dict],
                     known_recipients: set) -> dict:
    amounts = [float(t['amount']) for t in transactions]
    n       = len(amounts)

    avg_amount = sum(amounts) / n
    variance   = sum((a - avg_amount) ** 2 for a in amounts) / n
    std_amount = math.sqrt(variance)
    max_single = max(amounts)

    # Daily volume — group by calendar date
    daily_totals: dict[str, float] = {}
    for t in transactions:
        day_key = t['created_at'].strftime('%Y-%m-%d')
        daily_totals[day_key] = daily_totals.get(day_key, 0.0) + float(t['amount'])

    avg_daily_volume = (
        sum(daily_totals.values()) / len(daily_totals) if daily_totals else 0.0
    )

    # Transaction frequency (per day over the history window)
    if n >= 2:
        earliest  = min(t['created_at'] for t in transactions)
        latest    = max(t['created_at'] for t in transactions)
        days_span = max((latest - earliest).days, 1)
        txn_freq  = round(n / days_span, 4)
    else:
        txn_freq = 0.0

    # [FIX-3] Usual hours — may wrap midnight for night-shift customers
    hours = [t['created_at'].hour for t in transactions]
    usual_hour_start, usual_hour_end = _compute_usual_hours(hours)

    profile_strength = round(min(n / 50, 1.0), 3)

    return {
        'customer_id':            customer_id,
        'avg_amount':             round(avg_amount, 2),
        'std_amount':             round(std_amount, 2),
        'max_single_amount':      round(max_single, 2),
        'avg_daily_volume':       round(avg_daily_volume, 2),
        'transaction_frequency':  txn_freq,
        'usual_hour_start':       usual_hour_start,
        'usual_hour_end':         usual_hour_end,
        'known_recipients_count': len(known_recipients),
        'total_data_points':      n,
        'cold_start':             0,
        'profile_strength':       profile_strength,
        # Note: last_updated is managed by MySQL ON UPDATE CURRENT_TIMESTAMP
        # The DAO returns it; we do not set it here.
    }


def _cold_start_profile(customer_id: str,
                         n: int,
                         known_recipients: set) -> dict:
    """
    [FIX-2] Synthetic baseline for customers with < COLD_START_THRESHOLD
    transactions. Calibrated to median Indian retail banking customer.

    The original Rs 500 avg caused z-scores of 15+ on first transactions
    above Rs 800, producing BLOCK verdicts for entirely new customers.
    """
    return {
        'customer_id':            customer_id,
        'avg_amount':             COLD_START_AVG_AMOUNT,
        'std_amount':             COLD_START_STD_AMOUNT,
        'max_single_amount':      COLD_START_MAX_AMOUNT,
        'avg_daily_volume':       COLD_START_AVG_DAILY_VOLUME,
        'transaction_frequency':  0.5,
        'usual_hour_start':       COLD_START_HOUR_START,
        'usual_hour_end':         COLD_START_HOUR_END,
        'known_recipients_count': len(known_recipients),
        'total_data_points':      n,
        'cold_start':             1,
        'profile_strength':       round(n / (COLD_START_THRESHOLD * 10), 3),
        # last_updated managed by MySQL ON UPDATE CURRENT_TIMESTAMP
    }


def _compute_usual_hours(hours: list[int]) -> tuple[int, int]:
    """
    Finds the contiguous (possibly wrap-around) hour window covering
    80% of the customer's transactions.

    Returns (start_hour, end_hour) where start_hour > end_hour indicates
    a wrap-around window (e.g. 22 → 5 for a night-shift customer).

    The anomaly extractor handles wrap-around correctly:
      if start <= end: normal window  (start <= hour <= end)
      if start >  end: wrap window    (hour >= start OR hour <= end)
    """
    if not hours:
        return COLD_START_HOUR_START, COLD_START_HOUR_END

    hour_counts = [0] * 24
    for h in hours:
        hour_counts[h % 24] += 1

    total        = len(hours)
    target_count = int(total * 0.80)

    best_start = 0
    best_end   = 23
    best_span  = 24

    for start in range(24):
        covered = 0
        for span in range(1, 25):
            hour_idx = (start + span - 1) % 24
            covered += hour_counts[hour_idx]
            if covered >= target_count:
                if span < best_span:
                    best_span  = span
                    best_start = start
                    best_end   = hour_idx
                break

    return best_start, best_end