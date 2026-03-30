"""
action_executor.py  (Module 2)
──────────────────────────────
Dispatches verdict-specific actions based on RAA output.

Each verdict triggers a different action set:
  ALLOW    → silent_log()
  FLAG     → push_notification() + confirm_wait()
  FLAG+MFA → action audit only (OTP already sent and verified by payment_routes)
  ALERT    → push_notification() + email_notification() + verification_request()
  BLOCK    → stop_transaction() + typology_actions() + compliance_notify()

[FIX] OTP is sent synchronously by payment_routes for scores ≥45 BEFORE commit.
FLAG+MFA actions here are for audit logging only — OTP gate already handled synchronously.

[FIX] Verdict names corrected from SOFT_FLAG/RESTRICT/FREEZE_BLOCK to
FLAG/ALERT/BLOCK matching RAA's score_engine output after the vocabulary fix.

[FIX] _handle_alert: removed duplicate HOLD_TRANSACTION action (gateway already
handles the hold). Added correct notification actions.

[FIX] _handle_block typology loop: added SOFT_FREEZE action handler.

[FIX] Added covert_mode flag to result for ABA audit logging.
"""

from et_service.aba.constants import (
    TYPOLOGY_ACTIONS,
    FLAG_MFA_MIN_SCORE,
    FLAG_MFA_MAX_SCORE,
)


def execute_verdict_actions(payload: dict, gateway_result: dict) -> dict:
    """
    Executes all actions for the given verdict.

    Args:
        payload:        RAA action package payload
        gateway_result: Result from gateway_controller.determine_gateway_action()

    Returns:
        {
            'actions_executed': list[str],
            'account_frozen':   bool,
            'notification_sent': bool,
            'case_created':     bool,
            'str_queued':       bool,
            'ctr_filed':        bool,
            'covert_mode':      bool,
        }
    """
    verdict  = payload.get('raa_verdict', 'ALLOW')
    typology = payload.get('typology_code') or ''
    score    = float(payload.get('final_raa_score', 0) or 0)

    result = {
        'actions_executed':  [],
        'account_frozen':    False,
        'notification_sent': False,
        'case_created':      False,
        'str_queued':        False,
        'ctr_filed':         False,
        'covert_mode':       False,
    }

    if verdict == 'ALLOW':
        result['actions_executed'].extend(_handle_allow(payload))

    elif verdict == 'FLAG':
        # MFA sub-band (score 45-50) triggers OTP gate, not simple confirm
        if FLAG_MFA_MIN_SCORE <= score <= FLAG_MFA_MAX_SCORE:
            result['actions_executed'].extend(_handle_flag_mfa(payload))
        else:
            result['actions_executed'].extend(_handle_flag(payload))
        result['notification_sent'] = True

    elif verdict == 'ALERT':
        result['actions_executed'].extend(_handle_alert(payload))
        result['notification_sent'] = True

    elif verdict == 'BLOCK':
        actions, frozen, covert = _handle_block(payload, typology)
        result['actions_executed'].extend(actions)
        result['account_frozen']    = frozen
        result['covert_mode']       = covert
        result['notification_sent'] = True
        result['case_created']      = True

        # Regulatory flags passed through from RAA
        if payload.get('str_required'):
            result['str_queued'] = True
        if payload.get('ctr_flag'):
            result['ctr_filed'] = True

    return result


# ── Verdict handlers ───────────────────────────────────────────────────────────

def _handle_allow(payload: dict) -> list:
    """ALLOW: Silent log only — zero customer contact."""
    _log(f"ALLOW | alert_id={payload.get('alert_id')} — silent approval")
    return ['SILENT_LOG']


def _handle_flag(payload: dict) -> list:
    """
    FLAG (score 26-44): Push notification with CONFIRM/NOT ME tap.
    Auto-approves after 15-second timer if no response.
    """
    _log(f"FLAG | alert_id={payload.get('alert_id')} — confirmation required")
    return [
        'PUSH_NOTIFICATION',
        'AWAIT_CONFIRMATION',
        'AUTO_APPROVE_TIMER_15S',
    ]


def _handle_flag_mfa(payload: dict) -> list:
    """
    FLAG+MFA (score 45-50): Audit logging for transactions that required OTP.
    OTP was sent synchronously by payment_routes and verified BEFORE commit.
    By the time ABA runs, payment is already committed and OTP verified.
    This function records the action chain for audit trail only.
    """
    _log(f"FLAG+MFA | alert_id={payload.get('alert_id')} — OTP was required (already verified)")
    return [
        'OTP_VERIFIED_PRE_COMMIT',  # Audit trail — OTP gate passed before commit
        'PUSH_NOTIFICATION',
        'AWAIT_CONFIRMATION',
    ]


