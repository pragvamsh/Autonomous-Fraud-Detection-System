"""
PDF Generator — Exports STR/CTR documents as formatted PDFs

Generates regulatory-compliant PDF reports from STR/CTR JSON content.
Uses reportlab for PDF generation with professional formatting.
"""

import os
from datetime import datetime
from typing import Dict, Any, Optional

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image
    )
    from reportlab.lib import colors
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False
    print("[pdf_generator] WARNING: reportlab not installed. PDF generation disabled.")

from et_service.cla.constants import PDF_OUTPUT_DIR
from et_service.cla.term_glossary import (
    translate_anomaly_flag,
    translate_typology,
    get_verdict_info,
    get_score_explanation,
    AGENT_EXPLANATIONS,
)

# ═══════════════════════════════════════════════════════════════════════════════
# BRAND COLORS — Consistent with customer-facing pages
# ═══════════════════════════════════════════════════════════════════════════════

PDF_COLORS = {
    'header_bg': '#7f5539',       # Brown primary
    'header_text': '#e6ccb2',     # Cream text on brown
    'section_bg': '#ede0d4',      # Light cream for sections
    'section_alt_bg': '#e6ccb2',  # Alternate cream
    'body_text': '#3d2e1f',       # Dark brown for body
    'accent': '#9c6644',          # Brown mid for accents
    'success': '#4caf50',         # Green
    'warning': '#F5A623',         # Gold/Yellow (FLAG)
    'alert': '#F6AD55',           # Orange (ALERT)
    'danger': '#E53E3E',          # Red (BLOCK)
    'info': '#805AD5',            # Purple
}


