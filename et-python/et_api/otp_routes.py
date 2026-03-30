from flask import Blueprint, request, jsonify
from et_service.auth_service import session_required
from et_service.otp_service import generate_otp, send_otp_email, verify_otp, is_expired
from et_dao.otp_dao import store_otp, fetch_latest_otp, mark_otp_used
from et_dao.auth_dao import find_customer_by_id, mark_email_verified

otp_bp = Blueprint('otp', __name__, url_prefix='/api')

VALID_PURPOSES = ('EMAIL_VERIFY', 'PASSWORD_CHANGE')


@otp_bp.route('/send-otp', methods=['POST'])
@session_required
def send_otp(customer_id):
    """
    Send an OTP to the customer's registered email.
    Body: { "purpose": "EMAIL_VERIFY" | "PASSWORD_CHANGE" }
    """
    data    = request.json or {}
    purpose = (data.get('purpose') or '').strip().upper()

    if purpose not in VALID_PURPOSES:
        return jsonify({"message": f"Invalid purpose. Must be one of: {', '.join(VALID_PURPOSES)}"}), 400

    customer = find_customer_by_id(customer_id)
    if not customer:
        return jsonify({"message": "Account not found."}), 404

    # Guard: don't let already-verified emails re-trigger EMAIL_VERIFY
    if purpose == 'EMAIL_VERIFY' and customer['is_email_verified']:
        return jsonify({"message": "Email is already verified."}), 409

    # Guard: must have password set to request PASSWORD_CHANGE OTP
    if purpose == 'PASSWORD_CHANGE' and not customer['password_set']:
        return jsonify({"message": "Set your password first before requesting a change OTP."}), 400

    otp = generate_otp()

    try:
        store_otp(customer_id, otp, purpose)
    except ValueError as e:
        return jsonify({"message": str(e)}), 429   # rate limit
    except RuntimeError as e:
        return jsonify({"message": str(e)}), 500

    sent = send_otp_email(customer['email'], customer['full_name'], otp, purpose)
    if not sent:
        return jsonify({"message": "Failed to send OTP email. Please try again."}), 500

    return jsonify({
        "message": f"OTP sent to {customer['email']}.",
        "expires_in_minutes": 10,
    }), 200


@otp_bp.route('/verify-email-otp', methods=['POST'])
@session_required
def verify_email_otp(customer_id):
    """
    Verify the EMAIL_VERIFY OTP and mark the email as verified.
    Body: { "otp": "123456" }
    """
    data = request.json or {}
    otp  = (data.get('otp') or '').strip()

    if not otp:
        return jsonify({"message": "OTP is required."}), 400

    record = fetch_latest_otp(customer_id, 'EMAIL_VERIFY')
    if not record:
        return jsonify({"message": "No OTP found. Please request a new one."}), 400
    if is_expired(record['expires_at']):
        return jsonify({"message": "OTP has expired. Please request a new one."}), 400
    if not verify_otp(otp, record['hashed_otp']):
        return jsonify({"message": "Invalid OTP. Please try again."}), 400

    mark_otp_used(record['id'])
    mark_email_verified(customer_id)

    return jsonify({"message": "Email verified successfully. ✅"}), 200