"""
pattern_routes.py
─────────────────
Flask API routes for the Pattern Recognition Agent (PRA).

Endpoints:
  GET /api/pattern-alert/<payment_id>  — retrieve PRA result for a payment
"""

from flask import Blueprint, jsonify
from et_service.auth_service import login_required

pattern_bp = Blueprint('pattern', __name__)



@pattern_bp.route('/pattern-profile', methods=['GET'])
@login_required
def get_pattern_profile(customer_id):
    """
    GET /api/pattern-profile
    Returns the current customer's rolling pattern profile.
    Shows trend, escalation count, and rolling average risk.
    """
    try:
        from et_dao.pattern_dao import get_pattern_profile as _get_profile
        profile = _get_profile(customer_id)
        if not profile:
            return jsonify({
                "customer_id":       customer_id,
                "rolling_avg_risk":  0.0,
                "trend_direction":   "STABLE",
                "escalation_count":  0,
                "consecutive_blocks": 0,
                "last_pattern_alert_at": None,
            }), 200
        # Serialise datetime
        if profile.get('last_pattern_alert_at'):
            profile['last_pattern_alert_at'] = str(profile['last_pattern_alert_at'])
        if profile.get('last_updated'):
            profile['last_updated'] = str(profile['last_updated'])
        return jsonify(profile), 200
    except RuntimeError as e:
        return jsonify({"message": "Could not retrieve pattern profile."}), 500
