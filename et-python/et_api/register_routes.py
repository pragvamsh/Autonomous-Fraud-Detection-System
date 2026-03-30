from flask import Blueprint, request, jsonify

from et_service.register_service import validate_registration_data
from et_model.customer import CustomerRegistration
from et_dao.customer_dao import insert_customer
from et_service.auth_service import set_session

register_bp = Blueprint('register', __name__, url_prefix='/api')


@register_bp.route('/register', methods=['POST'])
def register():
    data = request.json
    if not data:
        return jsonify({"message": "No data provided."}), 400

    # Normalise PAN to uppercase before validation
    if data.get('pan'):
        data['pan'] = data['pan'].strip().upper()

    # 1. Validate (pure, no DB)
    errors = validate_registration_data(data)
    if errors:
        return jsonify({"message": "Validation failed", "errors": errors}), 400

    # 2. Build model
    customer = CustomerRegistration.from_dict(data)

    # 3. Persist via DAO
    try:
        result = insert_customer(customer)
    except ValueError as e:
        return jsonify({"message": str(e)}), 409
    except RuntimeError as e:
        return jsonify({"message": str(e)}), 500

    # 4. Unpack result dict and set session
    customer_id    = result["customer_id"]
    account_number = result["account_number"]
    
    set_session(customer_id)

    return jsonify({
        "message": "Registration successful.",
        "customer_id": customer_id,
        "account_number": account_number,
        "temp_password_note": "A temporary system password has been assigned."
    }), 201