import random
import string
from datetime import datetime


ADD_MONEY_MIN = 1.00
ADD_MONEY_MAX = 100000.00   # ₹1 lakh max per top-up (realistic cap)


def validate_add_money(amount) -> list[str]:
    errors = []
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        errors.append("Amount must be a valid number.")
        return errors

    if amount < ADD_MONEY_MIN:
        errors.append(f"Minimum top-up amount is ₹{ADD_MONEY_MIN:.2f}.")
    if amount > ADD_MONEY_MAX:
        errors.append(f"Maximum top-up amount per transaction is ₹{ADD_MONEY_MAX:,.2f}.")
    return errors


def generate_transaction_id() -> str:
    """Generate a unique 16-char alphanumeric transaction ID."""
    chars = string.ascii_uppercase + string.digits
    return "ET" + "".join(random.choices(chars, k=14))


def mask_account_number(account_number: str) -> str:
    """Return XXXX-XXXX-1234 style masked account number."""
    if len(account_number) < 4:
        return "****"
    visible = account_number[-4:]
    masked_blocks = ["XXXX"] * ((len(account_number) - 4) // 4)
    return "-".join(masked_blocks + [visible])