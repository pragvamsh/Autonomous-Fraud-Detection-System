"""
notification_engine.py  (Module 4)
───────────────────────────────────
Sends customer notifications via push, email, SMS.

Notifications are queued in notification_queue table for async delivery.
This module handles the queueing logic; actual delivery is done by a
separate notification service (not part of ABA).

[FIX] _build_notification_payload: FLAG push notification now shows
specific context from investigation_note instead of generic message.
CONFIRM/NOT ME buttons added to FLAG push payload.

[FIX] Added covert mode notification path: TY-03 Covert Mode shows
'technical issues temporarily unavailable' — no fraud language that
would alert the subject (PDF spec Section 4.1 / PMLA S.12A).

[FIX] Verdict names updated to FLAG/ALERT/BLOCK (was SOFT_FLAG/RESTRICT/FREEZE_BLOCK).
"""

from et_dao.aba_dao import save_notification, get_customer_contact
from et_service.aba.constants import (
    NOTIFICATION_TEMPLATES,
    NOTIFICATION_CHANNELS,
)


def dispatch_notifications(payload: dict, verdict: str) -> dict:
    """
    Dispatches appropriate notifications based on verdict.

    ALLOW  → no notification (silent log only)
    FLAG   → PUSH with CONFIRM/NOT ME buttons
    ALERT  → PUSH + EMAIL with verification request
    BLOCK  → PUSH + EMAIL + SMS (or covert message for TY-03)

    Args:
        payload: RAA action package payload
        verdict: RAA verdict (ALLOW, FLAG, ALERT, BLOCK)

    Returns:
        {
            'notifications_queued': int,
            'channels':             list[str],
            'notification_ids':     list[str],
        }
    """
    customer_id = payload.get('customer_id')
    alert_id    = payload.get('alert_id')
    typology    = payload.get('typology_code') or ''
    covert_mode = payload.get('covert_mode', False)

    # TY-03 Covert Mode: override to single covert push notification
    # Do NOT use fraud language — must not alert the subject
    if covert_mode or typology == 'TY-03':
        return _dispatch_covert_notification(payload)

    channels = NOTIFICATION_CHANNELS.get(verdict, [])

    if not channels:
        # ALLOW — silent log, no customer contact
        return {
            'notifications_queued': 0,
            'channels':             [],
            'notification_ids':     [],
        }

    customer = get_customer_contact(customer_id)
    if not customer:
        _log(f"ERROR: Customer not found: {customer_id}")
        return {
            'notifications_queued': 0,
            'channels':             [],
            'notification_ids':     [],
            'error':                'Customer not found',
        }

    notification_ids = []

    for channel in channels:
        template             = _get_template_for_verdict(verdict, channel)
        notification_payload = _build_notification_payload(payload, channel, verdict)

        notification = {
            'customer_id': customer_id,
            'alert_id':    alert_id,
            'channel':     channel,
            'template':    template,
            'payload':     notification_payload,
            'status':      'PENDING',
        }

        try:
            notification_id = save_notification(notification)
            notification_ids.append(notification_id)
            _log(f"Notification queued | {channel} → customer={customer_id} | id={notification_id}")
        except Exception as e:
            _log(f"ERROR queueing {channel} notification: {e}")

    return {
        'notifications_queued': len(notification_ids),
        'channels':             channels,
        'notification_ids':     notification_ids,
    }


def _dispatch_covert_notification(payload: dict) -> dict:
    """
    TY-03 Structuring — Covert Mode notification.

    Shows 'technical issues' message. NO fraud language. NO account freeze
    language. Monitoring continues silently.
    Legal basis: PMLA Section 12A.
    """
    customer_id = payload.get('customer_id')
    alert_id    = payload.get('alert_id')

    notification = {
        'customer_id': customer_id,
        'alert_id':    alert_id,
        'channel':     'PUSH',
        'template':    'COVERT_TECHNICAL_ISSUE',
        'payload': {
            'type':  'TECHNICAL_ISSUE',
            'title': 'Service Temporarily Unavailable',
            'body':  'This transaction is temporarily unavailable due to a technical issue. Please try again shortly.',
        },
        'status': 'PENDING',
    }

    try:
        nid = save_notification(notification)
        _log(f"Covert notification queued | TY-03 | customer={customer_id} | id={nid}")
        return {
            'notifications_queued': 1,
            'channels':             ['PUSH'],
            'notification_ids':     [nid],
            'covert_mode':          True,
        }
    except Exception as e:
        _log(f"ERROR queueing covert notification: {e}")
        return {'notifications_queued': 0, 'channels': [], 'notification_ids': []}


def queue_flag_confirmation_notification(payload: dict) -> str:
    """
    Queues FLAG confirmation push notification.
    Returns notification_id.
    """
    customer_id = payload.get('customer_id')
    alert_id    = payload.get('alert_id')
    amount      = payload.get('amount', '?')

    notification = {
        'customer_id': customer_id,
        'alert_id':    alert_id,
        'channel':     'PUSH',
        'template':    NOTIFICATION_TEMPLATES['FLAG_CONFIRM'],
        'payload': {
            'type':             'FRAUD_CONFIRM',
            'title':            'Confirm Transaction',
            'body':             f'Did you authorize a transaction of Rs {amount}?',
            'amount':           amount,
            'transaction_id':   payload.get('transaction_id'),
            'buttons':          ['CONFIRM', 'NOT_ME'],
            'timeout_seconds':  15,
        },
        'status': 'PENDING',
    }

    notification_id = save_notification(notification)
    _log(f"FLAG confirmation notification queued: {notification_id}")
    return notification_id


