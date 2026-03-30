"""
pra_agent.py  (pra)
─────────────────────
Module 5 of the PRA pipeline — orchestrator and background poller.

The PRA runs as a background polling service. It:
  1. Polls fraud_alerts every 500ms for unprocessed FLAG/ALERT/BLOCK rows
  2. Dispatches each to a worker thread (max 4 concurrent)
  3. Executes the 5-stage pipeline per alert:

     Stage 1 — Trigger check (read TMA row from fraud_alerts)
     Stage 2 — Sequence Builder → (30×15) matrix
     Stage 3 — BiLSTM Inference → bilstm_score + hidden_state
     Stage 4 — 3-Layer RAG → urgency_multiplier, precedent_adj, reg_adj
     Stage 5 — Pattern Scorer → final_pattern_score + pra_verdict
               + write-back to fraud_alerts + pra_feedback_writer

Phase 1 Stability Guarantee:
  PRA adds new files only. It reads TMA's fraud_alerts rows via MySQL
  and writes back to the SAME row (pra_* columns). Zero modifications
  to any Phase 1 file.

Entry points:
  start_pra_poller()  — start background thread (called from app startup)
  process_alert(alert_id)  — process a single alert (for testing)
"""

from __future__ import annotations

import time
import threading
from concurrent.futures import ThreadPoolExecutor

from et_dao.pattern_dao         import (
    get_unprocessed_alerts,
    get_alert_by_id,
    mark_alert_pra_complete,
    write_pra_result,
    save_pattern_alert,
    link_pattern_alert_to_payment,
    claim_single_alert,          # [FIX-4] atomic claim for direct calls
)
from et_service.pattern_agent.sequence_builder  import build_sequence
from et_service.pattern_agent.bilstm_model      import run_inference
from et_service.pattern_agent.pra_rag_layer     import retrieve_pra_rag
from et_service.pattern_agent.pattern_scorer    import compute_pattern_score, build_agent_reasoning
from et_service.pattern_agent.pra_feedback_writer import write_novel_pattern_to_l3
from et_service.pattern_agent.constants import (
    POLLER_INTERVAL_MS,
    POLLER_MAX_WORKERS,
    POLLER_BATCH_SIZE,
)

# ── Background poller ──────────────────────────────────────────────────────────

_executor: ThreadPoolExecutor | None = None
_running   = False


def start_pra_poller():
    """
    Starts the PRA background polling thread.
    Call once from Flask app startup (e.g. in create_app()).
    """
    global _executor, _running
    if _running:
        return

    _executor = ThreadPoolExecutor(max_workers=POLLER_MAX_WORKERS, thread_name_prefix='pra-worker')
    _running  = True
    t = threading.Thread(target=_poll_loop, name='pra-poller', daemon=True)
    t.start()
    print(f"[PRA] Poller started — interval={POLLER_INTERVAL_MS}ms, "
          f"workers={POLLER_MAX_WORKERS}")


def stop_pra_poller():
    """Graceful shutdown — call from app teardown."""
    global _running, _executor
    _running = False
    if _executor:
        _executor.shutdown(wait=True)
    print("[PRA] Poller stopped.")


def _poll_loop():
    interval_s = POLLER_INTERVAL_MS / 1000.0
    while _running:
        try:
            # Fetch unprocessed FLAG/ALERT/BLOCK alerts
            # Uses compound index (pra_processed, verdict) for efficiency
            alerts = get_unprocessed_alerts(batch_size=POLLER_BATCH_SIZE)
            for alert in alerts:
                _executor.submit(_safe_process, alert['id'])
        except Exception as e:
            print(f"[PRA] Poller error: {e}")
        time.sleep(interval_s)


def _safe_process(alert_id: int):
    """Wrapper so worker thread exceptions don't kill the executor."""
    try:
        process_alert(alert_id)
    except Exception as e:
        print(f"[PRA] ERROR processing alert_id={alert_id}: {e}")
        # Mark as processed anyway to prevent infinite retry loop
        try:
            mark_alert_pra_complete(alert_id, success=False)
        except Exception:
            pass


