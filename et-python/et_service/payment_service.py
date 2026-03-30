from et_service.account_service import generate_transaction_id
from et_dao.payment_dao import (
    get_customer_by_account,
    create_pending_payment,
    commit_payment as dao_commit_payment,
    hold_payment as dao_hold_payment,
    reject_payment as dao_reject_payment,
    update_payment_status,
    get_payment_history,
    get_held_payment as dao_get_held_payment,   # new — needed by OTP verify route
)

PAYMENT_MIN = 1.00
PAYMENT_MAX = 100000.00  # Rs 1 lakh max per payment


def validate_payment(amount, recipient_account: str,
                     sender_account: str) -> list[str]:
    errors = []

    # ── Amount validation ─────────────────────────────────────────────
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        errors.append("Amount must be a valid number.")
        return errors

    if amount < PAYMENT_MIN:
        errors.append(f"Minimum payment amount is Rs {PAYMENT_MIN:.2f}.")
    if amount > PAYMENT_MAX:
        errors.append(f"Maximum payment amount is Rs {PAYMENT_MAX:,.2f}.")

    # ── Recipient validation ──────────────────────────────────────────
    if not recipient_account or not str(recipient_account).strip():
        errors.append("Recipient account number is required.")
    elif recipient_account == sender_account:
        errors.append("Cannot transfer money to your own account.")

    return errors


def process_payment(sender_customer_id: str,
                    sender_account: str,
                    recipient_account: str,
                    amount: float,
                    description: str = "Payment") -> dict:
    """
    Executes a peer-to-peer payment atomically.

    Steps:
      1. Validate recipient exists in our system
      2. Check sender has sufficient balance
      3. Debit sender + insert DEBIT transaction record
      4. Credit recipient + insert CREDIT transaction record
      5. Create payment_transactions record
      6. Return payment details for the monitoring agent to evaluate

    Returns a dict with payment_id, debit/credit transaction IDs,
    new sender balance, and recipient info — everything the
    monitoring agent needs to evaluate the transaction.
    """
    amount = float(amount)

    # ── Step 1: Verify recipient account exists ───────────────────────
    recipient = get_customer_by_account(recipient_account)
    if not recipient:
        raise ValueError("Recipient account not found. Please check the account number.")

    recipient_customer_id = recipient["customer_id"]

    # ── Step 2: Check sender balance ──────────────────────────────────
    from et_dao.account_dao import get_balance
    current_balance = get_balance(sender_customer_id)
    if current_balance is None:
        raise RuntimeError("Could not retrieve account balance.")
    # Reject payment if balance < amount (no tolerance for overdraft)
    if current_balance < amount:
        raise ValueError(
            f"Insufficient balance. Available: Rs {current_balance:,.2f}, "
            f"Required: Rs {amount:,.2f}."
        )

    # ── Steps 3-5: Create pending payment record ──────────────────────
    payment_id    = "PAY" + generate_transaction_id()[2:]   # PAY + 13 chars
    debit_txn_id  = generate_transaction_id()
    credit_txn_id = generate_transaction_id()

    create_pending_payment(
        sender_customer_id=sender_customer_id,
        sender_account=sender_account,
        recipient_account=recipient_account,
        amount=amount,
        description=description,
        payment_id=payment_id,
        debit_txn_id=debit_txn_id,
        credit_txn_id=credit_txn_id,
        recipient_customer_id=recipient_customer_id,
        credit_txn_description=f"Payment received from {sender_account[-4:]}",
    )

    return {
        "payment_id":            payment_id,
        "debit_transaction_id":  debit_txn_id,
        "credit_transaction_id": credit_txn_id,
        "amount":                amount,
        "sender_customer_id":    sender_customer_id,
        "sender_account":        sender_account,
        "recipient_account":     recipient_account,
        "recipient_customer_id": recipient_customer_id,
        "description":           description,
        "created_at":            "now",   # for PRA
    }


def commit_payment(payment_result, status_override='COMPLETED') -> dict:
    """Commits a pending or held payment — deducts balance and credits recipient."""
    return dao_commit_payment(
        payment_id=payment_result['payment_id'],
        sender_customer_id=payment_result['sender_customer_id'],
        recipient_customer_id=payment_result['recipient_customer_id'],
        amount=payment_result['amount'],
        debit_txn_id=payment_result['debit_transaction_id'],
        credit_txn_id=payment_result['credit_transaction_id'],
        sender_account=payment_result['sender_account'],
        credit_txn_description=f"Payment received from {payment_result['sender_account'][-4:]}",
        status_override=status_override,
    )


def hold_payment(payment_result):
    """
    Holds a pending payment — status set to HELD.
    Money does NOT move. Balance is NOT deducted.
    Used for ALERT verdict: payment waits for OTP verification.
    """
    dao_hold_payment(
        payment_id=payment_result['payment_id'],
        debit_txn_id=payment_result['debit_transaction_id'],
    )


def reject_payment(payment_result):
    """
    Rejects a pending or held payment.
    Any reserved funds are released back to sender.
    """
    dao_reject_payment(
        payment_id=payment_result['payment_id'],
        debit_txn_id=payment_result['debit_transaction_id'],
    )


def get_held_payment(payment_id: str, customer_id: str) -> dict | None:
    """
    Returns the payment_result dict for a HELD payment.

    Used by the OTP verification route to retrieve the held payment
    after the customer successfully verifies their OTP, so it can
    be committed.

    Returns None if:
      - Payment not found
      - Payment is not in HELD status (already committed, rejected, or expired)
      - customer_id does not match (security check)
    """
    return dao_get_held_payment(payment_id=payment_id, customer_id=customer_id)


def get_payment_transactions(customer_id: str, limit: int = 20) -> list[dict]:
    """Returns recent payment history for a customer."""
    return get_payment_history(customer_id, limit)