def generate_str_pdf(
    str_content: Dict[str, Any],
    output_filename: Optional[str] = None
) -> Optional[str]:
    """
    Generates a PDF document from STR content.

    Args:
        str_content: STR document dict from str_assembler
        output_filename: Optional custom filename (default: {filing_id}.pdf)

    Returns:
        Full path to generated PDF, or None on failure
    """
    if not REPORTLAB_AVAILABLE:
        print("[pdf_generator] Cannot generate PDF - reportlab not installed")
        return None

    try:
        # Determine output path
        filing_id = str_content.get('filing_id', 'UNKNOWN')
        if not output_filename:
            output_filename = f"{filing_id}.pdf"
        output_path = os.path.join(PDF_OUTPUT_DIR, output_filename)

        # Create PDF
        doc = SimpleDocTemplate(
            output_path,
            pagesize=A4,
            rightMargin=0.75*inch,
            leftMargin=0.75*inch,
            topMargin=0.75*inch,
            bottomMargin=0.75*inch
        )

        # Build content
        story = []
        styles = getSampleStyleSheet()

        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            textColor=colors.HexColor('#1a237e'),
            spaceAfter=12,
            alignment=TA_CENTER
        )

        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#283593'),
            spaceAfter=8,
            spaceBefore=12
        )

        body_style = ParagraphStyle(
            'CustomBody',
            parent=styles['BodyText'],
            fontSize=10,
            alignment=TA_JUSTIFY,
            spaceAfter=6
        )

        # Title
        story.append(Paragraph("SUSPICIOUS TRANSACTION REPORT (STR)", title_style))
        story.append(Spacer(1, 0.2*inch))

        # Institution header
        institution_data = [
            ['Institution:', str_content.get('institution', 'N/A')],
            ['Branch:', str_content.get('branch', 'N/A')],
            ['Reporting Entity:', str_content.get('reporting_entity', 'N/A')],
            ['Filing Date:', datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')]
        ]

        institution_table = Table(institution_data, colWidths=[2*inch, 4*inch])
        institution_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#e8eaf6')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
        ]))

        story.append(institution_table)
        story.append(Spacer(1, 0.3*inch))

        # Transaction Details
        story.append(Paragraph("Transaction Details", heading_style))

        transaction_data = [
            ['Filing ID:', str_content.get('filing_id', 'N/A')],
            ['Case ID:', str_content.get('case_id', 'N/A')],
            ['Transaction ID:', str_content.get('transaction_id', 'N/A')],
            ['Transaction Date:', str_content.get('transaction_date', 'N/A')],
            ['Amount:', f"₹{str_content.get('amount', 0):,.2f}"],
            ['Description:', str_content.get('description', 'N/A')],
            ['Severity:', str_content.get('severity', 'N/A')],
            ['Typology Code:', f"{str_content.get('typology_code', 'N/A')} - {str_content.get('typology_description', 'N/A')}"]
        ]

        transaction_table = Table(transaction_data, colWidths=[2*inch, 4*inch])
        transaction_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#fff3e0')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
        ]))

        story.append(transaction_table)
        story.append(Spacer(1, 0.3*inch))

        # Customer Information
        story.append(Paragraph("Customer Information", heading_style))

        customer_data = [
            ['Customer ID:', str_content.get('customer_id', 'N/A')],
            ['Customer Name:', str_content.get('customer_name', 'N/A')],
            ['Account Number:', str_content.get('account_number', 'N/A')]
        ]

        customer_table = Table(customer_data, colWidths=[2*inch, 4*inch])
        customer_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#e0f2f1')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
        ]))

        story.append(customer_table)
        story.append(Spacer(1, 0.3*inch))

        # Narrative
        story.append(Paragraph("Narrative", heading_style))
        narrative_text = str_content.get('narrative', 'No narrative provided.')
        story.append(Paragraph(narrative_text, body_style))
        story.append(Spacer(1, 0.2*inch))

        # Investigation Note
        story.append(Paragraph("Investigation Note", heading_style))
        investigation_note = str_content.get('investigation_note', 'N/A')
        story.append(Paragraph(investigation_note, body_style))
        story.append(Spacer(1, 0.2*inch))

        # Citations
        story.append(Paragraph("Supporting Citations", heading_style))
        citations = str_content.get('citations', [])

        if citations:
            for idx, citation in enumerate(citations, 1):
                citation_text = (
                    f"<b>[{idx}] {citation.get('category', 'N/A')}</b> - "
                    f"{citation.get('title', 'N/A')}<br/>"
                    f"<i>{citation.get('content', 'N/A')}</i>"
                )
                story.append(Paragraph(citation_text, body_style))
                story.append(Spacer(1, 0.1*inch))
        else:
            story.append(Paragraph("No citations available.", body_style))

        story.append(Spacer(1, 0.3*inch))

        # Risk Score
        story.append(Paragraph("Risk Assessment", heading_style))
        risk_text = f"Final Risk Score: <b>{str_content.get('final_raa_score', 0):.2f}/100</b>"
        story.append(Paragraph(risk_text, body_style))

        # Footer
        story.append(Spacer(1, 0.5*inch))
        footer_style = ParagraphStyle(
            'Footer',
            parent=styles['Normal'],
            fontSize=8,
            textColor=colors.grey,
            alignment=TA_CENTER
        )
        footer_text = (
            f"Generated by EagleTrust Fraud Detection System - CLA Module<br/>"
            f"Generation Time: {str_content.get('generated_at', 'N/A')}<br/>"
            f"This document is confidential and intended for authorized personnel only."
        )
        story.append(Paragraph(footer_text, footer_style))

        # Build PDF
        doc.build(story)

        print(f"[pdf_generator] ✅ PDF generated: {output_path}")
        return output_path

    except Exception as e:
        print(f"[pdf_generator] Error generating PDF: {e}")
        import traceback
        traceback.print_exc()
        return None


