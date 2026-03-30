"""
score_engine.py  (Module 6)
────────────────────────────
Final score computation for the RAA.

Implements the exact 60/40 fusion formula from the spec:
  final_score = (Score_B * 0.60) + (Score_A_adjusted * 0.40)

followed by PRA pattern bonus and override floors in strict priority order:
  1. CRITICAL floor (min 60) — checked FIRST regardless of tier
  2. T1 floor (min 25)
  3. T2 floor (min 20)
  4. T3 floor (min 10)
  5. T4: no floor

Verdict mapping (0-100 → ALLOW / FLAG / ALERT / BLOCK):
  0-25   → ALLOW
  26-50  → FLAG    [was SOFT_FLAG  — renamed to match ABA vocabulary]
  51-75  → ALERT   [was RESTRICT   — renamed to match ABA vocabulary]
  76-100 → BLOCK   [was FREEZE_BLOCK — renamed to match ABA vocabulary]

[FIX] Only _score_to_verdict was changed. The score computation itself
(fuse_scores, compute_raw_danger, floors) is completely unchanged.
The old names (SOFT_FLAG / RESTRICT / FREEZE_BLOCK) did not match ABA's
routing logic which expects FLAG / ALERT / BLOCK, causing every ABA branch
to silently fall through — 0 notifications, 0 actions, 0 cases.
"""

from et_service.raa.tier_engine import TIER_FLOORS


# ── Score_B sub-components ────────────────────────────────────────────────────
def compute_raw_danger(
    amount_zscore:  float,
    recipient_flag: bool | int,
    velocity_score: float,   # transactions_last_1h / 10.0
    hour_anomaly:   bool | int,
) -> float:
    """
    Score_B: raw transaction danger, 0-100.

    Captures what just happened — dominating signal (60% of final).
    """
    # z-score contribution: cap at |z|=4 → 100
    z_contrib   = min(100.0, abs(amount_zscore) * 25.0)

    # New recipient adds risk
    recip_bonus = 30.0 if recipient_flag else 0.0

    # Velocity: number of txns in last hour × 10 (cap at 100)
    vel_contrib = min(100.0, velocity_score * 100.0)

    # Unusual hour
    hour_bonus  = 20.0 if hour_anomaly else 0.0

    raw = (0.50 * z_contrib + 0.25 * vel_contrib
           + 0.15 * recip_bonus + 0.10 * hour_bonus)
    return max(0.0, min(100.0, raw))


def fuse_scores(dims: dict, rag: dict, data: dict) -> dict:
    """
    Main entry point — fuses Score_A and Score_B into final_raa_score.

    dims : output of dimension_scorer (D1-D5, score_a)
    rag  : output of raa_rag_layer (pattern_mult, coldstart_adj, regulatory_adj …)
    data : full fraud_alerts row

    Returns:
      final_raa_score, raa_verdict, score_a (adjusted), score_b
    """
    fs          = data.get('feature_snapshot') or {}
    pra_verdict = data.get('pra_verdict') or ''
    tier        = data.get('_tier', 'T2')

    # ── Step 1: Score_B (raw transaction danger — 60% weight) ─────────────────
    score_b = compute_raw_danger(
        amount_zscore  = float(fs.get('amount_z_score', 0.0)),
        recipient_flag = bool(fs.get('is_new_recipient', False)),
        velocity_score = float(fs.get('transactions_last_1h', 0)) / 10.0,
        hour_anomaly   = bool(fs.get('is_unusual_hour', False)),
    )

    # ── Step 2: Apply RAG multipliers to Score_A (40% weight) ─────────────────
    score_a_raw     = dims.get('score_a', 0.0)
    pattern_mult    = rag.get('pattern_mult', 1.5)
    coldstart_adj   = rag.get('coldstart_adj', 0.0)
    regulatory_adj  = rag.get('regulatory_adj', 0.0)

    score_a_adjusted = score_a_raw * pattern_mult
    score_a_adjusted += coldstart_adj
    score_a_adjusted += regulatory_adj
    score_a_adjusted  = max(0.0, min(200.0, score_a_adjusted))   # allow headroom before clamp

    # ── Step 3: 60/40 fusion ──────────────────────────────────────────────────
    raw_final = (score_b * 0.60) + (score_a_adjusted * 0.40)

    # ── Step 4: PRA pattern bonus ──────────────────────────────────────────────
    urgency = float(data.get('urgency_multiplier') or 1.0)
    if urgency > 1.2:
        pattern_score = float(data.get('pattern_score') or 0)
        raw_final += pattern_score * 0.10

    # ── Step 5: Override floors — strict priority order ────────────────────────
    #  CRITICAL must be first (may affect T4 veterans)
    floor_applied = 'none'
    if pra_verdict == 'CRITICAL':
        raw_final     = max(raw_final, 60.0)
        floor_applied = 'CRITICAL (min 60)'
    elif tier == 'T1':
        raw_final     = max(raw_final, TIER_FLOORS['T1'])
        floor_applied = f'T1 (min {TIER_FLOORS["T1"]})'
    elif tier == 'T2':
        raw_final     = max(raw_final, TIER_FLOORS['T2'])
        floor_applied = f'T2 (min {TIER_FLOORS["T2"]})'
    elif tier == 'T3':
        raw_final     = max(raw_final, TIER_FLOORS['T3'])
        floor_applied = f'T3 (min {TIER_FLOORS["T3"]})'
    # T4: no floor

    # ── Step 6: Clamp to [0, 100] and map to verdict ───────────────────────────
    final_raa_score = round(max(0.0, min(100.0, raw_final)), 2)
    raa_verdict     = _score_to_verdict(final_raa_score)

    _log(
        f"Score_B={score_b:.2f} | Score_A_adj={score_a_adjusted:.2f} | "
        f"raw={raw_final:.2f} | floor:{floor_applied} | "
        f"final={final_raa_score} | verdict={raa_verdict}"
    )

    return {
        'final_raa_score': final_raa_score,
        'raa_verdict':     raa_verdict,
        'score_a':         round(score_a_adjusted, 2),
        'score_b':         round(score_b, 2),
        'floor_applied':   floor_applied,
    }


# ── Helpers ────────────────────────────────────────────────────────────────────

def _score_to_verdict(score: float) -> str:
    """
    Maps final_raa_score to ABA's verdict vocabulary.

    [FIX] Previously returned SOFT_FLAG / RESTRICT / FREEZE_BLOCK.
    ABA's entire routing tree (gateway_controller, action_executor,
    notification_engine, constants.NOTIFICATION_CHANNELS) is keyed on
    FLAG / ALERT / BLOCK. The name mismatch caused every ABA branch to
    silently miss, producing 0 notifications, 0 actions, and 0 cases.
    Only the return values changed — score bands are identical.
    """
    if score <= 25:
        return 'ALLOW'
    elif score <= 50:
        return 'FLAG'    # was SOFT_FLAG
    elif score <= 75:
        return 'ALERT'   # was RESTRICT
    else:
        return 'BLOCK'   # was FREEZE_BLOCK


def _log(msg: str):
    print(f"[RAA][ScoreEngine] {msg}")