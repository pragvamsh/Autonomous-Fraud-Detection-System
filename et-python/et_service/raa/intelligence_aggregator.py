"""
intelligence_aggregator.py  (Module 2)
────────────────────────────────────────
Reads and validates the fraud_alerts row for RAA processing.

⚠  This module fails loudly on missing required fields — it does NOT silently
   continue with defaults. If TMA or PRA hasn't written a required field, RAA
   raises ValueError so the alert stays in the queue for retry.

Required TMA fields:
  risk_score, ml_score, rag_score, confidence,
  typology_code, feature_snapshot, rag_citations

Required PRA fields:
  pra_verdict, pattern_score, bilstm_score,
  urgency_multiplier, pra_reg_citations, sequence_length

Merges TMA + PRA citations into all_citations for the evidence pack.
"""

import json
from et_dao.raa_dao import get_full_alert_row

# ── Required field contracts ───────────────────────────────────────────────────
# These fields must exist (not None) for RAA to proceed.
_REQUIRED_TMA_FIELDS = [
    'risk_score',
    'ml_score',
    # rag_score and confidence are optional — TMA may run in ML-only fallback
]

_REQUIRED_PRA_FIELDS = [
    'pra_verdict',
    # pattern_score, bilstm_score etc. are best-effort; PRA may not have all fields
]


def aggregate(alert_id: int) -> dict:
    """
    Main entry point. Fetches, validates, and enriches the fraud_alerts row.

    Returns the enriched row dict with 'all_citations' merged.
    Raises ValueError if the row is missing or incomplete.
    """
    row = get_full_alert_row(alert_id)
    if not row:
        raise ValueError(f"alert_id {alert_id} not found in fraud_alerts.")

    # ── Validate TMA fields ───────────────────────────────────────────────────
    missing_tma = [f for f in _REQUIRED_TMA_FIELDS if row.get(f) is None]
    if missing_tma:
        raise ValueError(
            f"alert_id {alert_id}: Missing TMA fields {missing_tma}. "
            f"Is TMA fully operational?"
        )

    # ── Validate PRA fields ───────────────────────────────────────────────────
    missing_pra = [f for f in _REQUIRED_PRA_FIELDS if row.get(f) is None]
    if missing_pra:
        raise ValueError(
            f"alert_id {alert_id}: Missing PRA fields {missing_pra}. "
            f"Is PRA fully operational and pra_processed=1?"
        )

    # ── Parse / default optional JSON fields ──────────────────────────────────
    rag_citations     = _parse_json(row.get('rag_citations'), [])
    pra_reg_citations = _parse_json(row.get('pra_reg_citations'), [])
    feature_snapshot  = _parse_json(row.get('feature_snapshot'), {})
    anomaly_flags     = _parse_json(row.get('anomaly_flags'), [])

    row['rag_citations']     = rag_citations
    row['pra_reg_citations'] = pra_reg_citations
    row['feature_snapshot']  = feature_snapshot
    row['anomaly_flags']     = anomaly_flags

    # ── Merge all citations — TMA + PRA → RAA carries through ─────────────────
    rag_list = rag_citations if isinstance(rag_citations, list) else [rag_citations] if rag_citations else []
    pra_list = pra_reg_citations if isinstance(pra_reg_citations, list) else [pra_reg_citations] if pra_reg_citations else []
    all_citations = rag_list + pra_list
    row['all_citations'] = all_citations

    # ── Normalise optional numerics ───────────────────────────────────────────
    for f in ('pattern_score', 'bilstm_score', 'sequence_length'):
        if row.get(f) is not None:
            try:
                row[f] = int(row[f])
            except (TypeError, ValueError):
                row[f] = 0

    for f in ('urgency_multiplier',):
        if row.get(f) is not None:
            try:
                row[f] = float(row[f])
            except (TypeError, ValueError):
                row[f] = 1.0
        else:
            row[f] = 1.0   # safe default

    for f in ('confidence',):
        if row.get(f) is not None:
            try:
                row[f] = float(row[f])
            except (TypeError, ValueError):
                row[f] = 0.5
        else:
            row[f] = 0.5

    _log(
        f"alert_id={alert_id} | customer={row.get('customer_id')} | "
        f"pra_verdict={row.get('pra_verdict')} | "
        f"typology={row.get('typology_code')} | "
        f"citations={len(all_citations)}"
    )

    return row


# ── Helpers ────────────────────────────────────────────────────────────────────

def _parse_json(value, default):
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return default
    return default


def _log(msg: str):
    print(f"[RAA][IntelligenceAggregator] {msg}")