def generate_ctr_pdf(
    ctr_content: Dict[str, Any],
    output_filename: Optional[str] = None
) -> Optional[str]:
    """
    Generates a PDF document from CTR content.

    Args:
        ctr_content: CTR document dict from str_assembler
        output_filename: Optional custom filename (default: {filing_id}.pdf)

    Returns:
        Full path to generated PDF, or None on failure
    """
    if not REPORTLAB_AVAILABLE:
        print("[pdf_generator] Cannot generate PDF - reportlab not installed")
        return None

    try:
        # Determine output path
        filing_id = ctr_content.get('filing_id', 'UNKNOWN')
        if not output_filename:
            output_filename = f"{filing_id}.pdf"
        output_path = os.path.join(PDF_OUTPUT_DIR, output_filename)

        # Create PDF (similar structure to STR, but simpler)
        doc = SimpleDocTemplate(
            output_path,
            pagesize=A4,
            rightMargin=0.75*inch,
            leftMargin=0.75*inch,
            topMargin=0.75*inch,
            bottomMargin=0.75*inch
        )

        story = []
        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            textColor=colors.HexColor('#1a237e'),
            spaceAfter=12,
            alignment=TA_CENTER
        )

        story.append(Paragraph("CASH TRANSACTION REPORT (CTR)", title_style))
        story.append(Spacer(1, 0.2*inch))

        # Institution and transaction details
        report_data = [
            ['Institution:', ctr_content.get('institution', 'N/A')],
            ['Threshold Amount:', f"₹{ctr_content.get('threshold_amount', 0):,.2f}"],
            ['Filing ID:', ctr_content.get('filing_id', 'N/A')],
            ['Transaction ID:', ctr_content.get('transaction_id', 'N/A')],
            ['Transaction Date:', ctr_content.get('transaction_date', 'N/A')],
            ['Amount:', f"₹{ctr_content.get('amount', 0):,.2f}"],
            ['Customer ID:', ctr_content.get('customer_id', 'N/A')],
            ['Customer Name:', ctr_content.get('customer_name', 'N/A')],
            ['Account Number:', ctr_content.get('account_number', 'N/A')]
        ]

        report_table = Table(report_data, colWidths=[2*inch, 4*inch])
        report_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#e8eaf6')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
        ]))

        story.append(report_table)
        story.append(Spacer(1, 0.3*inch))

        # Narrative
        body_style = ParagraphStyle(
            'CustomBody',
            parent=styles['BodyText'],
            fontSize=10,
            alignment=TA_JUSTIFY
        )
        narrative = ctr_content.get('narrative', 'N/A')
        story.append(Paragraph(narrative, body_style))

        # Build PDF
        doc.build(story)

        print(f"[pdf_generator] ✅ CTR PDF generated: {output_path}")
        return output_path

    except Exception as e:
        print(f"[pdf_generator] Error generating CTR PDF: {e}")
        import traceback
        traceback.print_exc()
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# ALERT PDF — Comprehensive fraud alert report for admin dashboard
# ═══════════════════════════════════════════════════════════════════════════════

