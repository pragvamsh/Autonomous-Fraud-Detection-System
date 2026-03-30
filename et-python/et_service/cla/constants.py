"""
CLA Constants — Configuration for Citation & Legal Archive Agent

Defines thresholds, scoring weights, and citation mapping for STR generation.
"""

# ═════════════════════════════════════════════════════════════════════════════
# FILING THRESHOLDS
# ═════════════════════════════════════════════════════════════════════════════

STR_AUTO_THRESHOLD = 85    # Auto-file STR if final_raa_score >= 85
STR_APPROVAL_THRESHOLD = 70  # Require approval if 70 <= score < 85
CTR_AMOUNT_THRESHOLD = 200000.00  # ₹2,00,000 — auto CTR filing

# ═════════════════════════════════════════════════════════════════════════════
# CITATION CATEGORIES
# ═════════════════════════════════════════════════════════════════════════════

CITATION_CATEGORIES = {
    'REGULATORY': 'L1',   # Regulatory rules from L1_regulatory
    'PRECEDENT': 'L2',    # Fraud case precedents from L2_fraud_cases
    'TYPOLOGY': 'L3'      # Fraud typologies from L3_typologies
}

# ═════════════════════════════════════════════════════════════════════════════
# STR SEVERITY MAPPING
# ═════════════════════════════════════════════════════════════════════════════

def get_severity_from_score(score: float) -> str:
    """
    Maps RAA score to STR severity level.
    """
    if score >= 90:
        return 'CRITICAL'
    elif score >= 75:
        return 'HIGH'
    elif score >= 60:
        return 'MEDIUM'
    else:
        return 'LOW'

# ═════════════════════════════════════════════════════════════════════════════
# TYPOLOGY CODES (FATF FIU-IND)
# ═════════════════════════════════════════════════════════════════════════════

TYPOLOGY_CODES = {
    'TY-001': 'Structuring / Smurfing',
    'TY-002': 'Rapid Movement of Funds',
    'TY-003': 'High-Risk Jurisdiction Transfers',
    'TY-004': 'Unusual Transaction Patterns',
    'TY-005': 'Money Mule Activity',
    'TY-006': 'Trade-Based Money Laundering',
    'TY-007': 'Beneficial Owner Concealment',
    'TY-008': 'Round-Tripping',
    'TY-009': 'Identity Fraud / Synthetic Accounts',
    'TY-010': 'High-Value Cash Equivalents'
}

# ═════════════════════════════════════════════════════════════════════════════
# FILING TEMPLATES
# ═════════════════════════════════════════════════════════════════════════════

STR_TEMPLATE = {
    'report_type': 'STR',
    'institution': 'Eagle Trust Bank',
    'branch': 'Chennai Main Branch',
    'reporting_entity': 'EagleTrust Fraud Detection System',
    'fields': [
        'filing_id',
        'case_id',
        'customer_id',
        'customer_name',
        'account_number',
        'transaction_id',
        'transaction_date',
        'amount',
        'description',
        'severity',
        'typology_code',
        'narrative',
        'citations',
        'investigation_note'
    ]
}

CTR_TEMPLATE = {
    'report_type': 'CTR',
    'institution': 'Eagle Trust Bank',
    'threshold_amount': CTR_AMOUNT_THRESHOLD,
    'fields': [
        'filing_id',
        'customer_id',
        'customer_name',
        'account_number',
        'transaction_id',
        'transaction_date',
        'amount',
        'description',
        'narrative'
    ]
}

# ═════════════════════════════════════════════════════════════════════════════
# ADMIN CREDENTIALS (HARDCODED FOR DEMO)
# ═════════════════════════════════════════════════════════════════════════════

ADMIN_USERNAME = 'et_admin'
ADMIN_PASSWORD = 'eagletrust'

# ═════════════════════════════════════════════════════════════════════════════
# FILE PATHS
# ═════════════════════════════════════════════════════════════════════════════

import os

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ARCHIVE_DIR = os.path.join(_BASE_DIR, 'cla_archive')
PDF_OUTPUT_DIR = os.path.join(ARCHIVE_DIR, 'pdfs')

# Ensure directories exist
os.makedirs(ARCHIVE_DIR, exist_ok=True)
os.makedirs(PDF_OUTPUT_DIR, exist_ok=True)
