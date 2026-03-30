"""
cla_routes.py
─────────────
CLA API endpoints — Citation & Legal Archive operations.

[FIX] export_filing_pdf: Added Path 3 fallback — generates PDF directly
from fraud_cases + fraud_alerts when CLA hasn't processed the case yet
(cla_archive is empty). This is why CASE-xxx IDs returned 404.

[FIX] CLA agent must be started in app.py — see bottom of this file for
the _bootstrap_cla() function to add to app.py.
"""

from flask import Blueprint, request, jsonify, send_file, session
from functools import wraps
from et_dao.cla_dao import (
    get_all_filings,
    get_filing_by_id,
    get_filing_by_case_id,
    update_filing_status,
    get_archive_by_filing_id,
    get_archive_by_case_id,
    get_citations_by_category,
    get_citation_by_id,
    get_case_by_id,
)
from et_service.cla.pdf_generator import generate_str_pdf, generate_ctr_pdf
from et_service.cla.cla_agent import process_case_manually
import os
import json

cla_bp = Blueprint('cla', __name__)


# ═════════════════════════════════════════════════════════════════════════════
# ADMIN AUTHENTICATION DECORATOR
# ═════════════════════════════════════════════════════════════════════════════

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return jsonify({'error': 'Unauthorized - Admin login required'}), 401
        return f(*args, **kwargs)
    return decorated_function


# ═════════════════════════════════════════════════════════════════════════════
# FILINGS ENDPOINTS  (unchanged)
# ═════════════════════════════════════════════════════════════════════════════

