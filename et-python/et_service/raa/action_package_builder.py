"""
action_package_builder.py  (Module 8)
──────────────────────────────────────
Assembles the final action_package and dispatches it to the action_packages table.

This is the RAA → ABA contract: every field ABA needs to execute actions
must be present in this package.

Also writes back the RAA scoring columns to fraud_alerts via raa_dao.
"""

import uuid
from datetime import datetime

from et_dao.raa_dao import save_action_package, mark_raa_processed


def dispatch(
    data:   dict,   # enriched fraud_alerts row from intelligence_aggregator
    tier:   str,    # T1/T2/T3/T4
    dims:   dict,   # D1-D5, score_a
    rag:    dict,   # pattern_mult, adjustments, citations, l3_typology_doc
    scores: dict,   # final_raa_score, raa_verdict, score_a, score_b
    reg:    dict,   # ctr_flag, str_required, str_draft
) -> str:
    """
    Assembles the action_package, writes it to action_packages table,
    and backfills the RAA columns in fraud_alerts.

    Returns the generated package_id.
    """
    alert_id    = data.get('id') or data.get('alert_id')
    customer_id = data.get('customer_id', '')

    # ── Merge all citations (TMA + PRA already in data['all_citations']) ───────
    raa_l1_citations = rag.get('l1_citations', [])
    raa_l2_citations = rag.get('l2_citations', [])
    raa_l3_citations = rag.get('l3_citations', [])
    all_citations = (
        data.get('all_citations', [])     # TMA + PRA
        + raa_l1_citations
        + raa_l2_citations
        + raa_l3_citations
    )

    # ── Build human-readable investigation note ────────────────────────────────
    investigation_note = _build_investigation_note(data, tier, dims, scores, reg)

    # Append investigation_note into str_draft if present
    if reg.get('str_draft'):
        reg['str_draft']['investigation_note'] = investigation_note

    # ── Assemble action_package ────────────────────────────────────────────────
    action_package = {
        # RAA core output
        'final_raa_score':  scores.get('final_raa_score'),
        'raa_verdict':      scores.get('raa_verdict'),
        'action_required':  scores.get('raa_verdict'),   # ABA reads this field
        'customer_tier':    tier,
        'score_a':          scores.get('score_a'),
        'score_b':          scores.get('score_b'),

        # Provenance from TMA + PRA
        'tma_score':         data.get('risk_score'),
        'pra_verdict':       data.get('pra_verdict'),
        'pattern_score':     data.get('pattern_score'),
        'typology_code':     data.get('typology_code'),
        'urgency_multiplier': data.get('urgency_multiplier'),
        'confidence':        data.get('confidence'),

        # Dimension breakdown (for audit)
        'dim_scores': {
            'D1': dims.get('D1'),
            'D2': dims.get('D2'),
            'D3': dims.get('D3'),
            'D4': dims.get('D4'),
            'D5': dims.get('D5'),
        },

        # RAG multipliers (for audit)
        'rag_multipliers': {
            'pattern_mult':   rag.get('pattern_mult'),
            'coldstart_adj':  rag.get('coldstart_adj'),
            'regulatory_adj': rag.get('regulatory_adj'),
        },

        # Regulatory outputs
        'str_required': reg.get('str_required', False),
        'ctr_flag':     reg.get('ctr_flag', False),
        'str_draft':    reg.get('str_draft') or None,   # None if not required

        # Evidence pack — ABA passes this to CLA
        'all_citations':     all_citations,
        'investigation_note': investigation_note,

        # Routing
        'customer_id': customer_id,
        'alert_id':    alert_id,
        'timestamp':   datetime.now().isoformat(),
    }

    # ── Write action package to DB ─────────────────────────────────────────────
    package_id = f"PKG-{datetime.now().strftime('%Y%m%d%H%M%S')}-{str(alert_id).zfill(6)}-{uuid.uuid4().hex[:8].upper()}"
    save_action_package(package_id, alert_id, action_package)

    # ── Backfill RAA columns in fraud_alerts ───────────────────────────────────
    mark_raa_processed(alert_id, {
        'final_raa_score':    scores.get('final_raa_score'),
        'raa_verdict':        scores.get('raa_verdict'),
        'customer_tier':      tier,
        'score_a':            scores.get('score_a'),
        'score_b':            scores.get('score_b'),
        'str_required':       reg.get('str_required', False),
        'ctr_flag':           reg.get('ctr_flag', False),
        'investigation_note': investigation_note,
        'raa_citations':      raa_l1_citations + raa_l2_citations + raa_l3_citations,
    })

    _log(
        f"Action package dispatched | package_id={package_id} | "
        f"alert_id={alert_id} | verdict={scores.get('raa_verdict')} | "
        f"str_required={reg.get('str_required')} | ctr_flag={reg.get('ctr_flag')}"
    )

    return package_id


def _build_investigation_note(
    data: dict, tier: str, dims: dict, scores: dict, reg: dict
) -> str:
    """Generates a human-readable English investigation note for compliance."""
    pra_verdict  = data.get('pra_verdict') or 'MAINTAIN'
    typology     = data.get('typology_code') or 'not identified'
    final_score  = scores.get('final_raa_score', 0)
    raa_verdict  = scores.get('raa_verdict', 'ALLOW')

    parts = [
        f"RAA final score: {final_score}/100 → {raa_verdict}.",
        f"Customer tier: {tier}.",
        f"TMA transaction anomaly score: {data.get('risk_score', 'N/A')}.",
        f"PRA sequence verdict: {pra_verdict}.",
        f"Fraud typology: {typology}.",
    ]

    if pra_verdict == 'CRITICAL':
        parts.append(
            "CRITICAL demotion applied — PRA detected high-confidence "
            "adversarial sequence (e.g. account takeover pattern). "
            "Customer reclassified to T1 regardless of historical tier."
        )

    if reg.get('str_required'):
        parts.append(
            "STR auto-draft generated — confirmed pattern or PRA CRITICAL verdict "
            "triggers statutory reporting obligation under PMLA S.12. "
            "Awaiting compliance officer approval before filing with FIU-IND."
        )

    if reg.get('ctr_flag'):
        reason = reg.get('ctr_reason') or 'threshold exceeded'
        parts.append(f"CTR flag raised: {reason}.")

    dims_note = (
        f"5-Dimension scores: D1(Txn)={dims.get('D1', 0):.0f}, "
        f"D2(Behav)={dims.get('D2', 0):.0f}, "
        f"D3(Net)={dims.get('D3', 0):.0f}, "
        f"D4(Identity)={dims.get('D4', 0):.0f}, "
        f"D5(Temporal)={dims.get('D5', 0):.0f}."
    )
    parts.append(dims_note)

    return " ".join(parts)


def _log(msg: str):
    print(f"[RAA][ActionPackageBuilder] {msg}")