def queue_block_notifications(payload: dict) -> list:
    """
    Queues all BLOCK notifications (push, email, SMS).
    Returns list of notification_ids.
    """
    customer_id = payload.get('customer_id')
    alert_id    = payload.get('alert_id')
    customer    = get_customer_contact(customer_id)
    amount      = payload.get('amount', '?')

    notification_ids = []

    push = {
        'customer_id': customer_id,
        'alert_id':    alert_id,
        'channel':     'PUSH',
        'template':    NOTIFICATION_TEMPLATES['BLOCK_NOTIFY'],
        'payload': {
            'type':            'FRAUD_BLOCK',
            'title':           'Transaction Blocked',
            'body':            'A suspicious transaction has been blocked for your security.',
            'amount':          amount,
            'support_contact': '1800-XXX-XXXX',
        },
        'status': 'PENDING',
    }
    notification_ids.append(save_notification(push))

    email = {
        'customer_id': customer_id,
        'alert_id':    alert_id,
        'channel':     'EMAIL',
        'template':    NOTIFICATION_TEMPLATES['BLOCK_NOTIFY'],
        'payload': {
            'type':               'FRAUD_BLOCK',
            'to_email':           customer['email'] if customer else None,
            'to_name':            customer['full_name'] if customer else None,
            'subject':            'Transaction Blocked — Action Required',
            'amount':             amount,
            'investigation_note': payload.get('investigation_note'),
            'support_contact':    '1800-XXX-XXXX',
        },
        'status': 'PENDING',
    }
    notification_ids.append(save_notification(email))

    sms = {
        'customer_id': customer_id,
        'alert_id':    alert_id,
        'channel':     'SMS',
        'template':    NOTIFICATION_TEMPLATES['BLOCK_NOTIFY'],
        'payload': {
            'type':    'FRAUD_BLOCK',
            'phone':   customer['phone_number'] if customer else None,
            'message': (
                f'ALERT: EagleTrust blocked a suspicious transaction of Rs {amount}. '
                f'Contact support: 1800-XXX-XXXX immediately.'
            ),
        },
        'status': 'PENDING',
    }
    notification_ids.append(save_notification(sms))

    _log(f"BLOCK notifications queued: {len(notification_ids)} for customer_id={customer_id}")
    return notification_ids


def queue_account_frozen_notification(customer_id: str, alert_id: int, reason: str) -> str:
    """Queues email notification that account has been frozen."""
    notification = {
        'customer_id': customer_id,
        'alert_id':    alert_id,
        'channel':     'EMAIL',
        'template':    NOTIFICATION_TEMPLATES['ACCOUNT_FROZEN'],
        'payload': {
            'type':            'ACCOUNT_FROZEN',
            'subject':         'Account Frozen — Security Alert',
            'reason':          reason,
            'support_contact': '1800-XXX-XXXX',
        },
        'status': 'PENDING',
    }

    notification_id = save_notification(notification)
    _log(f"Account frozen notification queued: {notification_id}")
    return notification_id


# ── Internal helpers ───────────────────────────────────────────────────────────

def _get_template_for_verdict(verdict: str, channel: str) -> str:
    """Returns the template code for the given verdict and channel."""
    mapping = {
        'FLAG':  NOTIFICATION_TEMPLATES['FLAG_CONFIRM'],
        'ALERT': NOTIFICATION_TEMPLATES['ALERT_VERIFY'],
        'BLOCK': NOTIFICATION_TEMPLATES['BLOCK_NOTIFY'],
    }
    return mapping.get(verdict, 'GENERIC_NOTIFICATION')


def _build_notification_payload(payload: dict, channel: str, verdict: str) -> dict:
    """
    Builds channel-specific notification payload.

    [FIX] FLAG push now includes CONFIRM/NOT ME buttons and shows specific
    context from investigation_note rather than a generic message.
    Amount is now included in all channels for customer recognition.
    """
    amount = payload.get('amount', '?')
    note   = payload.get('investigation_note', '')

    base_payload = {
        'transaction_id': payload.get('transaction_id'),
        'amount':         amount,
        'verdict':        verdict,
        'score':          payload.get('final_raa_score'),
    }

    if channel == 'PUSH':
        if verdict == 'FLAG':
            # Specific context to help customer recognise their own transaction
            body = (
                note[:120] if note
                else f'Unusual activity detected on a transaction of Rs {amount}. Was this you?'
            )
            base_payload.update({
                'title':           'Confirm Your Transaction',
                'body':            body,
                'buttons':         ['CONFIRM', 'NOT_ME'],
                'timeout_seconds': 15,
            })
        elif verdict == 'ALERT':
            base_payload.update({
                'title': 'Security Verification Required',
                'body':  f'Please verify a transaction of Rs {amount} using biometric or OTP.',
            })
        elif verdict == 'BLOCK':
            base_payload.update({
                'title': 'Transaction Blocked',
                'body':  f'A transaction of Rs {amount} has been blocked for your security.',
            })

    elif channel == 'EMAIL':
        subjects = {
            'FLAG':  'Action Required — Confirm Your Transaction',
            'ALERT': 'Security Verification Required',
            'BLOCK': 'Transaction Blocked — Action Required',
        }
        base_payload.update({
            'subject':            subjects.get(verdict, 'Security Alert'),
            'investigation_note': note,
        })

    elif channel == 'SMS':
        messages = {
            'FLAG':  f'EagleTrust: Did you authorise Rs {amount}? Tap app to confirm. Call 1800-XXX-XXXX if not you.',
            'ALERT': f'EagleTrust: Transaction of Rs {amount} held. Open app to verify identity.',
            'BLOCK': f'EagleTrust: Suspicious transaction of Rs {amount} blocked. Call 1800-XXX-XXXX now.',
        }
        base_payload['message'] = messages.get(verdict, 'Security alert on your account. Check app.')

    return base_payload


def _log(msg: str):
    print(f"[ABA][NotificationEngine] {msg}")