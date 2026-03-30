"""
Admin Routes — Admin dashboard authentication and endpoints

Provides:
  - /api/admin/login         — Admin authentication
  - /api/admin/logout        — Session termination
  - /api/admin/check_auth    — Session check
  - /api/admin/dashboard     — Dashboard stats
  - /api/admin/filings       — Flagged transaction filings (FLAG/ALERT/BLOCK only)
  - /api/admin/unfreeze/<id> — Unfreeze a customer account
  - /api/admin/cases         — Open fraud cases

[FIX] Role isolation: admin session and customer session are completely
separate. Admin login sets 'admin_logged_in' in session. Customer login
sets 'customer_id'. The admin_required decorator ONLY checks admin session.
The customer login_required decorator ONLY checks customer session.
Neither can access the other's endpoints.
"""

from flask import Blueprint, request, jsonify, session
from functools import wraps
from et_service.cla.constants import ADMIN_USERNAME, ADMIN_PASSWORD
from et_dao.cla_dao import get_dashboard_stats

admin_bp = Blueprint('admin', __name__)


# ═════════════════════════════════════════════════════════════════════════════
# AUTHENTICATION DECORATOR
# ═════════════════════════════════════════════════════════════════════════════

def admin_required(f):
    """
    Protects admin-only endpoints.

    Checks ONLY 'admin_logged_in' in session.
    Does NOT check customer session keys.
    An authenticated customer cannot pass this check.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return jsonify({'error': 'Unauthorized — Admin login required'}), 401
        # Extra safety: if somehow a customer_id is in session but admin is not
        # set, this still blocks. Belt-and-suspenders.
        return f(*args, **kwargs)
    return decorated_function


# ═════════════════════════════════════════════════════════════════════════════
# LOGIN / LOGOUT
# ═════════════════════════════════════════════════════════════════════════════

@admin_bp.route('/api/admin/login', methods=['POST'])
def admin_login():
    """
    POST /api/admin/login
    Body: { "username": "...", "password": "..." }

    Sets admin_logged_in = True in session.
    Does NOT set customer_id — admin sessions are isolated from customer sessions.
    """
    try:
        data     = request.get_json() or {}
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()

        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            # Clear any stale customer session before setting admin session
            # Prevents a logged-in customer from escalating to admin
            session.clear()
            session['admin_logged_in'] = True
            session['admin_username']  = username
            session.permanent          = True

            return jsonify({
                'success':  True,
                'message':  'Login successful',
                'username': username,
                'role':     'admin',
            }), 200
        else:
            return jsonify({
                'success': False,
                'error':   'Invalid credentials',
            }), 401

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_bp.route('/api/admin/logout', methods=['POST'])
@admin_required
def admin_logout():
    """POST /api/admin/logout — Clears admin session."""
    try:
        session.pop('admin_logged_in', None)
        session.pop('admin_username',  None)
        return jsonify({'success': True, 'message': 'Logout successful'}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_bp.route('/api/admin/check_auth', methods=['GET'])
def check_auth():
    """
    GET /api/admin/check_auth
    Returns admin authentication status.
    Also returns role='admin' so the frontend can distinguish
    admin from customer sessions.
    """
    is_logged_in = session.get('admin_logged_in', False)
    username     = session.get('admin_username', None)
    return jsonify({
        'authenticated': is_logged_in,
        'username':      username if is_logged_in else None,
        'role':          'admin'  if is_logged_in else None,
    }), 200


# ═════════════════════════════════════════════════════════════════════════════
# DASHBOARD
# ═════════════════════════════════════════════════════════════════════════════

@admin_bp.route('/api/admin/dashboard', methods=['GET'])
@admin_required
def get_admin_dashboard():
    """GET /api/admin/dashboard — Returns CLA stats for admin view."""
    try:
        stats = get_dashboard_stats()
        return jsonify({'success': True, 'stats': stats}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ═════════════════════════════════════════════════════════════════════════════
# FLAGGED TRANSACTIONS  (FLAG / ALERT / BLOCK only)
# ═════════════════════════════════════════════════════════════════════════════

@admin_bp.route('/api/admin/flagged-transactions', methods=['GET'])
@admin_required
def get_flagged_transactions():
    """
    GET /api/admin/flagged-transactions?type=FLAG|ALERT|BLOCK&limit=50

    Returns fraud_alerts rows where TMA decision is FLAG, ALERT, or BLOCK.
    ALLOW transactions are never shown in the admin dashboard.

    Query params:
      type  — optional filter: FLAG | ALERT | BLOCK (default: all three)
      limit — max rows to return (default: 50, max: 200)
    """
    try:
        from db import get_db_connection
        import json

        verdict_filter = request.args.get('type', '').upper()
        limit          = min(int(request.args.get('limit', 50)), 200)

        allowed_verdicts = {'FLAG', 'ALERT', 'BLOCK'}
        if verdict_filter and verdict_filter in allowed_verdicts:
            verdicts = [verdict_filter]
        else:
            verdicts = list(allowed_verdicts)

        placeholders = ', '.join(['%s'] * len(verdicts))

        conn   = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(f"""
            SELECT
                fa.id                 AS alert_id,
                fa.customer_id,
                fa.transaction_id,
                fa.decision           AS tma_decision,
                fa.risk_score         AS tma_score,
                fa.pra_verdict,
                fa.pattern_score,
                fa.raa_verdict,
                fa.final_raa_score,
                fa.customer_tier,
                fa.typology_code,
                fa.str_required,
                fa.ctr_flag,
                fa.investigation_note,
                fa.aba_gateway_action,
                fa.aba_case_id,
                fa.created_at,
                c.full_name           AS customer_name,
                c.account_number,
                c.is_frozen,
                pt.payment_id,
                pt.amount
            FROM fraud_alerts fa
            LEFT JOIN customers c        ON fa.customer_id  = c.customer_id
            LEFT JOIN payment_transactions pt ON fa.transaction_id = pt.debit_transaction_id
            WHERE fa.decision IN ({placeholders})
            ORDER BY fa.created_at DESC
            LIMIT %s
        """, (*verdicts, limit))

        rows = cursor.fetchall()

        # Serialise datetimes
        for row in rows:
            if row.get('created_at'):
                row['created_at'] = str(row['created_at'])

        cursor.close()
        conn.close()

        return jsonify({
            'success':      True,
            'transactions': rows,
            'count':        len(rows),
            'filter':       verdict_filter or 'ALL',
        }), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


# ═════════════════════════════════════════════════════════════════════════════
# ACCOUNT UNFREEZE
# ═════════════════════════════════════════════════════════════════════════════

@admin_bp.route('/api/admin/unfreeze/<customer_id>', methods=['POST'])
@admin_required
def unfreeze_account(customer_id):
    """
    POST /api/admin/unfreeze/<customer_id>

    Unfreezes a customer account that was frozen by ABA after a BLOCK verdict.
    Only admin can unfreeze — customers cannot unfreeze their own account.

    Logs the unfreeze action with the admin username for audit trail.
    """
    try:
        from db import get_db_connection

        admin_username = session.get('admin_username', 'unknown_admin')
        conn   = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Check current freeze status
        cursor.execute("""
            SELECT customer_id, full_name, is_frozen, frozen_reason, frozen_by_alert_id
            FROM customers WHERE customer_id = %s
        """, (customer_id,))
        customer = cursor.fetchone()

        if not customer:
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Customer not found'}), 404

        if not customer.get('is_frozen'):
            cursor.close()
            conn.close()
            return jsonify({
                'success': False,
                'error':   f"Account {customer_id} is not currently frozen.",
            }), 400

        # Unfreeze
        cursor.execute("""
            UPDATE customers
            SET is_frozen          = 0,
                frozen_at          = NULL,
                frozen_reason      = NULL,
                frozen_by_alert_id = NULL
            WHERE customer_id = %s
        """, (customer_id,))
        conn.commit()

        # Write audit log
        cursor.execute("""
            INSERT INTO admin_audit_log
                (action, customer_id, performed_by, details, created_at)
            VALUES
                ('UNFREEZE_ACCOUNT', %s, %s, %s, NOW())
        """, (
            customer_id,
            admin_username,
            f"Account unfrozen by admin {admin_username}. "
            f"Was frozen for: {customer.get('frozen_reason', 'unknown')}. "
            f"Frozen by alert_id: {customer.get('frozen_by_alert_id', 'unknown')}.",
        ))
        conn.commit()

        cursor.close()
        conn.close()

        print(f"[AdminRoute] Account unfrozen | customer={customer_id} | "
              f"by_admin={admin_username} | "
              f"was_frozen_for={customer.get('frozen_reason', 'unknown')}")

        return jsonify({
            'success':       True,
            'message':       f"Account for {customer.get('full_name', customer_id)} "
                             f"has been unfrozen successfully.",
            'customer_id':   customer_id,
            'unfrozen_by':   admin_username,
        }), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_bp.route('/api/admin/frozen-accounts', methods=['GET'])
@admin_required
def get_frozen_accounts():
    """
    GET /api/admin/frozen-accounts
    Returns all currently frozen customer accounts for the admin dashboard.
    """
    try:
        from db import get_db_connection
        conn   = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT customer_id, full_name, account_number,
                   frozen_at, frozen_reason, frozen_by_alert_id
            FROM customers
            WHERE is_frozen = 1
            ORDER BY frozen_at DESC
        """)
        rows = cursor.fetchall()
        for row in rows:
            if row.get('frozen_at'):
                row['frozen_at'] = str(row['frozen_at'])
        cursor.close()
        conn.close()
        return jsonify({'success': True, 'frozen_accounts': rows, 'count': len(rows)}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ═════════════════════════════════════════════════════════════════════════════
# FRAUD CASES
# ═════════════════════════════════════════════════════════════════════════════

@admin_bp.route('/api/admin/cases', methods=['GET'])
@admin_required
def get_fraud_cases():
    """GET /api/admin/cases — Returns open fraud cases for admin review."""
    try:
        from db import get_db_connection
        import json

        limit  = min(int(request.args.get('limit', 50)), 200)
        status = request.args.get('status', 'OPEN').upper()

        conn   = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT fc.case_id, fc.alert_id, fc.customer_id,
                   fc.priority, fc.status, fc.created_at,
                   c.full_name AS customer_name
            FROM fraud_cases fc
            LEFT JOIN customers c ON fc.customer_id = c.customer_id
            WHERE fc.status = %s
            ORDER BY fc.priority ASC, fc.created_at DESC
            LIMIT %s
        """, (status, limit))

        rows = cursor.fetchall()
        for row in rows:
            if row.get('created_at'):
                row['created_at'] = str(row['created_at'])
        cursor.close()
        conn.close()
        return jsonify({'success': True, 'cases': rows, 'count': len(rows)}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ═════════════════════════════════════════════════════════════════════════════
# PDF EXPORT ENDPOINTS
# ═════════════════════════════════════════════════════════════════════════════

@admin_bp.route('/api/admin/alerts/<int:alert_id>/pdf', methods=['GET'])
@admin_required
def export_alert_pdf(alert_id):
    """
    GET /api/admin/alerts/<alert_id>/pdf

    Generates and downloads a comprehensive Alert Report PDF.
    Includes translated anomaly flags, risk explanations, and glossary.
    """
    try:
        from flask import send_file
        from db import get_db_connection
        from et_service.cla.pdf_generator import generate_alert_pdf
        import json

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # 1. Fetch alert data
        cursor.execute("""
            SELECT * FROM fraud_alerts WHERE id = %s
        """, (alert_id,))
        alert_data = cursor.fetchone()

        if not alert_data:
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Alert not found'}), 404

        # Parse JSON fields
        for json_field in ['anomaly_flags', 'rag_citations', 'pra_reg_citations', 'raa_citations']:
            if alert_data.get(json_field) and isinstance(alert_data[json_field], str):
                try:
                    alert_data[json_field] = json.loads(alert_data[json_field])
                except:
                    pass

        # 2. Fetch customer data
        cursor.execute("""
            SELECT customer_id, full_name, account_number, is_frozen,
                   frozen_at, frozen_reason
            FROM customers WHERE customer_id = %s
        """, (alert_data['customer_id'],))
        customer_data = cursor.fetchone() or {}

        # 3. Fetch transaction data
        cursor.execute("""
            SELECT pt.*, pt.debit_transaction_id as transaction_id
            FROM payment_transactions pt
            WHERE pt.debit_transaction_id = %s
        """, (alert_data['transaction_id'],))
        transaction_data = cursor.fetchone() or {}

        cursor.close()
        conn.close()

        # 4. Generate PDF
        pdf_path = generate_alert_pdf(alert_data, customer_data, transaction_data)

        if not pdf_path:
            return jsonify({'success': False, 'error': 'PDF generation failed'}), 500

        # 5. Return PDF file
        return send_file(
            pdf_path,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f"Alert-{alert_id}-Report.pdf"
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_bp.route('/api/admin/frozen/<customer_id>/pdf', methods=['GET'])
@admin_required
def export_block_pdf(customer_id):
    """
    GET /api/admin/frozen/<customer_id>/pdf

    Generates and downloads an Account Block/Freeze Report PDF.
    Explains why the account was frozen with user-friendly language.
    """
    try:
        from flask import send_file
        from db import get_db_connection
        from et_service.cla.pdf_generator import generate_block_pdf
        import json

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # 1. Fetch customer and freeze data
        cursor.execute("""
            SELECT customer_id, full_name, account_number, is_frozen,
                   frozen_at, frozen_reason, frozen_by_alert_id
            FROM customers WHERE customer_id = %s
        """, (customer_id,))
        customer_data = cursor.fetchone()

        if not customer_data:
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Customer not found'}), 404

        if not customer_data.get('is_frozen'):
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Account is not frozen'}), 400

        # Extract freeze data
        freeze_data = {
            'frozen_at': customer_data.get('frozen_at'),
            'frozen_reason': customer_data.get('frozen_reason'),
            'frozen_by_alert_id': customer_data.get('frozen_by_alert_id'),
        }

        # 2. Fetch triggering alert (if exists)
        alert_data = None
        if customer_data.get('frozen_by_alert_id'):
            cursor.execute("""
                SELECT * FROM fraud_alerts WHERE id = %s
            """, (customer_data['frozen_by_alert_id'],))
            alert_data = cursor.fetchone()

            # Parse JSON fields
            if alert_data:
                for json_field in ['anomaly_flags', 'rag_citations', 'pra_reg_citations', 'raa_citations']:
                    if alert_data.get(json_field) and isinstance(alert_data[json_field], str):
                        try:
                            alert_data[json_field] = json.loads(alert_data[json_field])
                        except:
                            pass

        cursor.close()
        conn.close()

        # 3. Generate PDF
        pdf_path = generate_block_pdf(customer_data, alert_data or {}, freeze_data)

        if not pdf_path:
            return jsonify({'success': False, 'error': 'PDF generation failed'}), 500

        # 4. Return PDF file
        return send_file(
            pdf_path,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f"Block-Report-{customer_id}.pdf"
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500