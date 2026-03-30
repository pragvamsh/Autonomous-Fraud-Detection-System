"""
account_controller.py  (Module 5)
─────────────────────────────────
Account freeze/unfreeze and credential management.

Handles:
  - Account freeze (temp/permanent)
  - Credential reset queuing
  - OTP verification for FLAG+MFA
"""

from et_dao.aba_dao import (
    set_account_frozen,
    set_credential_reset_required,
    get_customer_contact,
)


def freeze_account(customer_id: str, alert_id: int, reason: str = None) -> dict:
    """
    Freezes customer account.
    All future transactions will be blocked until unfrozen.
    """
    set_account_frozen(
        customer_id=customer_id,
        is_frozen=True,
        frozen_by_alert_id=alert_id,
        reason=reason or 'ABA_BLOCK_VERDICT'
    )
    _log(f"Account frozen: customer_id={customer_id}, alert_id={alert_id}, reason={reason}")
    return {'frozen': True, 'customer_id': customer_id}


def unfreeze_account(customer_id: str) -> dict:
    """
    Unfreezes customer account.
    Usually done by compliance officer after investigation.
    """
    set_account_frozen(
        customer_id=customer_id,
        is_frozen=False,
    )
    _log(f"Account unfrozen: customer_id={customer_id}")
    return {'frozen': False, 'customer_id': customer_id}


def trigger_credential_reset(customer_id: str, alert_id: int) -> dict:
    """
    Marks account for mandatory credential reset on next login.
    Used for ATO (Account Takeover) typology.
    """
    set_credential_reset_required(customer_id, alert_id)
    _log(f"Credential reset required: customer_id={customer_id}, alert_id={alert_id}")
    return {'credential_reset_required': True}


def request_otp_verification(customer_id: str, alert_id: int) -> dict:
    """
    Initiates OTP verification flow for FLAG+MFA verdict.
    Uses existing OTP infrastructure with FRAUD_MFA purpose.
    """
    from et_service.otp_service import generate_otp, send_otp_email
    from et_dao.otp_dao import store_otp
    from et_service.aba.constants import OTP_PURPOSE_FRAUD_MFA

    customer = get_customer_contact(customer_id)
    if not customer:
        _log(f"ERROR: Customer not found: {customer_id}")
        return {'otp_sent': False, 'error': 'Customer not found'}

    otp = generate_otp()
    store_otp(customer_id, otp, OTP_PURPOSE_FRAUD_MFA)

    send_otp_email(
        to_email=customer['email'],
        to_name=customer['full_name'],
        otp=otp,
        purpose=OTP_PURPOSE_FRAUD_MFA  # Use consistent purpose string
    )

    _log(f"OTP sent for FRAUD_MFA: customer_id={customer_id}, alert_id={alert_id}")
    return {'otp_sent': True, 'purpose': OTP_PURPOSE_FRAUD_MFA}


def verify_fraud_mfa_otp(customer_id: str, otp: str, payment_id: str) -> dict:
    """
    Verifies OTP for FLAG+MFA transactions.
    If verified, transaction can proceed. If failed, escalates to ALERT.
    """
    from et_dao.otp_dao import verify_otp
    from et_service.aba.constants import OTP_PURPOSE_FRAUD_MFA

    is_valid = verify_otp(customer_id, otp, OTP_PURPOSE_FRAUD_MFA)

    if is_valid:
        _log(f"OTP verified: customer_id={customer_id}, payment_id={payment_id}")
        return {
            'verified': True,
            'action': 'APPROVE_TRANSACTION',
            'payment_id': payment_id,
        }
    else:
        _log(f"OTP verification FAILED: customer_id={customer_id}, payment_id={payment_id}")
        return {
            'verified': False,
            'action': 'ESCALATE_TO_ALERT',
            'payment_id': payment_id,
        }


def _log(msg: str):
    print(f"[ABA][AccountController] {msg}")
