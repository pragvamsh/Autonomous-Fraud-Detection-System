"""
raa_agent.py  (Module 1 — Orchestrator — Build Last)
──────────────────────────────────────────────────────
Entry point for the Risk Assessment Agent.

Starts a background polling thread that checks for fraud_alerts rows where
  pra_processed = 1  AND  raa_processed = 0
(meaning PRA has finished and RAA hasn't run yet).

8-Stage Pipeline (per alert_id):
  Stage 1  — Intelligence Aggregator : read + validate fraud_alerts row
  Stage 2  — Customer Tier Engine    : T1-T4 classification + CRITICAL demotion
  Stage 3  — 5-Dimension Scorer      : D1-D5 formulas → Score_A
  Stage 4  — RAG Layer               : L2 K=15 / L1 K=3 / L3 typology retrievals
  Stage 5  — Score Engine            : Score_B + 60/40 fusion + floors → verdict
  Stage 6  — Regulatory Engine       : CTR/STR checks + STR auto-draft
  Stage 7  — Action Package Builder  : assemble + dispatch to action_packages
  Stage 8  — DB write-back           : raa_processed=1 in fraud_alerts

RAA never executes actions (no account freezes, no notifications, no STR filing).
It concludes and delegates — ABA executes based on action_package contents.

Wiring (app.py):
  from et_service.raa.raa_agent import RAAAgent
  raa_agent = RAAAgent.create()   # starts background poller immediately
"""

import json
import time
import threading

from et_dao.raa_dao import get_unprocessed_alerts
from et_service.raa.intelligence_aggregator import aggregate
from et_service.raa.tier_engine             import classify_tier
from et_service.raa.dimension_scorer        import score_dimensions
from et_service.raa.raa_rag_layer           import retrieve
from et_service.raa.score_engine            import fuse_scores
from et_service.raa.regulatory_engine       import check_regulatory
from et_service.raa.action_package_builder  import dispatch

# ── Constants ──────────────────────────────────────────────────────────────────
_POLL_INTERVAL_S = 0.5    # seconds between poll cycles
_BATCH_LIMIT     = 10     # alerts processed per poll cycle


