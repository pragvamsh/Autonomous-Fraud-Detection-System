from flask import session, jsonify
from functools import wraps
import bcrypt

PASSWORD_MIN_LENGTH = 8


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def validate_password_strength(password: str) -> list[str]:
    errors = []
    if len(password) < PASSWORD_MIN_LENGTH:
        errors.append(f"Password must be at least {PASSWORD_MIN_LENGTH} characters.")
    if not any(c.isupper() for c in password):
        errors.append("Password must contain at least one uppercase letter.")
    if not any(c.islower() for c in password):
        errors.append("Password must contain at least one lowercase letter.")
    if not any(c.isdigit() for c in password):
        errors.append("Password must contain at least one digit.")
    if not any(c in "!@#$%^&*()_+-=[]{}|;':\",./<>?" for c in password):
        errors.append("Password must contain at least one special character.")
    return errors


# ── Session helpers ───────────────────────────────────────────────────────────

def set_session(customer_id: str) -> None:
    """Store customer_id in Flask session."""
    session['customer_id'] = customer_id
    session.permanent = True


def clear_session() -> None:
    """Clear the current session."""
    session.clear()


# ── Route decorators ──────────────────────────────────────────────────────────

def login_required(f):
    """
    Protects customer-only endpoints.

    Two-layer check:
      1. Blocks admin sessions — an admin cannot access customer endpoints
         while logged in as admin. Forces explicit customer login.
      2. Checks customer_id in session — rejects unauthenticated requests.

    [FIX] Added admin session block to enforce strict role separation.
    Without this, an admin logged in via /api/admin/login could call
    /api/payment or /api/me by simply having customer_id absent — the
    check would return 401 (not 403), which is the wrong error. More
    importantly, if a customer_id somehow leaked into an admin session,
    this guard catches it explicitly.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        # Block admin sessions from customer endpoints
        if session.get('admin_logged_in'):
            return jsonify({
                "message": "Forbidden — you are logged in as admin. "
                           "Please log out of the admin portal and log in as a customer.",
                "code":    "ROLE_MISMATCH",
            }), 403

        # Check customer session
        customer_id = session.get('customer_id')
        if not customer_id:
            return jsonify({
                "message": "Not logged in. Please log in.",
                "code":    "UNAUTHENTICATED",
            }), 401

        return f(customer_id, *args, **kwargs)
    return decorated


def session_required(f):
    """
    Alias for login_required — same role isolation rules apply.
    Kept for backwards compatibility with routes that use @session_required.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        # Block admin sessions
        if session.get('admin_logged_in'):
            return jsonify({
                "message": "Forbidden — admin session cannot access customer endpoints.",
                "code":    "ROLE_MISMATCH",
            }), 403

        customer_id = session.get('customer_id')
        if not customer_id:
            return jsonify({
                "message": "Not authenticated. Please log in.",
                "code":    "UNAUTHENTICATED",
            }), 401

        return f(customer_id, *args, **kwargs)
    return decorated


def security_complete(customer: dict) -> bool:
    return bool(customer.get("password_set")) and bool(customer.get("is_email_verified"))