# ── Main pipeline ──────────────────────────────────────────────────────────────

def process_alert(alert_id: int) -> dict:
    """
    Executes the full 5-stage PRA pipeline for one fraud_alert row.

    [FIX-4] Atomic claim guard added: sets pra_processed=2 before running.
    This prevents triple-processing where:
      - The background poller picks up the alert (run 1)
      - payment_routes._fire_pattern_agent() calls process_alert directly (run 2)
      - OTP verify fires _fire_pattern_agent() again after commit (run 3)
    Now, whichever thread gets here first claims pra_processed=2. Any
    subsequent call for the same alert_id hits the guard and exits immediately.

    Parameters:
      alert_id — primary key of the fraud_alerts row to process

    Returns the pra_result dict written back to fraud_alerts.
    """
    # ── Atomic claim — prevents duplicate/triple processing ───────────
    # [FIX-4] claim_single_alert does: UPDATE SET pra_processed=2
    #         WHERE id=alert_id AND pra_processed=0  (atomic, row-level lock)
    # Returns True if this thread claimed it, False if already claimed/done.
    if not claim_single_alert(alert_id):
        print(f"[PRA] alert_id={alert_id} already claimed or processed — skipping")
        return {}

    # ── Stage 1: Read TMA alert row ───────────────────────────────────
    alert = get_alert_by_id(alert_id)
    if alert is None:
        print(f"[PRA] WARN — alert_id={alert_id} not found in DB.")
        return {}

    customer_id      = alert['customer_id']
    anomaly_features = alert.get('anomaly_features') or {}
    flag_labels      = alert.get('anomaly_flag_labels') or []

    print(f"[PRA] Processing alert_id={alert_id}, customer={customer_id}, "
          f"tma_verdict={alert.get('decision')}, tma_score={alert.get('risk_score')}")

    # ── Stage 2: Sequence Builder → (30 × 15) matrix ─────────────────
    try:
        matrix, sequence_length = build_sequence(customer_id, alert_id)
    except Exception as e:
        print(f"[PRA] ERROR in sequence_builder: {e}")
        _write_failure(alert_id, f"sequence_builder failed: {e}")
        return {}

    # ── Stage 3: BiLSTM Inference ─────────────────────────────────────
    try:
        inference = run_inference(matrix)
        bilstm_score  = inference['bilstm_score']
        hidden_state  = inference['hidden_state']
    except Exception as e:
        print(f"[PRA] ERROR in BiLSTM inference: {e}")
        _write_failure(alert_id, f"bilstm_model failed: {e}")
        return {}

    # ── Stage 4: 3-Layer RAG Retrieval ───────────────────────────────
    try:
        rag = retrieve_pra_rag(
            hidden_state=hidden_state,
            anomaly_features=anomaly_features,
            anomaly_flag_labels=flag_labels,
        )
    except Exception as e:
        print(f"[PRA] ERROR in RAG retrieval: {e}")
        # Graceful degradation: continue with RAG defaults
        rag = {
            'typology_code':      alert.get('typology_code'),  # fallback to TMA's
            'urgency_multiplier': 1.0,
            'regulatory_action':  None,
            'precedent_adj':      0.0,
            'reg_adj':            0.0,
            'reg_citations':      [],
            'l3_similarity':      0.0,
            'rag_reasoning':      f'RAG failed: {e}',
        }

    # ── Stage 5: Pattern Scorer & Verdict ────────────────────────────
    try:
        scored = compute_pattern_score(
            bilstm_score=bilstm_score,
            precedent_adj=rag['precedent_adj'],
            reg_adj=rag['reg_adj'],
            urgency_multiplier=rag['urgency_multiplier'],
        )
        agent_reasoning = build_agent_reasoning(
            bilstm_score=bilstm_score,
            precedent_adj=rag['precedent_adj'],
            reg_adj=rag['reg_adj'],
            urgency_multiplier=rag['urgency_multiplier'],
            typology_code=rag['typology_code'],
            l3_similarity=rag['l3_similarity'],
            n_cases=rag.get('n_cases', 0),
            final_pattern_score=scored['final_pattern_score'],
            pra_verdict=scored['pra_verdict'],
            reg_citations=rag['reg_citations'],
        )
    except Exception as e:
        print(f"[PRA] ERROR in pattern_scorer: {e}")
        _write_failure(alert_id, f"pattern_scorer failed: {e}")
        return {}

    # ── Write-back to fraud_alerts (pra_* columns) ─────────────────────
    pra_result = {
        'pra_processed':      1,
        'pra_verdict':        scored['pra_verdict'],
        'pattern_score':      scored['final_pattern_score'],
        'bilstm_score':       round(bilstm_score, 2),
        'precedent_adj':      rag['precedent_adj'],
        'reg_adj':            rag['reg_adj'],
        'urgency_multiplier': rag['urgency_multiplier'],
        'typology_code':      rag['typology_code'],
        'sequence_length':    sequence_length,
        'pra_reg_citations':  rag['reg_citations'],   # JSON — forwarded to RAA
        'agent_reasoning':    agent_reasoning,
    }

    try:
        write_pra_result(alert_id, pra_result)
        print(
            f"[PRA] OK - alert_id={alert_id} — "
            f"verdict={scored['pra_verdict']}, "
            f"score={scored['final_pattern_score']}, "
            f"bilstm={bilstm_score:.1f}, "
            f"typology={rag['typology_code']}, "
            f"urgency x{rag['urgency_multiplier']:.2f}"
        )
    except Exception as e:
        print(f"[PRA] ERROR writing pra_result to DB: {e}")

    # ── Write to pattern_alerts table (for /api/pattern-alert/ endpoint) ──
    payment_id = alert.get('payment_id')
    if payment_id:
        try:
            pa_row = {
                'payment_id':     payment_id,
                'customer_id':    customer_id,
                'pattern_score':  int(scored['final_pattern_score']),
                'temporal_score': 0,
                'network_score':  0,
                'rag_adjustment': round(rag['precedent_adj'] + rag['reg_adj'], 2),
                'decision':       scored['pra_verdict'],
                'pattern_types':  None,
                'network_flags':  None,
                'agent_reasoning': agent_reasoning,
                'typology_code':  rag['typology_code'],
                'tma_risk_score': alert.get('risk_score'),
                'tma_decision':   alert.get('decision'),
            }
            pa_id = save_pattern_alert(pa_row)
            link_pattern_alert_to_payment(payment_id, pa_id)
        except Exception as e:
            print(f"[PRA] WARN — could not write pattern_alerts row: {e}")

    # ── Feedback Writer: novel patterns → L3 ─────────────────────────
    # If the BiLSTM score is high but no L3 match was found, this is
    # a potentially novel pattern — log it for future L3 ingestion.
    if bilstm_score >= 70 and rag['l3_similarity'] < RAG_L3_SIM_THRESHOLD_FOR_FEEDBACK:
        try:
            write_novel_pattern_to_l3(
                alert_id=alert_id,
                hidden_state=hidden_state,
                bilstm_score=bilstm_score,
                customer_id=customer_id,
                flag_labels=flag_labels,
            )
        except Exception as e:
            print(f"[PRA] WARN — feedback writer failed: {e}")

    return pra_result


# ── Helpers ────────────────────────────────────────────────────────────────────

RAG_L3_SIM_THRESHOLD_FOR_FEEDBACK = 0.40   # below this = potentially novel


def _write_failure(alert_id: int, reason: str):
    """Marks the alert as processed with a failure flag so it isn't retried."""
    try:
        write_pra_result(alert_id, {
            'pra_processed': 1,
            'pra_verdict':   None,
            'agent_reasoning': f'PRA FAILED: {reason}',
        })
    except Exception as e:
        print(f"[PRA] Could not write failure state for alert_id={alert_id}: {e}")