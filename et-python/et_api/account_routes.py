from flask import Blueprint, request, jsonify
from et_service.auth_service import session_required
from et_service.account_service import validate_add_money, mask_account_number
from et_dao.account_dao import get_balance, credit_account, get_transactions
from et_dao.auth_dao import find_customer_by_id

account_bp = Blueprint('account', __name__, url_prefix='/api')


@account_bp.route('/account', methods=['GET'])
@session_required
def get_account(customer_id):
    customer = find_customer_by_id(customer_id)
    if not customer:
        return jsonify({"message": "Account not found."}), 404

    return jsonify({
        "account_number": mask_account_number(customer['account_number']),
        "account_type":   customer['account_type'],
        "balance":        float(customer['balance']),
        "full_name":      customer['full_name'],
        "city":           customer['city'],
        "is_minor":       bool(customer['is_minor']),
    }), 200


@account_bp.route('/account/add-money', methods=['POST'])
@session_required
def add_money(customer_id):
    data   = request.json or {}
    amount = data.get('amount')

    errors = validate_add_money(amount)
    if errors:
        return jsonify({"message": "Invalid amount.", "errors": errors}), 400

    amount = round(float(amount), 2)

    try:
        result = credit_account(customer_id, amount, description="Add Money — Self Top-Up")
    except ValueError as e:
        return jsonify({"message": str(e)}), 404
    except RuntimeError as e:
        return jsonify({"message": str(e)}), 500

    return jsonify({
        "message":        f"₹{amount:,.2f} added successfully.",
        "transaction_id": result['transaction_id'],
        "new_balance":    result['new_balance'],
    }), 200


@account_bp.route('/transactions', methods=['GET'])
@session_required
def transactions(customer_id):
    limit = min(int(request.args.get('limit', 20)), 100)
    try:
        txns = get_transactions(customer_id, limit)
    except RuntimeError as e:
        return jsonify({"message": str(e)}), 500

    return jsonify({"transactions": txns, "count": len(txns)}), 200