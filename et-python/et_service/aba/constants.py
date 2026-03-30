"""
constants.py
────────────
Configuration constants for the Alert & Block Agent (ABA).

[FIX] TYPOLOGY_ACTIONS previously used short codes (ATO, APP, CNP etc.)
but RAA outputs FIU-IND TY-XX codes from L3 ChromaDB retrieval.
Both sets are now present — TY-XX codes are checked first (primary),
short codes remain as legacy fallbacks.

[FIX] HIGH_RISK_TYPOLOGIES updated to include both TY-XX and short codes.
"""

# ── Polling configuration ──────────────────────────────────────────────────────
POLL_INTERVAL_S = 0.5      # 500ms poll cycle (matching RAA)
BATCH_LIMIT     = 10       # Max packages per poll cycle

# ── Verdict thresholds ─────────────────────────────────────────────────────────
# FLAG verdict with score 45-50 triggers MFA gate instead of simple confirm
# (PDF spec Section 9: MFA OTP gate)
FLAG_MFA_MIN_SCORE = 45
FLAG_MFA_MAX_SCORE = 50

# MFA configuration (PDF spec Section 9.6)
MFA_RISK_THRESHOLD   = 45    # >= this score within FLAG band triggers OTP gate
MFA_OTP_EXPIRY_S     = 300   # OTP validity window (5 minutes)
MFA_SESSION_TTL_S    = 900   # mfa_required key lifetime (15 minutes)
MFA_MAX_ATTEMPTS     = 3     # Failures before soft-lock
MFA_LOCKOUT_S        = 1800  # Soft-lock duration (30 minutes)
MFA_OTP_LENGTH       = 6     # OTP digit count

# ── Gateway actions mapped from verdicts ───────────────────────────────────────
GATEWAY_ACTIONS = {
    'ALLOW':  'APPROVE',
    'FLAG':   'APPROVE_AFTER_CONFIRM',   # or OTP_GATE if score 45-50
    'ALERT':  'HELD',
    'BLOCK':  'STOPPED',
}

# ── Typology-specific action codes ─────────────────────────────────────────────
# Executed when verdict is BLOCK.
#
# [FIX] Added FIU-IND TY-XX codes (primary — from RAA L3 retrieval).
# Legacy short codes kept as fallback for backwards compatibility.
#
# Covert Mode (TY-03): no account freeze — PMLA S.12A evidence preservation.
# MFA is suppressed in Covert Mode (PDF Section 9.5).
TYPOLOGY_ACTIONS = {
    # ── FIU-IND TY-XX codes (from RAA L3 ChromaDB retrieval) ──────────────────
    'TY-19': ['FREEZE_ACCOUNT', 'RESET_CREDENTIALS'],       # Account Takeover
    'TY-12': ['FREEZE_ACCOUNT'],                             # Probe-then-Strike
    'TY-31': ['SOFT_FREEZE', 'FLAG_MULE_RECIPIENT'],        # Mule Account
    'TY-03': ['COVERT_MODE'],                               # Structuring (NO freeze)
    'TY-07': ['SOFT_FREEZE'],                               # Slow Bleed
    'TY-11': ['COVERT_HOLD', 'STR_PRIORITY'],               # Trade-based ML
    'TY-18': ['FULL_FREEZE', 'STR_PRIORITY'],               # Rapid fund movement
    'TY-21': ['COVERT_HOLD', 'STR_PRIORITY'],               # Smurfing

    # ── Legacy short codes (fallback) ─────────────────────────────────────────
    'ATO':   ['FREEZE_ACCOUNT', 'RESET_CREDENTIALS'],
    'APP':   ['HOLD_FUNDS', 'FLAG_MULE_RECIPIENT'],
    'CNP':   ['BLOCK_CARD', 'REISSUE_CARD'],
    'MON':   ['COVERT_HOLD', 'STR_PRIORITY'],
    'SYN':   ['FULL_FREEZE', 'SAR_FILING'],
    'INS':   ['IMMEDIATE_ESCALATION', 'HR_NOTIFY'],
}

# High-risk typologies that qualify for P1 priority fraud cases
# [FIX] Added TY-XX equivalents alongside short codes
HIGH_RISK_TYPOLOGIES = {
    'TY-19', 'TY-18', 'TY-21',   # FIU-IND codes
    'ATO', 'SYN', 'INS', 'MON',  # legacy codes
}

# ── Fraud case priority thresholds ─────────────────────────────────────────────
P1_MIN_SCORE    = 90   # P1 Critical: score 90+, BLOCK + high-risk typology
BLOCK_MIN_SCORE = 76   # P2 High: score 76-89, BLOCK standard

# ── Timeouts ───────────────────────────────────────────────────────────────────
OTP_TIMEOUT_S                  = 60    # 60 seconds for OTP verification
CONFIRM_TIMEOUT_S              = 15    # 15 seconds for FLAG confirmation
ALERT_VERIFICATION_TIMEOUT_S   = 300   # 5 minutes for ALERT biometric/OTP

# ── OTP purpose for fraud MFA ──────────────────────────────────────────────────
OTP_PURPOSE_FRAUD_MFA = 'FRAUD_MFA'

# ── Notification templates ─────────────────────────────────────────────────────
NOTIFICATION_TEMPLATES = {
    'FLAG_CONFIRM':   'FRAUD_FLAG_CONFIRM',
    'FLAG_MFA':       'FRAUD_FLAG_MFA',
    'ALERT_VERIFY':   'FRAUD_ALERT_VERIFY',
    'BLOCK_NOTIFY':   'FRAUD_BLOCK_NOTIFY',
    'ACCOUNT_FROZEN': 'ACCOUNT_FROZEN_NOTIFY',
}

# ── Notification channels per verdict ──────────────────────────────────────────
# [FIX] Verdict names now match RAA output (FLAG/ALERT/BLOCK, not SOFT_FLAG etc.)
NOTIFICATION_CHANNELS = {
    'ALLOW':  [],                     # Silent log only — no customer contact
    'FLAG':   ['PUSH'],               # Push notification with CONFIRM/NOT ME
    'ALERT':  ['PUSH', 'EMAIL'],      # Push + email — transaction held
    'BLOCK':  ['PUSH', 'EMAIL', 'SMS'], # All channels — transaction stopped
}