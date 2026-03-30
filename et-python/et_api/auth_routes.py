from flask import Blueprint, request, jsonify
from et_service.auth_service import (
    verify_password, hash_password, validate_password_strength,
    set_session, clear_session, session_required, security_complete
)
from et_dao.auth_dao import (
    find_customer_by_email_or_id, find_customer_by_id,
    set_password as dao_set_password,
    update_email, update_phone
)
from et_dao.otp_dao import fetch_latest_otp, mark_otp_used
from et_service.otp_service import verify_otp, is_expired
from et_service.account_service import mask_account_number

auth_bp = Blueprint('auth', __name__, url_prefix='/api')


# ── Login ─────────────────────────────────────────────────────────────────────

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.json or {}
    identifier = (data.get('identifier') or '').strip()
    password   = (data.get('password') or '').strip()

    if not identifier or not password:
        return jsonify({"message": "Customer ID / Email and password are required."}), 400

    customer = find_customer_by_email_or_id(identifier)
    if not customer:
        return jsonify({"message": "Invalid credentials."}), 401

    if not customer.get('password_set') or not customer.get('password_hash'):
        return jsonify({"message": "Password not set yet. Please complete your security setup."}), 403

    if not verify_password(password, customer['password_hash']):
        return jsonify({"message": "Invalid credentials."}), 401

    set_session(customer['customer_id'])
    
    # Check if account is frozen and warn user
    from et_dao.auth_dao import find_customer_by_id
    full_customer = find_customer_by_id(customer['customer_id'])
    is_frozen = bool(full_customer.get('is_frozen')) if full_customer else False
    
    return jsonify({
        "message": "Login successful.",
        "customer_id": customer['customer_id'],
        "is_first_login": bool(customer['is_first_login']),
        "security_complete": security_complete(customer),
        "is_frozen": is_frozen,
        "frozen_reason": full_customer.get('frozen_reason') if is_frozen else None,
    }), 200


# ── Profile ───────────────────────────────────────────────────────────────────

@auth_bp.route('/me', methods=['GET'])
@session_required
def get_me(customer_id):
    try:
        customer = find_customer_by_id(customer_id)
        if not customer:
            return jsonify({"message": "Account not found."}), 404

        return jsonify({
            "customer_id":       customer['customer_id'],
            "full_name":         customer['full_name'],
            "email":             customer['email'],
            "phone_number":      customer['phone_number'],
            "date_of_birth":     str(customer['date_of_birth']),
            "gender":            customer['gender'],
            "account_number":    mask_account_number(customer['account_number']),
            "account_number_raw": customer['account_number'],  # for internal use
            "account_type":      customer['account_type'],
            "city":              customer['city'],
            "state":             customer['state'],
            "balance":           float(customer['balance']),
            "password_set":      bool(customer['password_set']),
            "is_first_login":    bool(customer['is_first_login']),
            "is_email_verified": bool(customer['is_email_verified']),
            "is_minor":          bool(customer['is_minor']),
            "is_frozen":         bool(customer.get('is_frozen', 0)),
            "frozen_reason":     customer.get('frozen_reason') or None,
            "frozen_at":         str(customer['frozen_at']) if customer.get('frozen_at') else None,
            "frozen_by_alert_id": customer.get('frozen_by_alert_id') or None,
            "security_complete": security_complete(customer),
            "member_since":      str(customer['created_at']),
        }), 200
    except Exception as e:
        print(f"[ERROR] /me endpoint failed: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"message": "Failed to load profile.", "error": str(e)}), 500


# ── First-time password setup (no OTP required) ───────────────────────────────

@auth_bp.route('/set-password', methods=['POST'])
@session_required
def set_password_first_time(customer_id):
    customer = find_customer_by_id(customer_id)
    if not customer:
        return jsonify({"message": "Account not found."}), 404

    if customer['password_set']:
        return jsonify({"message": "Password already set. Use change-password instead."}), 409

    data     = request.json or {}
    password = data.get('password', '')
    confirm  = data.get('confirmPassword', '')

    if password != confirm:
        return jsonify({"message": "Passwords do not match."}), 400

    errors = validate_password_strength(password)
    if errors:
        return jsonify({"message": "Password too weak.", "errors": errors}), 400

    dao_set_password(customer_id, hash_password(password))
    return jsonify({"message": "Password set successfully."}), 200


# ── Change password (OTP required) ────────────────────────────────────────────

@auth_bp.route('/change-password', methods=['POST'])
@session_required
def change_password(customer_id):
    customer = find_customer_by_id(customer_id)
    if not customer:
        return jsonify({"message": "Account not found."}), 404

    if not customer['password_set']:
        return jsonify({"message": "Please use /set-password for first-time setup."}), 400

    data        = request.json or {}
    otp         = data.get('otp', '').strip()
    new_password = data.get('newPassword', '')
    confirm     = data.get('confirmPassword', '')

    if new_password != confirm:
        return jsonify({"message": "Passwords do not match."}), 400

    errors = validate_password_strength(new_password)
    if errors:
        return jsonify({"message": "Password too weak.", "errors": errors}), 400

    # Validate OTP
    record = fetch_latest_otp(customer_id, 'PASSWORD_CHANGE')
    if not record:
        return jsonify({"message": "No OTP found. Please request a new one."}), 400
    if is_expired(record['expires_at']):
        return jsonify({"message": "OTP has expired. Please request a new one."}), 400
    if not verify_otp(otp, record['hashed_otp']):
        return jsonify({"message": "Invalid OTP."}), 400

    mark_otp_used(record['id'])
    dao_set_password(customer_id, hash_password(new_password))
    return jsonify({"message": "Password changed successfully."}), 200


# ── Update profile (email / phone — OTP required for email) ──────────────────

@auth_bp.route('/profile/update-email', methods=['POST'])
@session_required
def update_email_route(customer_id):
    data      = request.json or {}
    new_email = (data.get('newEmail') or '').strip().lower()
    otp       = (data.get('otp') or '').strip()

    if not new_email:
        return jsonify({"message": "New email is required."}), 400

    # Validate OTP (EMAIL_VERIFY purpose used for email change too)
    record = fetch_latest_otp(customer_id, 'EMAIL_VERIFY')
    if not record:
        return jsonify({"message": "No OTP found. Please request a new OTP."}), 400
    if is_expired(record['expires_at']):
        return jsonify({"message": "OTP has expired."}), 400
    if not verify_otp(otp, record['hashed_otp']):
        return jsonify({"message": "Invalid OTP."}), 400

    mark_otp_used(record['id'])
    update_email(customer_id, new_email)
    return jsonify({"message": "Email updated. Please verify your new email."}), 200


@auth_bp.route('/profile/update-phone', methods=['POST'])
@session_required
def update_phone_route(customer_id):
    import re
    data      = request.json or {}
    new_phone = (data.get('newPhone') or '').strip()

    if not re.match(r'^[6-9]\d{9}$', new_phone):
        return jsonify({"message": "Enter a valid 10-digit Indian mobile number."}), 400

    update_phone(customer_id, new_phone)
    return jsonify({"message": "Phone number updated successfully."}), 200


# ── Logout ────────────────────────────────────────────────────────────────────

@auth_bp.route('/logout', methods=['POST'])
@session_required
def logout(customer_id):
    clear_session()
    return jsonify({"message": "Logout successful."}), 200