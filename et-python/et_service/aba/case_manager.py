"""
case_manager.py  (Module 7)
───────────────────────────
Creates fraud cases and hands off to CLA.

Case Priority:
  P1 (Critical) — Score 90+, BLOCK with high-risk typology
  P2 (High)     — Score 76-89, BLOCK standard

Evidence Pack:
  - All RAG citations (TMA + PRA + RAA)
  - Investigation note
  - Dimension scores
  - Timeline of alerts
"""

from et_dao.aba_dao import save_fraud_case, save_regulatory_filing
from et_service.aba.constants import (
    HIGH_RISK_TYPOLOGIES,
    P1_MIN_SCORE,
    BLOCK_MIN_SCORE,
)


def create_fraud_case(payload: dict, package_id: str) -> dict:
    """
    Creates fraud case if criteria met (BLOCK verdict).
    Returns case details or None if no case needed.
    """
    verdict = payload.get('raa_verdict')
    score = float(payload.get('final_raa_score', 0) or 0)

    if verdict != 'BLOCK':
        return {
            'case_created': False,
            'reason': 'Not BLOCK verdict',
        }

    # Determine priority
    priority = _determine_priority(score, payload.get('typology_code'))

    # Build evidence pack
    evidence_pack = _build_evidence_pack(payload)

    case = {
        'alert_id': payload['alert_id'],
        'package_id': package_id,
        'customer_id': payload['customer_id'],
        'priority': priority,
        'status': 'OPEN',
        'evidence_pack': evidence_pack,
        'cla_consumed': 0,  # Handoff flag for CLA (5th agent)
    }

    case_id = save_fraud_case(case)

    _log(
        f"Fraud case created: case_id={case_id} | "
        f"priority={priority} | alert_id={payload['alert_id']}"
    )

    return {
        'case_created': True,
        'case_id': case_id,
        'priority': priority,
    }


def queue_regulatory_filings(payload: dict) -> dict:
    """
    Queues CTR and/or STR filings based on RAA flags.
    Returns filing details.
    """
    result = {
        'ctr_filed': False,
        'str_queued': False,
        'ctr_filing_id': None,
        'str_filing_id': None,
    }

    customer_id = payload.get('customer_id')
    alert_id = payload.get('alert_id')
    amount = payload.get('amount')

    # CTR filing (auto-filed, no approval needed)
    if payload.get('ctr_flag'):
        ctr = {
            'type': 'CTR',
            'alert_id': alert_id,
            'customer_id': customer_id,
            'amount': amount,
            'status': 'AUTO_FILED',
            'draft_content': _build_ctr_content(payload),
            'investigation_note': None,
        }
        ctr_id = save_regulatory_filing(ctr)
        result['ctr_filed'] = True
        result['ctr_filing_id'] = ctr_id
        _log(f"CTR auto-filed: {ctr_id}")

    # STR filing (needs compliance approval)
    if payload.get('str_required'):
        str_filing = {
            'type': 'STR',
            'alert_id': alert_id,
            'customer_id': customer_id,
            'amount': amount,
            'status': 'PENDING_APPROVAL',
            'draft_content': payload.get('str_draft'),
            'investigation_note': payload.get('investigation_note'),
        }
        str_id = save_regulatory_filing(str_filing)
        result['str_queued'] = True
        result['str_filing_id'] = str_id
        _log(f"STR queued for approval: {str_id}")

    return result


def _determine_priority(score: float, typology: str) -> str:
    """
    Determines fraud case priority based on score and typology.

    P1 (Critical): Score 90+, BLOCK with high-risk typology
    P2 (High): Score 76-89, BLOCK standard
    P3 (Medium): Everything else
    """
    if score >= P1_MIN_SCORE and typology in HIGH_RISK_TYPOLOGIES:
        return 'P1'
    elif score >= BLOCK_MIN_SCORE:
        return 'P2'
    return 'P3'


def _build_evidence_pack(payload: dict) -> dict:
    """
    Builds the evidence pack for the fraud case.
    Contains all information needed for investigation.
    """
    return {
        # Provenance chain
        'tma_score': payload.get('tma_score'),
        'pra_verdict': payload.get('pra_verdict'),
        'pattern_score': payload.get('pattern_score'),
        'raa_verdict': payload.get('raa_verdict'),
        'final_raa_score': payload.get('final_raa_score'),

        # Typology
        'typology_code': payload.get('typology_code'),
        'urgency_multiplier': payload.get('urgency_multiplier'),

        # Customer tier
        'customer_tier': payload.get('customer_tier'),

        # Dimension scores
        'dim_scores': payload.get('dim_scores', {}),

        # RAG multipliers
        'rag_multipliers': payload.get('rag_multipliers', {}),

        # All citations from TMA + PRA + RAA
        'all_citations': payload.get('all_citations', []),

        # Investigation note (human-readable)
        'investigation_note': payload.get('investigation_note'),

        # Regulatory flags
        'str_required': payload.get('str_required', False),
        'ctr_flag': payload.get('ctr_flag', False),
        'str_draft': payload.get('str_draft'),

        # Timestamps
        'timestamp': payload.get('timestamp'),
    }


def _build_ctr_content(payload: dict) -> dict:
    """Builds CTR filing content."""
    return {
        'customer_id': payload.get('customer_id'),
        'transaction_amount': payload.get('amount'),
        'transaction_date': payload.get('timestamp'),
        'typology_code': payload.get('typology_code'),
        'auto_generated': True,
        'reason': 'Amount exceeds CTR threshold',
    }


def _log(msg: str):
    print(f"[ABA][CaseManager] {msg}")