class RAAAgent:
    """
    Risk Assessment Agent — background polling orchestrator.

    Usage:
        agent = RAAAgent.create()   # returns immediately, starts bg thread

    The agent instance must be kept alive (held by the app context).
    The background thread is daemonised — it exits when the main process exits.
    """

    def __init__(self):
        self._running = False

    @classmethod
    def create(cls) -> 'RAAAgent':
        """
        Factory method: creates the agent and starts the background poll loop.
        Called once at Flask startup alongside TMA and PRA bootstrap.
        """
        agent = cls()
        agent._running = True
        t = threading.Thread(
            target=agent._poll_loop,
            daemon=True,
            name='raa-poller',
        )
        t.start()
        _log("Poll thread started | interval=500ms | batch=10")
        return agent

    # ── Background poll loop ───────────────────────────────────────────────────

    def _poll_loop(self):
        """Continuous poll loop — runs until the process exits."""
        while self._running:
            try:
                rows = get_unprocessed_alerts(limit=_BATCH_LIMIT)
                for row in rows:
                    alert_id = row.get('alert_id') or row.get('id')
                    try:
                        self._process(alert_id)
                    except Exception as e:
                        _log(f"ERROR processing alert_id={alert_id}: {e}")
            except Exception as e:
                _log(f"ERROR in poll loop: {e}")

            time.sleep(_POLL_INTERVAL_S)

    # ── Single alert processing ────────────────────────────────────────────────

    def _process(self, alert_id: int):
        """
        Runs all 8 pipeline stages for a single fraud_alert row.
        Stages are numbered to match the spec and logging format.
        """
        t_start = time.monotonic()
        _log(f"alert_id={alert_id} | Starting RAA pipeline")

        stages = []

        def update_stage(stage_num: int, name: str, status: str, result: str = "", ms: int = 0):
            stage = {
                "stage": stage_num,
                "name": name,
                "status": status,
                "result": result,
                "duration_ms": ms
            }
            existing = next((s for s in stages if s["stage"] == stage_num), None)
            if existing:
                existing.update(stage)
            else:
                stages.append(stage)
            try:
                from db import get_db_connection
                conn = get_db_connection()
                if not conn: return
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE fraud_alerts SET raa_stages = %s WHERE id = %s",
                    (json.dumps(stages), alert_id)
                )
                conn.commit()
                cursor.close()
                conn.close()
            except Exception as e:
                _log(f"WARN: could not save RAA stages to DB: {e}")

        try:
            # ── Stage 1: Intelligence Aggregator ──────────────────────────
            st_start = time.monotonic()
            update_stage(1, "Intelligence Aggregator", "processing")
            try:
                data = aggregate(alert_id)
                elapsed = int((time.monotonic() - st_start) * 1000)
                update_stage(1, "Intelligence Aggregator", "done", f"Found pra_verdict={data.get('pra_verdict')}", elapsed)
                _log(
                    f"alert_id={alert_id} | Stage 1 complete | "
                    f"customer_id={data.get('customer_id')} | "
                    f"pra_verdict={data.get('pra_verdict')} | "
                    f"typology={data.get('typology_code')}"
                )
            except ValueError as e:
                elapsed = int((time.monotonic() - st_start) * 1000)
                update_stage(1, "Intelligence Aggregator", "error", f"Validation err: {e}", elapsed)
                _log(f"alert_id={alert_id} | Stage 1 FAILED (validation): {e}")
                return
            except Exception as e:
                elapsed = int((time.monotonic() - st_start) * 1000)
                update_stage(1, "Intelligence Aggregator", "error", f"Error: {e}", elapsed)
                _log(f"alert_id={alert_id} | Stage 1 ERROR: {e}")
                return

            # ── Stage 2: Customer Tier Engine ─────────────────────────────
            st_start = time.monotonic()
            update_stage(2, "Customer Tier Engine", "processing")
            try:
                tier = classify_tier(data)
                elapsed = int((time.monotonic() - st_start) * 1000)
                update_stage(2, "Customer Tier Engine", "done", f"Tier classified: {tier}", elapsed)
                _log(
                    f"alert_id={alert_id} | Stage 2 complete | "
                    f"tier={tier} | pra_verdict={data.get('pra_verdict')}"
                    + (" | CRITICAL DEMOTION" if data.get('pra_verdict') == 'CRITICAL' else "")
                )
            except Exception as e:
                elapsed = int((time.monotonic() - st_start) * 1000)
                update_stage(2, "Customer Tier Engine", "error", f"Error: {e} -> T1", elapsed)
                _log(f"alert_id={alert_id} | Stage 2 ERROR: {e} — defaulting to T1")
                tier = 'T1'

            data['_tier'] = tier

            # ── Stage 3: 5-Dimension Scorer ───────────────────────────────
            st_start = time.monotonic()
            update_stage(3, "5-Dimension Scorer", "processing")
            try:
                dims = score_dimensions(data, tier)
                elapsed = int((time.monotonic() - st_start) * 1000)
                update_stage(3, "5-Dimension Scorer", "done", f"Score_A={dims['score_a']}", elapsed)
                _log(
                    f"alert_id={alert_id} | Stage 3 complete | "
                    f"D1={dims['D1']} D2={dims['D2']} D3={dims['D3']} "
                    f"D4={dims['D4']} D5={dims['D5']} | Score_A={dims['score_a']}"
                )
            except Exception as e:
                elapsed = int((time.monotonic() - st_start) * 1000)
                update_stage(3, "5-Dimension Scorer", "error", f"Error: {e}", elapsed)
                _log(f"alert_id={alert_id} | Stage 3 ERROR: {e} — using zero dims")
                dims = {'D1': 0, 'D2': 0, 'D3': 0, 'D4': 0, 'D5': 0, 'score_a': 0}

            # ── Stage 4: RAG Layer ────────────────────────────────────────
            st_start = time.monotonic()
            update_stage(4, "RAG Context Layer", "processing")
            try:
                rag = retrieve(data, dims)
                elapsed = int((time.monotonic() - st_start) * 1000)
                res_str = f"Pattern_mult={rag.get('pattern_mult'):.2f}, Reg_adj={rag.get('regulatory_adj'):+.1f}"
                update_stage(4, "RAG Context Layer", "done", res_str, elapsed)
                _log(
                    f"alert_id={alert_id} | Stage 4 complete | "
                    f"pattern_mult={rag.get('pattern_mult'):.2f} | "
                    f"coldstart_adj={rag.get('coldstart_adj'):+.1f} | "
                    f"regulatory_adj={rag.get('regulatory_adj'):+.1f} | "
                    f"ctr_threshold={rag.get('ctr_single_threshold'):,.0f} | "
                    f"L3_typology={rag.get('l3_typology_code', 'none')}"
                )
            except Exception as e:
                elapsed = int((time.monotonic() - st_start) * 1000)
                update_stage(4, "RAG Context Layer", "error", f"Error fallback: {e}", elapsed)
                _log(f"alert_id={alert_id} | Stage 4 ERROR: {e} — using RAG defaults")
                rag = {
                    'pattern_mult': 1.5, 'coldstart_adj': 0.0,
                    'network_adj': 1.0, 'age_adj': 0.0,
                    'regulatory_adj': 0.0,
                    'ctr_single_threshold': 1_000_000,
                    'ctr_aggregate_threshold': 500_000,
                    'l3_typology_doc': None, 'str_obligation': '',
                    'l3_typology_code': '',
                    'l2_citations': [], 'l1_citations': [], 'l3_citations': [],
                }

            # ── Stage 5: Score Engine ─────────────────────────────────────
            st_start = time.monotonic()
            update_stage(5, "Fusion Score Engine", "processing")
            try:
                scores = fuse_scores(dims, rag, data)
                elapsed = int((time.monotonic() - st_start) * 1000)
                update_stage(5, "Fusion Score Engine", "done", f"Final={scores['final_raa_score']}, Verdict={scores['raa_verdict']}", elapsed)
                _log(
                    f"alert_id={alert_id} | Stage 5 complete | "
                    f"Score_B={scores['score_b']} | "
                    f"Score_A_adj={scores['score_a']} | "
                    f"floor:{scores['floor_applied']} | "
                    f"final_raa_score={scores['final_raa_score']} | "
                    f"verdict={scores['raa_verdict']}"
                )
            except Exception as e:
                elapsed = int((time.monotonic() - st_start) * 1000)
                update_stage(5, "Fusion Score Engine", "error", f"FATAL: {e}", elapsed)
                _log(f"alert_id={alert_id} | Stage 5 FAILED: {e} — aborting")
                return

            # ── Stage 6: Regulatory Engine ────────────────────────────────
            st_start = time.monotonic()
            update_stage(6, "Regulatory Checks", "processing")
            try:
                data['_amount'] = float(data.get('amount') or 0.0)
                reg = check_regulatory(scores, rag, data)
                elapsed = int((time.monotonic() - st_start) * 1000)
                update_stage(6, "Regulatory Checks", "done", f"STR={reg['str_required']}, CTR={reg['ctr_flag']}", elapsed)
                _log(
                    f"alert_id={alert_id} | Stage 6 complete | "
                    f"str_required={reg['str_required']} | "
                    f"ctr_flag={reg['ctr_flag']} | "
                    f"str_draft={'generated' if reg.get('str_draft') else 'none'}"
                )
            except Exception as e:
                elapsed = int((time.monotonic() - st_start) * 1000)
                update_stage(6, "Regulatory Checks", "error", f"Fallback due to Err: {e}", elapsed)
                _log(f"alert_id={alert_id} | Stage 6 ERROR: {e} — no regulatory flags")
                reg = {'ctr_flag': False, 'str_required': False, 'str_draft': None}

            # ── Stage 7: Action Package Builder ───────────────────────────
            st_start = time.monotonic()
            update_stage(7, "Action Package Dispatch", "processing")
            try:
                package_id = dispatch(data, tier, dims, rag, scores, reg)
                elapsed = int((time.monotonic() - st_start) * 1000)
                update_stage(7, "Action Package Dispatch", "done", f"Pkg: {package_id}", elapsed)
                _log(
                    f"alert_id={alert_id} | Stage 7 complete | "
                    f"package_id={package_id}"
                )
            except Exception as e:
                elapsed = int((time.monotonic() - st_start) * 1000)
                update_stage(7, "Action Package Dispatch", "error", f"Fatal: {e}", elapsed)
                _log(f"alert_id={alert_id} | Stage 7 FAILED: {e} — action package not dispatched")
                return

            elapsed_ms = round((time.monotonic() - t_start) * 1000, 1)
            _log(
                f"alert_id={alert_id} | raa_processed=1 | DONE in {elapsed_ms}ms | "
                f"verdict={scores['raa_verdict']} | str={reg['str_required']} | "
                f"ctr={reg['ctr_flag']}"
            )
            
            try:
                from et_dao.raa_dao import mark_raa_processed
                mark_raa_processed(alert_id, {
                    'final_raa_score': scores.get('final_raa_score'),
                    'raa_verdict': scores.get('raa_verdict'),
                    'customer_tier': tier,
                    'score_a': dims.get('score_a'),
                    'score_b': scores.get('score_b'),
                    'str_required': reg.get('str_required'),
                    'ctr_flag': reg.get('ctr_flag'),
                    'investigation_note': '',
                    'raa_citations': []
                })
            except Exception as e:
                _log(f"CRITICAL: Could not write RAA scores to DB: {e}")

        finally:
            # [FIX] Always mark raa_processed=1 to prevent infinite retry loops.
            # If action_package_builder already set it, this is a harmless no-op.
            try:
                from et_dao.raa_dao import mark_raa_processed_flag
                mark_raa_processed_flag(alert_id)
            except Exception as e:
                _log(f"CRITICAL: Could not set raa_processed=1 for alert_id={alert_id}: {e}")


def _log(msg: str):
    print(f"[RAA] {msg}")
