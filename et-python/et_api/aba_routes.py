"""
aba_routes.py
─────────────
HTTP routes for the Alert & Block Agent (ABA).

Endpoints:
  GET  /api/aba/health           — Health check and queue stats
  GET  /api/aba/case/<case_id>   — Get fraud case details
  POST /api/aba/confirm/<payment_id> — Customer confirms FLAG transaction
  POST /api/aba/verify-otp       — Verify OTP for FLAG+MFA
"""

from flask import Blueprint, jsonify, request
from et_service.auth_service import login_required
from et_dao.aba_dao import get_aba_health_stats, get_fraud_case


aba_bp = Blueprint('aba', __name__)


@aba_bp.route('/aba/health', methods=['GET'])
def aba_health():
    """
    ABA health endpoint — no auth required for ops monitoring.

    Returns:
        {
            "status": "ok",
            "queue_depth": int,
            "processed_last_1h": int,
            "cases_today": int,
            "str_queued_today": int,
            "accounts_frozen_today": int
        }
    """
    try:
        stats = get_aba_health_stats()
        return jsonify({'status': 'ok', **stats}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)}), 500


@aba_bp.route('/aba/case/<case_id>', methods=['GET'])
@login_required
def get_case(customer_id, case_id):
    """
    Get fraud case details by case_id.
    Only returns case if it belongs to the authenticated customer.
    """
    try:
        case = get_fraud_case(case_id)
        if not case:
            return jsonify({'error': 'Case not found'}), 404

        # Security: Verify case belongs to customer
        if case.get('customer_id') != customer_id:
            return jsonify({'error': 'Unauthorized'}), 403

        # Remove sensitive internal fields
        safe_case = {
            'case_id': case.get('case_id'),
            'priority': case.get('priority'),
            'status': case.get('status'),
            'created_at': str(case.get('created_at')) if case.get('created_at') else None,
        }

        return jsonify(safe_case), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@aba_bp.route('/aba/confirm/<payment_id>', methods=['POST'])
@login_required
def confirm_transaction(customer_id, payment_id):
    """
    Customer confirms FLAG transaction within 15s window.

    Request body:
        {
            "action": "CONFIRM" | "NOT_ME"
        }

    Returns:
        {
            "status": "confirmed" | "escalated",
            "payment_id": str
        }
    """
    try:
        data = request.get_json() or {}
        action = data.get('action', 'CONFIRM')

        if action == 'CONFIRM':
            # Transaction confirmed by customer
            return jsonify({
                'status': 'confirmed',
                'payment_id': payment_id,
                'message': 'Transaction confirmed',
            }), 200
        elif action == 'NOT_ME':
            # Customer did not authorize — escalate to ALERT
            return jsonify({
                'status': 'escalated',
                'payment_id': payment_id,
                'message': 'Transaction escalated for investigation',
            }), 200
        else:
            return jsonify({'error': 'Invalid action'}), 400

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@aba_bp.route('/aba/verify-otp', methods=['POST'])
@login_required
def verify_fraud_otp(customer_id):
    """
    Verify OTP for FLAG+MFA transactions.

    Request body:
        {
            "otp": str,
            "payment_id": str
        }

    Returns:
        {
            "verified": bool,
            "action": "APPROVE_TRANSACTION" | "ESCALATE_TO_ALERT",
            "payment_id": str
        }
    """
    try:
        data = request.get_json() or {}
        otp = data.get('otp')
        payment_id = data.get('payment_id')

        if not otp or not payment_id:
            return jsonify({'error': 'Missing otp or payment_id'}), 400

        from et_service.aba.account_controller import verify_fraud_mfa_otp
        result = verify_fraud_mfa_otp(customer_id, otp, payment_id)

        return jsonify(result), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@aba_bp.route('/aba/queue-status', methods=['GET'])
def queue_status():
    """
    Returns detailed queue status for monitoring dashboards.
    No auth required for ops monitoring.
    """
    try:
        stats = get_aba_health_stats()

        return jsonify({
            'status': 'ok',
            'queue': {
                'pending': stats.get('queue_depth', 0),
                'processed_1h': stats.get('processed_last_1h', 0),
            },
            'cases': {
                'created_today': stats.get('cases_today', 0),
            },
            'regulatory': {
                'str_queued_today': stats.get('str_queued_today', 0),
            },
            'accounts': {
                'frozen_today': stats.get('accounts_frozen_today', 0),
            },
        }), 200

    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)}), 500
