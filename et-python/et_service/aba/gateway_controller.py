"""
gateway_controller.py  (Module 3)
─────────────────────────────────
Determines the gateway action based on RAA verdict.

Gateway Actions:
  APPROVE               — Transaction proceeds normally
  APPROVE_AFTER_CONFIRM — Requires customer CONFIRM/NOT ME tap (15s window)
  OTP_GATE              — OTP verified before commit (score 45-50, FLAG+MFA band)
  HELD                  — Transaction held pending biometric/OTP verification
  STOPPED               — Transaction blocked, funds returned
  COVERT_HOLD           — TY-03 Structuring: silent hold, no freeze (PMLA S.12A)

[FIX] OTP is sent synchronously by payment_routes for scores ≥45 BEFORE commit.
ABA's OTP_GATE action is for audit logging only — actual OTP already sent and verified.

[FIX] Added MFA gate for FLAG verdict with score >= 45 (PDF spec Section 9).
[FIX] Added TY-03 Covert Mode branch within BLOCK — no hard block visible to customer.
[FIX] Verdict names now match RAA output (FLAG/ALERT/BLOCK not SOFT_FLAG/RESTRICT).
[FIX] MFA is suppressed for TY-03 Covert Mode (PDF spec Section 9.5).
"""

from et_service.aba.constants import (
    GATEWAY_ACTIONS,
    FLAG_MFA_MIN_SCORE,
    FLAG_MFA_MAX_SCORE,
)


def determine_gateway_action(payload: dict) -> dict:
    """
    Maps RAA verdict to gateway action.

    Args:
        payload: RAA action_package dict

    Returns:
        {
            'gateway_action':        str,   APPROVE / APPROVE_AFTER_CONFIRM / OTP_GATE /
                                            HELD / STOPPED / COVERT_HOLD
            'requires_confirmation': bool,  FLAG normal — customer taps CONFIRM/NOT ME
            'requires_otp':          bool,  FLAG+MFA — OTP required before approve
            'requires_verification': bool,  ALERT — biometric/OTP/Video KYC
            'hold_funds':            bool,  True for ALERT/BLOCK/OTP_GATE
            'block_transaction':     bool,  True for BLOCK only
            'covert_mode':           bool,  True for TY-03 only
        }
    """
    verdict  = payload.get('raa_verdict', 'ALLOW')
    score    = float(payload.get('final_raa_score', 0) or 0)
    typology = payload.get('typology_code') or ''

    result = {
        'gateway_action':        'APPROVE',
        'requires_confirmation': False,
        'requires_otp':          False,
        'requires_verification': False,
        'hold_funds':            False,
        'block_transaction':     False,
        'covert_mode':           False,
    }

    if verdict == 'ALLOW':
        # Silent approval — no customer contact
        result['gateway_action'] = 'APPROVE'

    elif verdict == 'FLAG':
        # MFA gate: score 45–50 requires OTP before approving (PDF Section 9)
        # Exception: TY-03 Covert Mode suppresses MFA to avoid alerting subject
        # (PDF Section 9.5)
        if FLAG_MFA_MIN_SCORE <= score <= FLAG_MFA_MAX_SCORE and typology != 'TY-03':
            result['gateway_action'] = 'OTP_GATE'
            result['requires_otp']   = True
            result['hold_funds']     = True
            _log(f"FLAG+MFA gate | score={score} | typology={typology or 'none'}")
        else:
            # Normal FLAG: CONFIRM/NOT ME tap, 15-second auto-approve timer
            result['gateway_action']       = 'APPROVE_AFTER_CONFIRM'
            result['requires_confirmation'] = True
            _log(f"FLAG confirm gate | score={score}")

    elif verdict == 'ALERT':
        # Transaction held — biometric → OTP → Video KYC waterfall
        result['gateway_action']       = 'HELD'
        result['requires_verification'] = True
        result['hold_funds']           = True
        _log(f"ALERT hold | score={score}")

    elif verdict == 'BLOCK':
        # TY-03 Structuring: Covert Mode — show 'technical issues', no hard block
        # Legal basis: PMLA Section 12A — records must continue (PDF Section 4.1)
        if typology == 'TY-03':
            result['gateway_action'] = 'COVERT_HOLD'
            result['covert_mode']    = True
            result['hold_funds']     = True
            _log(f"BLOCK TY-03 Covert Mode | score={score}")
        else:
            # Standard BLOCK: reject immediately, funds returned
            result['gateway_action']    = 'STOPPED'
            result['block_transaction'] = True
            result['hold_funds']        = True
            _log(f"BLOCK stopped | score={score} | typology={typology or 'none'}")

    return result


def should_trigger_mfa(verdict: str, score: float, typology: str = '') -> bool:
    """
    Returns True if MFA OTP gate should fire.

    MFA fires when:
      - Verdict is FLAG
      - Score is in the 45-50 band
      - Typology is NOT TY-03 (Covert Mode suppresses MFA)
    """
    if verdict != 'FLAG':
        return False
    if typology == 'TY-03':
        return False
    return FLAG_MFA_MIN_SCORE <= score <= FLAG_MFA_MAX_SCORE


def _log(msg: str):
    print(f"[ABA][GatewayController] {msg}")