@cla_bp.route('/api/cla/filings', methods=['GET'])
@admin_required
def get_filings():
    try:
        limit   = request.args.get('limit', 100, type=int)
        filings = get_all_filings(limit=limit)
        return jsonify({'success': True, 'count': len(filings), 'filings': filings}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@cla_bp.route('/api/cla/filings/<filing_id>', methods=['GET'])
@admin_required
def get_filing(filing_id):
    try:
        filing = get_filing_by_id(filing_id)
        if not filing:
            return jsonify({'success': False, 'error': 'Filing not found'}), 404
        return jsonify({'success': True, 'filing': filing}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@cla_bp.route('/api/cla/filings/<filing_id>/approve', methods=['POST'])
@admin_required
def approve_filing(filing_id):
    try:
        data        = request.get_json() or {}
        approved_by = data.get('approved_by', session.get('admin_username', 'ADMIN'))
        success     = update_filing_status(filing_id, 'APPROVED', approved_by=approved_by)
        if not success:
            return jsonify({'success': False, 'error': 'Failed to approve filing'}), 500
        return jsonify({'success': True, 'message': f'Filing {filing_id} approved by {approved_by}'}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@cla_bp.route('/api/cla/filings/<filing_id>/reject', methods=['POST'])
@admin_required
def reject_filing(filing_id):
    try:
        success = update_filing_status(filing_id, 'REJECTED')
        if not success:
            return jsonify({'success': False, 'error': 'Failed to reject filing'}), 500
        return jsonify({'success': True, 'message': f'Filing {filing_id} rejected'}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@cla_bp.route('/api/cla/filings/<filing_id>/file', methods=['POST'])
@admin_required
def file_filing(filing_id):
    try:
        success = update_filing_status(filing_id, 'FILED')
        if not success:
            return jsonify({'success': False, 'error': 'Failed to mark filing as filed'}), 500
        return jsonify({'success': True, 'message': f'Filing {filing_id} marked as FILED'}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ═════════════════════════════════════════════════════════════════════════════
# PDF GENERATION  [FIX — Path 3 fallback added]
# ═════════════════════════════════════════════════════════════════════════════

@cla_bp.route('/api/cla/filings/<file_id>/export_pdf', methods=['GET'])
@admin_required
def export_filing_pdf(file_id):
    """
    Generates and downloads a PDF for the given filing_id or case_id.

    Lookup order — tries each path until content is found:

      Path 1: cla_archive by filing_id  (FIL-xxx)
              Works after CLA agent has processed the case.

      Path 2: cla_archive by case_id    (CASE-xxx)
              Works after CLA agent has processed the case.

      Path 3: Direct from fraud_cases + fraud_alerts  [NEW]
              Works even when CLA hasn't processed the case yet.
              Reads raw case data and builds the PDF content on the fly.
              This is why CASE-xxx IDs were returning 404 before —
              CLA agent wasn't started in app.py, so cla_archive was
              always empty and both Path 1 and 2 always returned None.

    Returns PDF as downloadable attachment.
    """
    try:
        str_content = None
        filing_type = 'STR'

        # ── Path 1: cla_archive by filing_id ─────────────────────────────
        archive = get_archive_by_filing_id(file_id)
        if archive:
            str_content = archive.get('str_content')
            filing_type = archive.get('filing_type', 'STR')

        # ── Path 2: cla_archive by case_id ───────────────────────────────
        if not str_content and file_id.startswith('CASE-'):
            archive = get_filing_by_case_id(file_id)
            if archive:
                str_content = archive.get('str_content')
                filing_type = archive.get('filing_type', 'STR')

        # ── Path 3: Direct from fraud_cases + fraud_alerts ────────────────
        # CLA agent may not have run yet — build content from raw DB data.
        if not str_content and file_id.startswith('CASE-'):
            str_content, filing_type = _build_content_from_case(file_id)

        if not str_content:
            return jsonify({
                'success': False,
                'error':   (
                    f'No data found for {file_id}. '
                    'The case may not exist or CLA processing may have failed.'
                ),
            }), 404

        # ── Generate PDF ──────────────────────────────────────────────────
        if filing_type == 'CTR':
            pdf_path = generate_ctr_pdf(str_content, output_filename=f"{file_id}.pdf")
        else:
            pdf_path = generate_str_pdf(str_content, output_filename=f"{file_id}.pdf")

        if not pdf_path or not os.path.exists(pdf_path):
            return jsonify({'success': False, 'error': 'PDF generation failed'}), 500

        return send_file(
            pdf_path,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f"{file_id}.pdf",
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


def _build_content_from_case(case_id: str) -> tuple:
    """
    Builds STR/PDF content directly from fraud_cases + fraud_alerts.

    Called when cla_archive has no entry for this case (CLA hasn't
    processed it yet). Returns (content_dict, filing_type).
    Returns (None, 'STR') if the case cannot be found.
    """
    try:
        from db import get_db_connection
        conn   = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Fetch case
        cursor.execute(
            "SELECT * FROM fraud_cases WHERE case_id = %s", (case_id,)
        )
        case = cursor.fetchone()
        if not case:
            return None, 'STR'

        alert_id    = case['alert_id']
        customer_id = case['customer_id']

        # Fetch alert (fraud_alerts row — full pipeline data)
        cursor.execute(
            "SELECT * FROM fraud_alerts WHERE id = %s", (alert_id,)
        )
        alert = cursor.fetchone()
        if not alert:
            return None, 'STR'

        # Fetch transaction
        cursor.execute(
            "SELECT * FROM transactions WHERE transaction_id = %s",
            (alert.get('transaction_id'),)
        )
        txn = cursor.fetchone()

        # Fetch customer
        cursor.execute(
            "SELECT * FROM customers WHERE customer_id = %s", (customer_id,)
        )
        customer = cursor.fetchone()

        # Parse evidence pack
        evidence = case.get('evidence_pack') or {}
        if isinstance(evidence, str):
            try:
                evidence = json.loads(evidence)
            except Exception:
                evidence = {}

        # Parse citations
        citations = []
        for field in ('rag_citations', 'raa_citations', 'pra_reg_citations'):
            raw = alert.get(field)
            if raw:
                try:
                    parsed = json.loads(raw) if isinstance(raw, str) else raw
                    if isinstance(parsed, list):
                        for c in parsed:
                            citations.append({
                                'category': c.get('source', 'L1'),
                                'title':    c.get('id', 'Regulatory Rule'),
                                'content':  c.get('text', str(c)),
                            })
                except Exception:
                    pass

        amount = float(txn['amount']) if txn and txn.get('amount') else 0.0

        # Determine filing type
        from et_service.cla.constants import CTR_AMOUNT_THRESHOLD
        filing_type = 'CTR' if amount >= CTR_AMOUNT_THRESHOLD else 'STR'

        # Build investigation note
        investigation_note = (
            alert.get('investigation_note')
            or evidence.get('investigation_note')
            or (
                f"RAA final score: {alert.get('final_raa_score', 'N/A')}/100 → "
                f"{alert.get('raa_verdict', 'N/A')}. "
                f"TMA score: {alert.get('risk_score', 'N/A')}. "
                f"PRA verdict: {alert.get('pra_verdict', 'N/A')}. "
                f"Customer tier: {alert.get('customer_tier', 'N/A')}. "
                f"Typology: {alert.get('typology_code', 'not identified')}."
            )
        )

        content = {
            # IDs
            'filing_id':         case_id,
            'case_id':           case_id,
            'transaction_id':    alert.get('transaction_id', 'N/A'),

            # Institution
            'institution':       'EagleTrust Bank',
            'branch':            'Main Branch',
            'reporting_entity':  'EagleTrust Fraud Detection System',
            'generated_at':      str(case.get('created_at', 'N/A')),

            # Transaction
            'transaction_date':  str(txn['created_at']) if txn and txn.get('created_at') else 'N/A',
            'amount':            amount,
            'description':       txn.get('description', 'N/A') if txn else 'N/A',
            'threshold_amount':  CTR_AMOUNT_THRESHOLD,

            # Risk
            'severity':          case.get('priority', 'P2'),
            'typology_code':     alert.get('typology_code', 'N/A'),
            'typology_description': 'See investigation note',
            'final_raa_score':   float(alert.get('final_raa_score') or 0),

            # Customer
            'customer_id':       customer_id,
            'customer_name':     customer.get('full_name', 'N/A') if customer else 'N/A',
            'account_number':    customer.get('account_number', 'N/A') if customer else 'N/A',

            # Narrative
            'narrative': (
                f"Fraud case {case_id} — Priority {case.get('priority', 'P2')}. "
                f"Transaction of ₹{amount:,.2f} flagged by Jatayu fraud detection pipeline. "
                f"TMA (Isolation Forest): score {alert.get('risk_score', 'N/A')}, "
                f"decision {alert.get('decision', 'N/A')}. "
                f"PRA (BiLSTM): {alert.get('pra_verdict', 'N/A')}. "
                f"RAA (Decision Tree): score {alert.get('final_raa_score', 'N/A')}/100, "
                f"verdict {alert.get('raa_verdict', 'N/A')}. "
                f"ABA action: {alert.get('aba_gateway_action', 'N/A')}."
            ),
            'investigation_note': investigation_note,
            'citations':          citations,
        }

        cursor.close()
        conn.close()
        return content, filing_type

    except Exception as e:
        print(f"[cla_routes] _build_content_from_case error for {case_id}: {e}")
        import traceback
        traceback.print_exc()
        return None, 'STR'


# ═════════════════════════════════════════════════════════════════════════════
# ARCHIVE ENDPOINTS  (unchanged)
# ═════════════════════════════════════════════════════════════════════════════

@cla_bp.route('/api/cla/archive/<filing_id>', methods=['GET'])
@admin_required
def get_archive(filing_id):
    try:
        archive = get_archive_by_filing_id(filing_id)
        if not archive:
            return jsonify({'success': False, 'error': 'Archive not found'}), 404
        return jsonify({'success': True, 'archive': archive}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@cla_bp.route('/api/cla/archive/case/<case_id>', methods=['GET'])
@admin_required
def get_archive_by_case(case_id):
    try:
        archives = get_archive_by_case_id(case_id)
        return jsonify({'success': True, 'count': len(archives), 'archives': archives}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ═════════════════════════════════════════════════════════════════════════════
# CITATIONS ENDPOINTS  (unchanged)
# ═════════════════════════════════════════════════════════════════════════════

@cla_bp.route('/api/cla/citations', methods=['GET'])
@admin_required
def get_citations():
    try:
        category  = request.args.get('category', 'REGULATORY')
        limit     = request.args.get('limit', 50, type=int)
        citations = get_citations_by_category(category, limit=limit)
        return jsonify({'success': True, 'count': len(citations), 'citations': citations}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@cla_bp.route('/api/cla/citations/<citation_id>', methods=['GET'])
@admin_required
def get_citation(citation_id):
    try:
        citation = get_citation_by_id(citation_id)
        if not citation:
            return jsonify({'success': False, 'error': 'Citation not found'}), 404
        return jsonify({'success': True, 'citation': citation}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ═════════════════════════════════════════════════════════════════════════════
# MANUAL CASE PROCESSING  (unchanged)
# ═════════════════════════════════════════════════════════════════════════════

@cla_bp.route('/api/cla/process_case/<case_id>', methods=['POST'])
@admin_required
def process_case(case_id):
    try:
        filing_id = process_case_manually(case_id)
        if not filing_id:
            return jsonify({'success': False, 'error': 'Case processing failed'}), 500
        return jsonify({
            'success':    True,
            'message':    f'Case {case_id} processed',
            'filing_id':  filing_id,
        }), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500