def generate_alert_pdf(
    alert_data: Dict[str, Any],
    customer_data: Dict[str, Any],
    transaction_data: Dict[str, Any],
    output_filename: Optional[str] = None
) -> Optional[str]:
    """
    Generates a user-friendly Alert Report PDF.

    Sections:
    1. Header with Jatayu branding
    2. Summary (verdict badge, risk score, amount)
    3. Customer Information
    4. Transaction Details
    5. Risk Assessment Breakdown (TMA/PRA/RAA)
    6. Detected Anomalies (translated to plain English)
    7. Typology Classification
    8. Supporting Citations
    9. Glossary of Terms
    10. Footer

    Args:
        alert_data: Dict from fraud_alerts table
        customer_data: Dict from customers table
        transaction_data: Dict from payment_transactions table
        output_filename: Optional custom filename

    Returns:
        Full path to generated PDF, or None on failure
    """
    if not REPORTLAB_AVAILABLE:
        print("[pdf_generator] Cannot generate PDF - reportlab not installed")
        return None

    try:
        import json

        # Determine output path
        alert_id = alert_data.get('id') or alert_data.get('alert_id', 'UNKNOWN')
        if not output_filename:
            output_filename = f"ALERT-{alert_id}.pdf"
        output_path = os.path.join(PDF_OUTPUT_DIR, output_filename)

        # Create PDF
        doc = SimpleDocTemplate(
            output_path,
            pagesize=A4,
            rightMargin=0.75*inch,
            leftMargin=0.75*inch,
            topMargin=0.75*inch,
            bottomMargin=0.75*inch
        )

        story = []
        styles = getSampleStyleSheet()

        # ─────────────────────────────────────────────────────────────────────
        # Custom Styles with Brand Colors
        # ─────────────────────────────────────────────────────────────────────

        title_style = ParagraphStyle(
            'AlertTitle',
            parent=styles['Heading1'],
            fontSize=20,
            textColor=colors.HexColor(PDF_COLORS['header_bg']),
            spaceAfter=6,
            alignment=TA_CENTER
        )

        subtitle_style = ParagraphStyle(
            'AlertSubtitle',
            parent=styles['Normal'],
            fontSize=11,
            textColor=colors.HexColor(PDF_COLORS['accent']),
            spaceAfter=12,
            alignment=TA_CENTER
        )

        heading_style = ParagraphStyle(
            'SectionHeading',
            parent=styles['Heading2'],
            fontSize=13,
            textColor=colors.HexColor(PDF_COLORS['header_bg']),
            spaceAfter=8,
            spaceBefore=16
        )

        body_style = ParagraphStyle(
            'BodyText',
            parent=styles['BodyText'],
            fontSize=10,
            textColor=colors.HexColor(PDF_COLORS['body_text']),
            alignment=TA_JUSTIFY,
            spaceAfter=6
        )

        small_style = ParagraphStyle(
            'SmallText',
            parent=styles['Normal'],
            fontSize=9,
            textColor=colors.HexColor(PDF_COLORS['body_text']),
            spaceAfter=4
        )

        # ─────────────────────────────────────────────────────────────────────
        # 1. HEADER
        # ─────────────────────────────────────────────────────────────────────

        story.append(Paragraph("JATAYU FRAUD DETECTION SYSTEM", title_style))
        story.append(Paragraph("Fraud Alert Report", subtitle_style))
        story.append(Spacer(1, 0.1*inch))

        # Alert ID and timestamp
        alert_meta = [
            ['Alert ID:', f"#{alert_id}"],
            ['Generated:', datetime.utcnow().strftime('%d %B %Y, %H:%M:%S UTC')],
        ]
        meta_table = Table(alert_meta, colWidths=[1.2*inch, 4.5*inch])
        meta_table.setStyle(TableStyle([
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor(PDF_COLORS['accent'])),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ]))
        story.append(meta_table)
        story.append(Spacer(1, 0.2*inch))

        # ─────────────────────────────────────────────────────────────────────
        # 2. SUMMARY BOX
        # ─────────────────────────────────────────────────────────────────────

        verdict = alert_data.get('decision', 'UNKNOWN')
        verdict_info = get_verdict_info(verdict)
        final_score = alert_data.get('final_raa_score') or alert_data.get('risk_score', 0)
        amount = transaction_data.get('amount', 0)

        summary_data = [
            ['Verdict', 'Risk Score', 'Transaction Amount'],
            [verdict, f"{final_score:.1f} / 100", f"Rs {amount:,.2f}"],
        ]

        # Determine verdict color
        verdict_color_map = {
            'ALLOW': PDF_COLORS['success'],
            'FLAG': PDF_COLORS['warning'],
            'ALERT': PDF_COLORS['alert'],
            'BLOCK': PDF_COLORS['danger'],
        }
        verdict_color = verdict_color_map.get(verdict, PDF_COLORS['info'])

        summary_table = Table(summary_data, colWidths=[2*inch, 2*inch, 2*inch])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(PDF_COLORS['section_bg'])),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor(PDF_COLORS['body_text'])),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('FONTSIZE', (0, 1), (-1, 1), 14),
            ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'),
            ('TEXTCOLOR', (0, 1), (0, 1), colors.HexColor(verdict_color)),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor(PDF_COLORS['accent'])),
        ]))
        story.append(summary_table)
        story.append(Spacer(1, 0.1*inch))

        # Verdict explanation
        story.append(Paragraph(f"<b>{verdict_info['title']}:</b> {verdict_info['description']}", small_style))
        story.append(Spacer(1, 0.2*inch))

        # ─────────────────────────────────────────────────────────────────────
        # 3. CUSTOMER INFORMATION
        # ─────────────────────────────────────────────────────────────────────

        story.append(Paragraph("Customer Information", heading_style))

        customer_table_data = [
            ['Customer ID:', customer_data.get('customer_id', 'N/A')],
            ['Customer Name:', customer_data.get('full_name', 'N/A')],
            ['Account Number:', customer_data.get('account_number', 'N/A')],
            ['Risk Tier:', alert_data.get('customer_tier', 'STANDARD')],
            ['Account Status:', 'FROZEN' if customer_data.get('is_frozen') else 'Active'],
        ]

        customer_table = Table(customer_table_data, colWidths=[2*inch, 4*inch])
        customer_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor(PDF_COLORS['section_bg'])),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor(PDF_COLORS['body_text'])),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor(PDF_COLORS['accent'])),
        ]))
        story.append(customer_table)
        story.append(Spacer(1, 0.2*inch))

        # ─────────────────────────────────────────────────────────────────────
        # 4. TRANSACTION DETAILS
        # ─────────────────────────────────────────────────────────────────────

        story.append(Paragraph("Transaction Details", heading_style))

        txn_date = transaction_data.get('created_at') or transaction_data.get('timestamp', 'N/A')
        if hasattr(txn_date, 'strftime'):
            txn_date = txn_date.strftime('%d %B %Y, %H:%M:%S')

        txn_table_data = [
            ['Transaction ID:', transaction_data.get('debit_transaction_id') or alert_data.get('transaction_id', 'N/A')],
            ['Date & Time:', str(txn_date)],
            ['Amount:', f"Rs {amount:,.2f}"],
            ['Description:', transaction_data.get('description', 'Fund Transfer')],
            ['Recipient:', transaction_data.get('recipient_account', 'N/A')],
        ]

        txn_table = Table(txn_table_data, colWidths=[2*inch, 4*inch])
        txn_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor(PDF_COLORS['section_alt_bg'])),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor(PDF_COLORS['body_text'])),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor(PDF_COLORS['accent'])),
        ]))
        story.append(txn_table)
        story.append(Spacer(1, 0.2*inch))

        # ─────────────────────────────────────────────────────────────────────
        # 5. RISK ASSESSMENT BREAKDOWN
        # ─────────────────────────────────────────────────────────────────────

        story.append(Paragraph("Risk Assessment Breakdown", heading_style))

        tma_score = alert_data.get('risk_score', 0)
        pra_verdict = alert_data.get('pra_verdict', 'N/A')
        pattern_score = alert_data.get('pattern_score', 0)
        bilstm_score = alert_data.get('bilstm_score', 0)
        raa_verdict = alert_data.get('raa_verdict', verdict)

        risk_breakdown = [
            ['Stage', 'Score/Verdict', 'Description'],
            ['TMA (Anomaly Detection)', f"{tma_score:.1f}/100", 'Initial transaction analysis'],
            ['PRA (Pattern Analysis)', pra_verdict or 'N/A', f"Pattern: {pattern_score:.1f}, BiLSTM: {bilstm_score:.1f}"],
            ['RAA (Final Assessment)', f"{final_score:.1f}/100", f"Final verdict: {raa_verdict}"],
        ]

        risk_table = Table(risk_breakdown, colWidths=[2.2*inch, 1.5*inch, 2.3*inch])
        risk_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(PDF_COLORS['header_bg'])),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor(PDF_COLORS['header_text'])),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor(PDF_COLORS['section_bg'])),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor(PDF_COLORS['body_text'])),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ALIGN', (1, 0), (1, -1), 'CENTER'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor(PDF_COLORS['accent'])),
        ]))
        story.append(risk_table)
        story.append(Spacer(1, 0.2*inch))

        # ─────────────────────────────────────────────────────────────────────
        # 6. DETECTED ANOMALIES (Translated)
        # ─────────────────────────────────────────────────────────────────────

        story.append(Paragraph("Detected Anomalies", heading_style))

        anomaly_flags = alert_data.get('anomaly_flags', [])
        if isinstance(anomaly_flags, str):
            try:
                anomaly_flags = json.loads(anomaly_flags)
            except:
                anomaly_flags = []

        if anomaly_flags:
            for flag in anomaly_flags:
                translated = translate_anomaly_flag(flag)
                severity_color = {
                    'HIGH': PDF_COLORS['danger'],
                    'MEDIUM': PDF_COLORS['warning'],
                    'LOW': PDF_COLORS['accent'],
                }.get(translated['severity'], PDF_COLORS['accent'])

                anomaly_text = (
                    f"<font color='{severity_color}'><b>{translated['title']}</b></font><br/>"
                    f"<font size='9'>{translated['description']}</font>"
                )
                story.append(Paragraph(anomaly_text, body_style))
                story.append(Spacer(1, 0.05*inch))
        else:
            story.append(Paragraph("No specific anomaly flags were recorded for this transaction.", small_style))

        story.append(Spacer(1, 0.15*inch))

        # ─────────────────────────────────────────────────────────────────────
        # 7. TYPOLOGY CLASSIFICATION
        # ─────────────────────────────────────────────────────────────────────

        typology_code = alert_data.get('typology_code')
        if typology_code:
            story.append(Paragraph("Typology Classification", heading_style))

            typology_info = translate_typology(typology_code)
            typology_text = (
                f"<b>{typology_code}: {typology_info['name']}</b><br/><br/>"
                f"{typology_info['explanation']}"
            )
            story.append(Paragraph(typology_text, body_style))
            story.append(Spacer(1, 0.15*inch))

        # ─────────────────────────────────────────────────────────────────────
        # 8. INVESTIGATION NOTE
        # ─────────────────────────────────────────────────────────────────────

        investigation_note = alert_data.get('investigation_note')
        if investigation_note:
            story.append(Paragraph("Investigation Note", heading_style))
            story.append(Paragraph(investigation_note, body_style))
            story.append(Spacer(1, 0.15*inch))

        # ─────────────────────────────────────────────────────────────────────
        # 9. GLOSSARY OF TERMS
        # ─────────────────────────────────────────────────────────────────────

        story.append(Paragraph("Glossary of Terms", heading_style))

        for agent_key in ['TMA', 'PRA', 'RAA']:
            agent_info = AGENT_EXPLANATIONS.get(agent_key, {})
            glossary_text = (
                f"<b>{agent_key} ({agent_info.get('name', agent_key)}):</b> "
                f"{agent_info.get('description', 'N/A')}"
            )
            story.append(Paragraph(glossary_text, small_style))
            story.append(Spacer(1, 0.03*inch))

        story.append(Spacer(1, 0.2*inch))

        # ─────────────────────────────────────────────────────────────────────
        # 10. FOOTER
        # ─────────────────────────────────────────────────────────────────────

        footer_style = ParagraphStyle(
            'Footer',
            parent=styles['Normal'],
            fontSize=8,
            textColor=colors.HexColor(PDF_COLORS['accent']),
            alignment=TA_CENTER
        )

        story.append(Spacer(1, 0.3*inch))
        footer_text = (
            "Generated by Jatayu Fraud Detection System | EagleTrust Bank<br/>"
            "This document is confidential and intended for authorized personnel only.<br/>"
            f"Report generated on {datetime.utcnow().strftime('%d %B %Y at %H:%M:%S UTC')}"
        )
        story.append(Paragraph(footer_text, footer_style))

        # Build PDF
        doc.build(story)

        print(f"[pdf_generator] ✅ Alert PDF generated: {output_path}")
        return output_path

    except Exception as e:
        print(f"[pdf_generator] Error generating Alert PDF: {e}")
        import traceback
        traceback.print_exc()
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# BLOCK PDF — Account freeze/block report
# ═══════════════════════════════════════════════════════════════════════════════

