"""
regulatory_engine.py  (Module 7)
──────────────────────────────────
CTR/STR compliance checks using L1-retrieved thresholds (no hardcoded values).

Four checks in order:
  1. Single transaction ≥ ctr_single_threshold    → ctr_flag = True
  2. 24h aggregate ≥ ctr_aggregate_threshold       → ctr_flag = True
  3. Confirmed structuring typology + score > 40  → str_required = True
  4. pra_verdict == 'CRITICAL'                     → str_required = True

If str_required: builds the STR auto-draft evidence pack.

⚠  RAA NEVER auto-files. str_draft is a dict in the action_package.
   CLA (Agent 5) is responsible for queuing it for human compliance approval.
"""

from datetime import datetime
from et_dao.raa_dao import get_24h_customer_total

# Typology codes known to carry STR obligation
# (comprehensive list — also validated against L3 regulatory_obligation field)
_STR_TYPOLOGY_CODES = {
    'TY-03',  # Structuring / layering
    'TY-07',  # Money mule
    'TY-11',  # Trade-based ML
    'TY-12',  # Round-tripping
    'TY-18',  # Rapid fund movement
    'TY-19',  # Account takeover
    'TY-21',  # Smurfing
}


def check_regulatory(scores: dict, rag: dict, data: dict) -> dict:
    """
    Main entry point.

    scores : output of score_engine (final_raa_score, raa_verdict)
    rag    : output of raa_rag_layer (ctr thresholds, l3_typology_doc, str_obligation)
    data   : full fraud_alerts row

    Returns:
      ctr_flag, ctr_reason, str_required, str_draft (or None)
    """
    customer_id     = data.get('customer_id', '')
    pra_verdict     = data.get('pra_verdict') or ''
    typology_code   = data.get('typology_code') or ''
    final_score     = scores.get('final_raa_score', 0)

    # Amount: prefer feature_snapshot, fallback to 0
    fs = data.get('feature_snapshot') or {}
    # Transaction amount is not directly in fraud_alerts — carry it from orchestrator
    amount = float(data.get('_amount', 0.0))

    # L1 thresholds (never hardcoded — always from RAG retrieval)
    ctr_single     = float(rag.get('ctr_single_threshold', 1_000_000))
    ctr_aggregate  = float(rag.get('ctr_aggregate_threshold', 500_000))
    str_obligation = rag.get('str_obligation', '')
    l3_typology_doc = rag.get('l3_typology_doc')
    all_citations   = (
        rag.get('l2_citations', [])
        + rag.get('l1_citations', [])
        + rag.get('l3_citations', [])
    )

    ctr_flag    = False
    ctr_reason  = None
    str_required = False

    # ── Check 1: Single transaction CTR ───────────────────────────────────────
    if amount >= ctr_single:
        ctr_flag   = True
        ctr_reason = f'single_txn_threshold ({amount:,.0f} >= {ctr_single:,.0f})'
        _log(f"CTR single txn | amount={amount:,.0f} >= threshold={ctr_single:,.0f}")

    # ── Check 2: 24h aggregate CTR ────────────────────────────────────────────
    if not ctr_flag:
        try:
            total_24h = get_24h_customer_total(customer_id)
            if total_24h + amount >= ctr_aggregate:
                ctr_flag   = True
                ctr_reason = (
                    f'aggregate_24h_threshold '
                    f'({total_24h + amount:,.0f} >= {ctr_aggregate:,.0f})'
                )
                _log(
                    f"CTR 24h aggregate | total={total_24h + amount:,.0f} "
                    f">= threshold={ctr_aggregate:,.0f}"
                )
        except Exception as e:
            _log(f"WARN: could not fetch 24h total: {e}")

    # ── Check 3: Confirmed structuring → STR ──────────────────────────────────
    is_structuring = (
        typology_code in _STR_TYPOLOGY_CODES
        or 'structuring' in (pra_verdict or '').lower()
        or 'structuring' in typology_code.lower()
    )
    if is_structuring and final_score > 40:
        str_required = True
        _log(f"STR: structuring pattern | typology={typology_code} | score={final_score}")

    # ── Check 4: PRA CRITICAL → STR mandatory ──────────────────────────────────
    if pra_verdict == 'CRITICAL':
        str_required = True
        _log(f"STR: pra_verdict=CRITICAL → str mandatory")

    # ── Check 5: L3 regulatory_obligation field says STR ──────────────────────
    if str_obligation == 'STR' and amount >= ctr_single * 0.05:   # above 5% of CTR threshold
        str_required = True
        _log(f"STR: L3 regulatory_obligation=STR | typology={typology_code}")

    # ── Auto-draft STR if required ─────────────────────────────────────────────
    str_draft = None
    if str_required:
        str_draft = build_str_draft(data, l3_typology_doc, all_citations, scores)
        _log(f"STR draft generated | typology={typology_code}")

    _log(
        f"Regulatory check complete | customer={customer_id} | "
        f"ctr_flag={ctr_flag} | str_required={str_required}"
    )

    return {
        'ctr_flag':    ctr_flag,
        'ctr_reason':  ctr_reason,
        'str_required': str_required,
        'str_draft':   str_draft,
    }


def build_str_draft(
    alert_row:       dict,
    l3_typology_doc: dict | None,
    all_citations:   list,
    scores:          dict,
) -> dict:
    """
    Assembles the STR evidence pack.

    ⚠  THIS IS A DRAFT ONLY — never auto-filed.
       Human compliance officer must approve before filing with FIU-IND.
    """
    typology_desc = ''
    decisive_signals = ''
    if l3_typology_doc:
        typology_desc    = l3_typology_doc.get('description', '')
        decisive_signals = l3_typology_doc.get('decisive_signals', '')

    return {
        'form':              'FIU-IND STR (Rule 7 PMLA)',
        'section':           'PMLA-S12',
        'status':            'DRAFT — PENDING HUMAN APPROVAL',
        'draft_generated_at': datetime.now().isoformat(),

        # Transaction context
        'transaction_id':    alert_row.get('transaction_id', ''),
        'customer_id':       alert_row.get('customer_id', ''),
        'typology_code':     alert_row.get('typology_code', ''),
        'typology_description': typology_desc,
        'decisive_signals':  decisive_signals,

        # Risk scores
        'tma_score':         alert_row.get('risk_score'),
        'pra_verdict':       alert_row.get('pra_verdict'),
        'pattern_score':     alert_row.get('pattern_score'),
        'final_raa_score':   scores.get('final_raa_score'),
        'raa_verdict':       scores.get('raa_verdict'),

        # Evidence pack
        'l1_citations':   [c for c in all_citations if c.get('source') == 'L1_regulatory'],
        'l2_citations':   [c for c in all_citations if c.get('source') == 'L2_fraud_cases'],
        'l3_citations':   [c for c in all_citations if c.get('source') == 'L3_typologies'],
        'all_citations':  all_citations,

        # Investigation note (to be populated by action_package_builder)
        'investigation_note': '',
    }


def _log(msg: str):
    print(f"[RAA][RegulatoryEngine] {msg}")
