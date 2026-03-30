"""
raa_routes.py
──────────────
HTTP routes for the Risk Assessment Agent.

Blueprint is registered in app.py with url_prefix='/api', so route
decorators must NOT include '/api/' — just the path after it.

GET /api/raa/health
GET /api/raa/alerts/<payment_id>
GET /api/raa/customer-alerts
GET /api/raa/customer-stats
"""

import json
from flask import Blueprint, jsonify
from et_service.auth_service import login_required
from et_dao.raa_dao import get_raa_health_stats

raa_bp = Blueprint('raa', __name__)


@raa_bp.route('/raa/health', methods=['GET'])
def raa_health():
    """RAA health endpoint — no auth required for ops monitoring."""
    try:
        stats = get_raa_health_stats()
        return jsonify({'status': 'ok', **stats}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)}), 500


@raa_bp.route('/raa/alerts/<payment_id>', methods=['GET'])
@login_required
def get_raa_alert(customer_id, payment_id):
    """
    GET /api/raa/alerts/{payment_id}

    Polls for the RAA result for a specific payment.
      200 — raa_processed = 1, returns full verdict
      202 — still processing, returns stage progress if available
      500 — unexpected error
    """
    try:
        from et_dao.monitoring_dao import get_fraud_alert_by_payment

        fa = get_fraud_alert_by_payment(payment_id, customer_id)
        if not fa:
            return jsonify({
                "status":  "processing",
                "stages":  [],
                "message": "RAA assessment not yet available.",
            }), 202

        # ── RAA complete ──────────────────────────────────────────────
        if fa.get('raa_processed') == 1:
            raa_citations = fa.get('raa_citations')
            if isinstance(raa_citations, str):
                try:
                    raa_citations = json.loads(raa_citations)
                except (json.JSONDecodeError, ValueError):
                    raa_citations = []
            elif raa_citations is None:
                raa_citations = []

            raa_stages = fa.get('raa_stages')
            if isinstance(raa_stages, str):
                try:
                    raa_stages = json.loads(raa_stages)
                except (json.JSONDecodeError, ValueError):
                    raa_stages = {}

            return jsonify({
                "status":             "completed",
                "raa_verdict":        fa.get('raa_verdict'),
                "final_raa_score":    fa.get('final_raa_score'),
                "customer_tier":      fa.get('customer_tier'),
                "score_a":            fa.get('score_a'),
                "score_b":            fa.get('score_b'),
                "str_required":       bool(fa.get('str_required')),
                "ctr_flag":           bool(fa.get('ctr_flag')),
                "investigation_note": fa.get('investigation_note'),
                "raa_citations":      raa_citations,
                "raa_stages":         raa_stages,
                # TMA + PRA summary so frontend modal can display all agents
                "tma_decision":       fa.get('decision'),
                "tma_score":          fa.get('risk_score'),
                "pra_verdict":        fa.get('pra_verdict'),
                "pattern_score":      fa.get('pattern_score'),
                "typology_code":      fa.get('typology_code'),
            }), 200

        # ── RAA still processing — return stage progress ──────────────
        raw_stages = fa.get('raa_stages')
        stages = {}
        if raw_stages:
            if isinstance(raw_stages, str):
                try:
                    stages = json.loads(raw_stages)
                except (json.JSONDecodeError, ValueError):
                    stages = {}
            else:
                stages = raw_stages

        return jsonify({
            "status":  "processing",
            "stages":  stages,
            "message": "RAA is evaluating this payment.",
        }), 202

    except Exception as e:
        import traceback
        print(f"[RAA Route] ERROR /raa/alerts/{payment_id}: {e}")
        traceback.print_exc()
        return jsonify({
            "status":  "error",
            "message": "Could not retrieve RAA alert.",
            "error":   str(e),
        }), 500


@raa_bp.route('/raa/customer-alerts', methods=['GET'])
@login_required
def get_customer_raa_alerts(customer_id):
    """GET /api/raa/customer-alerts — last 10 RAA alerts for this customer."""
    try:
        from et_dao.raa_dao import get_customer_raa_alerts as _get_alerts
        alerts = _get_alerts(customer_id, limit=10)
        return jsonify({"alerts": alerts}), 200
    except Exception as e:
        import traceback
        print(f"[RAA Route] ERROR /raa/customer-alerts: {e}")
        traceback.print_exc()
        return jsonify({"message": "Could not retrieve customer RAA alerts."}), 500


@raa_bp.route('/raa/customer-stats', methods=['GET'])
@login_required
def get_customer_raa_stats(customer_id):
    """GET /api/raa/customer-stats — aggregated RAA stats for this customer."""
    try:
        from et_dao.raa_dao import get_customer_raa_stats as _get_stats
        stats = _get_stats(customer_id)
        return jsonify(stats), 200
    except Exception as e:
        import traceback
        print(f"[RAA Route] ERROR /raa/customer-stats: {e}")
        traceback.print_exc()
        return jsonify({"message": "Could not retrieve customer RAA stats."}), 500