def generate_block_pdf(
    customer_data: Dict[str, Any],
    alert_data: Dict[str, Any],
    freeze_data: Dict[str, Any],
    output_filename: Optional[str] = None
) -> Optional[str]:
    """
    Generates an Account Freeze/Block Report PDF.

    Sections:
    1. Header with Jatayu branding
    2. Account Status Summary (FROZEN badge)
    3. Customer Information
    4. Freeze Justification
    5. Triggering Transaction Details
    6. Actions Taken
    7. Next Steps / Contact Information
    8. Footer

    Args:
        customer_data: Dict from customers table
        alert_data: Dict from fraud_alerts table (triggering alert)
        freeze_data: Freeze details (frozen_at, frozen_reason, etc.)
        output_filename: Optional custom filename

    Returns:
        Full path to generated PDF, or None on failure
    """
    if not REPORTLAB_AVAILABLE:
        print("[pdf_generator] Cannot generate PDF - reportlab not installed")
        return None

    try:
        import json

        # Determine output path
        customer_id = customer_data.get('customer_id', 'UNKNOWN')
        if not output_filename:
            timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
            output_filename = f"BLOCK-{customer_id}-{timestamp}.pdf"
        output_path = os.path.join(PDF_OUTPUT_DIR, output_filename)

        # Create PDF
        doc = SimpleDocTemplate(
            output_path,
            pagesize=A4,
            rightMargin=0.75*inch,
            leftMargin=0.75*inch,
            topMargin=0.75*inch,
            bottomMargin=0.75*inch
        )

        story = []
        styles = getSampleStyleSheet()

        # ─────────────────────────────────────────────────────────────────────
        # Custom Styles
        # ─────────────────────────────────────────────────────────────────────

        title_style = ParagraphStyle(
            'BlockTitle',
            parent=styles['Heading1'],
            fontSize=20,
            textColor=colors.HexColor(PDF_COLORS['danger']),
            spaceAfter=6,
            alignment=TA_CENTER
        )

        subtitle_style = ParagraphStyle(
            'BlockSubtitle',
            parent=styles['Normal'],
            fontSize=11,
            textColor=colors.HexColor(PDF_COLORS['accent']),
            spaceAfter=12,
            alignment=TA_CENTER
        )

        heading_style = ParagraphStyle(
            'SectionHeading',
            parent=styles['Heading2'],
            fontSize=13,
            textColor=colors.HexColor(PDF_COLORS['header_bg']),
            spaceAfter=8,
            spaceBefore=16
        )

        body_style = ParagraphStyle(
            'BodyText',
            parent=styles['BodyText'],
            fontSize=10,
            textColor=colors.HexColor(PDF_COLORS['body_text']),
            alignment=TA_JUSTIFY,
            spaceAfter=6
        )

        small_style = ParagraphStyle(
            'SmallText',
            parent=styles['Normal'],
            fontSize=9,
            textColor=colors.HexColor(PDF_COLORS['body_text']),
            spaceAfter=4
        )

        # ─────────────────────────────────────────────────────────────────────
        # 1. HEADER
        # ─────────────────────────────────────────────────────────────────────

        story.append(Paragraph("ACCOUNT FREEZE NOTICE", title_style))
        story.append(Paragraph("Jatayu Fraud Detection System", subtitle_style))
        story.append(Spacer(1, 0.2*inch))

        # ─────────────────────────────────────────────────────────────────────
        # 2. ACCOUNT STATUS SUMMARY
        # ─────────────────────────────────────────────────────────────────────

        frozen_at = freeze_data.get('frozen_at', 'N/A')
        if hasattr(frozen_at, 'strftime'):
            frozen_at = frozen_at.strftime('%d %B %Y, %H:%M:%S')

        status_data = [
            ['Account Status', 'Frozen Since', 'Triggering Alert'],
            ['FROZEN', str(frozen_at), f"#{freeze_data.get('frozen_by_alert_id', 'N/A')}"],
        ]

        status_table = Table(status_data, colWidths=[2*inch, 2.5*inch, 1.5*inch])
        status_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(PDF_COLORS['section_bg'])),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor(PDF_COLORS['body_text'])),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('FONTSIZE', (0, 1), (-1, 1), 12),
            ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'),
            ('TEXTCOLOR', (0, 1), (0, 1), colors.HexColor(PDF_COLORS['danger'])),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor(PDF_COLORS['danger'])),
        ]))
        story.append(status_table)
        story.append(Spacer(1, 0.2*inch))

        # ─────────────────────────────────────────────────────────────────────
        # 3. CUSTOMER INFORMATION
        # ─────────────────────────────────────────────────────────────────────

        story.append(Paragraph("Customer Information", heading_style))

        customer_table_data = [
            ['Customer ID:', customer_data.get('customer_id', 'N/A')],
            ['Customer Name:', customer_data.get('full_name', 'N/A')],
            ['Account Number:', customer_data.get('account_number', 'N/A')],
        ]

        customer_table = Table(customer_table_data, colWidths=[2*inch, 4*inch])
        customer_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor(PDF_COLORS['section_bg'])),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor(PDF_COLORS['body_text'])),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor(PDF_COLORS['accent'])),
        ]))
        story.append(customer_table)
        story.append(Spacer(1, 0.2*inch))

        # ─────────────────────────────────────────────────────────────────────
        # 4. FREEZE JUSTIFICATION
        # ─────────────────────────────────────────────────────────────────────

        story.append(Paragraph("Freeze Justification", heading_style))

        frozen_reason = freeze_data.get('frozen_reason', 'High-risk activity detected')

        # Translate the reason to user-friendly text
        reason_explanations = {
            'BLOCK verdict': 'The fraud detection system identified this transaction as high-risk and automatically blocked it to protect the account.',
            'ABA_FREEZE_ACCOUNT': 'The Action & Blocking Agent determined that the account should be frozen due to detected fraudulent activity patterns.',
            'Multiple BLOCK verdicts': 'Multiple high-risk transactions were detected, triggering an automatic account freeze.',
        }

        explanation = reason_explanations.get(frozen_reason, frozen_reason)

        story.append(Paragraph(f"<b>Reason:</b> {frozen_reason}", body_style))
        story.append(Paragraph(f"<b>What this means:</b> {explanation}", body_style))
        story.append(Spacer(1, 0.15*inch))

        # ─────────────────────────────────────────────────────────────────────
        # 5. TRIGGERING TRANSACTION (if alert_data available)
        # ─────────────────────────────────────────────────────────────────────

        if alert_data:
            story.append(Paragraph("Triggering Transaction", heading_style))

            verdict_info = get_verdict_info(alert_data.get('decision', 'BLOCK'))
            final_score = alert_data.get('final_raa_score') or alert_data.get('risk_score', 0)

            trigger_data = [
                ['Alert ID:', f"#{alert_data.get('id', 'N/A')}"],
                ['Transaction ID:', alert_data.get('transaction_id', 'N/A')],
                ['Verdict:', alert_data.get('decision', 'BLOCK')],
                ['Risk Score:', f"{final_score:.1f} / 100"],
                ['Typology:', alert_data.get('typology_code', 'N/A')],
            ]

            trigger_table = Table(trigger_data, colWidths=[2*inch, 4*inch])
            trigger_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), colors.HexColor(PDF_COLORS['section_alt_bg'])),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor(PDF_COLORS['body_text'])),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor(PDF_COLORS['accent'])),
            ]))
            story.append(trigger_table)
            story.append(Spacer(1, 0.1*inch))

            story.append(Paragraph(f"<i>{verdict_info['description']}</i>", small_style))
            story.append(Spacer(1, 0.15*inch))

        # ─────────────────────────────────────────────────────────────────────
        # 6. ACTIONS TAKEN
        # ─────────────────────────────────────────────────────────────────────

        story.append(Paragraph("Actions Taken", heading_style))

        actions = [
            "Account frozen — all outgoing transactions blocked",
            "Fraud case created for investigation",
        ]

        if alert_data:
            aba_action = alert_data.get('aba_gateway_action')
            if aba_action:
                actions.append(f"Gateway action: {aba_action}")

            case_id = alert_data.get('aba_case_id')
            if case_id:
                actions.append(f"Fraud case ID: {case_id}")

            if alert_data.get('str_required'):
                actions.append("Suspicious Transaction Report (STR) flagged for filing")

            if alert_data.get('ctr_flag'):
                actions.append("Cash Transaction Report (CTR) flagged")

        for action in actions:
            story.append(Paragraph(f"• {action}", body_style))

        story.append(Spacer(1, 0.2*inch))

        # ─────────────────────────────────────────────────────────────────────
        # 7. NEXT STEPS
        # ─────────────────────────────────────────────────────────────────────

        story.append(Paragraph("Next Steps", heading_style))

        next_steps_text = """
        <b>For the Account Holder:</b><br/>
        If you believe this freeze was made in error, please contact our fraud investigation
        team immediately with valid identification documents. An investigation will be conducted,
        and if the activity is verified as legitimate, your account will be unfrozen.<br/><br/>

        <b>For Bank Personnel:</b><br/>
        This account requires manual review. Check the fraud case details, verify customer
        identity, and assess the legitimacy of the flagged transactions before unfreezing.
        """
        story.append(Paragraph(next_steps_text, body_style))
        story.append(Spacer(1, 0.2*inch))

        # ─────────────────────────────────────────────────────────────────────
        # 8. FOOTER
        # ─────────────────────────────────────────────────────────────────────

        footer_style = ParagraphStyle(
            'Footer',
            parent=styles['Normal'],
            fontSize=8,
            textColor=colors.HexColor(PDF_COLORS['accent']),
            alignment=TA_CENTER
        )

        story.append(Spacer(1, 0.3*inch))
        footer_text = (
            "Generated by Jatayu Fraud Detection System | EagleTrust Bank<br/>"
            "This document is confidential and intended for authorized personnel only.<br/>"
            f"Report generated on {datetime.utcnow().strftime('%d %B %Y at %H:%M:%S UTC')}"
        )
        story.append(Paragraph(footer_text, footer_style))

        # Build PDF
        doc.build(story)

        print(f"[pdf_generator] ✅ Block PDF generated: {output_path}")
        return output_path

    except Exception as e:
        print(f"[pdf_generator] Error generating Block PDF: {e}")
        import traceback
        traceback.print_exc()
        return None