def _handle_alert(payload: dict) -> list:
    """
    ALERT (score 51-75): Biometric → OTP → Video KYC waterfall.
    Transaction is already held by gateway (gateway_action=HELD).
    This fires the notification and verification request.

    [FIX] Removed duplicate HOLD_TRANSACTION — gateway handles the hold.
    Added EMAIL_NOTIFICATION which is in spec for ALERT.
    """
    _log(f"ALERT | alert_id={payload.get('alert_id')} — verification required")
    return [
        'PUSH_NOTIFICATION',
        'EMAIL_NOTIFICATION',
        'VERIFICATION_REQUEST',   # biometric first, then OTP, then Video KYC
        'TIMER_5MIN',
    ]


def _handle_block(payload: dict, typology: str) -> tuple[list, bool, bool]:
    """
    BLOCK (score 76-100): Full enforcement suite.

    Returns (actions_list, account_frozen_flag, covert_mode_flag).

    Typology drives which account action fires — see TYPOLOGY_ACTIONS in constants.py.
    TY-03 Structuring activates Covert Mode (no freeze, silent monitoring).

    [FIX] Added SOFT_FREEZE handler to typology loop.
    [FIX] Returns covert_mode flag for audit logging.
    """
    alert_id    = payload.get('alert_id')
    customer_id = payload.get('customer_id')

    _log(f"BLOCK | alert_id={alert_id} | typology={typology or 'OTHER'}")

    actions      = ['STOP_TRANSACTION']
    account_frozen = False
    covert_mode    = False

    # Typology-specific account actions
    typology_actions = TYPOLOGY_ACTIONS.get(typology, [])

    if not typology_actions:
        # Unknown typology — safe default: 24h soft freeze
        _log(f"  Unknown typology '{typology}' — applying default SOFT_FREEZE (24h)")
        typology_actions = ['SOFT_FREEZE']

    for action in typology_actions:

        if action == 'FREEZE_ACCOUNT':
            from et_service.aba.account_controller import freeze_account
            freeze_account(customer_id, alert_id, reason=f'BLOCK_{typology}')
            actions.append('FREEZE_ACCOUNT')
            account_frozen = True

        elif action == 'FULL_FREEZE':
            from et_service.aba.account_controller import freeze_account
            freeze_account(customer_id, alert_id, reason=f'FULL_FREEZE_{typology}')
            actions.append('FULL_FREEZE')
            account_frozen = True

        elif action == 'SOFT_FREEZE':
            # [FIX] Added — was missing from original typology loop
            # Soft freeze: temporary hold (24h), not permanent
            from et_service.aba.account_controller import freeze_account
            freeze_account(customer_id, alert_id, reason=f'SOFT_FREEZE_{typology}')
            actions.append('SOFT_FREEZE')
            account_frozen = True

        elif action == 'RESET_CREDENTIALS':
            from et_service.aba.account_controller import trigger_credential_reset
            trigger_credential_reset(customer_id, alert_id)
            actions.append('CREDENTIAL_RESET_QUEUED')

        elif action == 'COVERT_MODE':
            # TY-03: no freeze, 'technical issues' message, silent monitoring
            # Legal basis: PMLA Section 12A
            covert_mode = True
            actions.append('COVERT_MODE_ENABLED')
            _log(f"  TY-03 Covert Mode activated — no freeze, silent monitoring")

        elif action == 'COVERT_HOLD':
            covert_mode = True
            actions.append('COVERT_HOLD')

        elif action == 'HOLD_FUNDS':
            actions.append('HOLD_FUNDS')

        elif action == 'FLAG_MULE_RECIPIENT':
            actions.append('FLAG_MULE_RECIPIENT')

        elif action == 'BLOCK_CARD':
            actions.append('BLOCK_CARD')

        elif action == 'REISSUE_CARD':
            actions.append('REISSUE_CARD_QUEUED')

        elif action == 'STR_PRIORITY':
            actions.append('STR_PRIORITY')

        elif action == 'SAR_FILING':
            actions.append('SAR_FILING_QUEUED')

        elif action == 'IMMEDIATE_ESCALATION':
            actions.append('IMMEDIATE_ESCALATION')

        elif action == 'HR_NOTIFY':
            actions.append('HR_NOTIFY_QUEUED')

    # Notification suite (typology-aware message selected by notification_engine)
    if not covert_mode:
        # Normal BLOCK: full notification suite
        actions.extend(['PUSH_NOTIFICATION', 'EMAIL_NOTIFICATION', 'SMS_NOTIFICATION'])
    else:
        # Covert Mode: 'technical issues' message only — no fraud language
        actions.append('COVERT_NOTIFICATION')

    # Case creation always fires for BLOCK
    actions.append('CREATE_FRAUD_CASE')

    # Regulatory passthrough from RAA
    if payload.get('str_required'):
        actions.append('STR_DRAFT_QUEUED')
    if payload.get('ctr_flag'):
        actions.append('CTR_FILED')

    return actions, account_frozen, covert_mode


def _log(msg: str):
    print(f"[ABA][ActionExecutor] {msg}")