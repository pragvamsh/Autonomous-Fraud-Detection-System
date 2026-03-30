"""
aba_agent.py  (Module 1 — Orchestrator)
───────────────────────────────────────
Entry point for the Alert & Block Agent.

Starts a background polling thread that checks action_packages where:
  aba_consumed = 0
(meaning RAA has dispatched but ABA hasn't processed yet).

7-Stage Pipeline (per package_id):
  Stage 1 — Package Loader        : read + validate action_packages row
  Stage 2 — Gateway Controller    : determine gateway action (APPROVE/HELD/STOPPED)
  Stage 3 — Action Executor       : dispatch verdict-specific actions
  Stage 4 — Notification Dispatcher : push/email/SMS to customer
  Stage 5 — Account Controller    : freeze/unfreeze/credential reset (via action_executor)
  Stage 6 — Regulatory Router     : CTR/STR queue insertion
  Stage 7 — Case Manager          : fraud_cases + handoff to CLA

Wiring (app.py):
  from et_service.aba.aba_agent import ABAAgent
  aba_agent = ABAAgent.create()   # starts background poller immediately
"""

import threading
import time
import traceback

from et_dao.aba_dao import (
    get_unconsumed_packages,
    mark_aba_consumed,
    update_fraud_alert_aba,
    save_execution_log,
    recover_stale_aba_claims,
)
from et_service.aba.constants import POLL_INTERVAL_S, BATCH_LIMIT
from et_service.aba.gateway_controller import determine_gateway_action
from et_service.aba.action_executor import execute_verdict_actions
from et_service.aba.notification_engine import dispatch_notifications
from et_service.aba.case_manager import create_fraud_case, queue_regulatory_filings


class ABAAgent:
    """
    Alert & Block Agent — 4th agent in the pipeline.
    Consumes action_packages from RAA and executes customer-facing actions.
    """

    def __init__(self):
        self._running = False
        self._poller_thread = None

    @classmethod
    def create(cls) -> 'ABAAgent':
        """
        Factory method: creates agent and starts background poll loop.
        This is the standard entry point; call from app.py.
        """
        agent = cls()
        agent._running = True

        # Recover any stale claims from previous crashes
        recovered = recover_stale_aba_claims(threshold_seconds=120)
        if recovered > 0:
            _log(f"Recovered {recovered} stale claims (aba_consumed=2→0)")

        t = threading.Thread(
            target=agent._poll_loop,
            daemon=True,
            name='aba-poller',
        )
        t.start()
        agent._poller_thread = t
        _log(f"Poll thread started | interval={POLL_INTERVAL_S}s | batch={BATCH_LIMIT}")
        return agent

    def stop(self):
        """Stops the polling loop gracefully."""
        self._running = False
        if self._poller_thread:
            self._poller_thread.join(timeout=2)
        _log("Polling stopped.")

    def _poll_loop(self):
        """Continuous poll loop — runs until process exits or stop() called."""
        while self._running:
            try:
                packages = get_unconsumed_packages(limit=BATCH_LIMIT)
                for pkg in packages:
                    package_id = pkg.get('package_id')
                    payload = pkg.get('payload', {})
                    # Enrich payload with package_id and alert_id from row
                    payload['package_id'] = package_id
                    payload['alert_id'] = pkg.get('alert_id')

                    try:
                        self._process(package_id, payload)
                    except Exception as e:
                        _log(f"ERROR processing package_id={package_id}: {e}")
                        traceback.print_exc()
                        # Still mark as consumed to prevent infinite retry
                        self._finalize(package_id, payload, error=str(e))
            except Exception as e:
                _log(f"ERROR in poll loop: {e}")
                traceback.print_exc()

            time.sleep(POLL_INTERVAL_S)

    def _process(self, package_id: str, payload: dict):
        """
        Runs all 7 pipeline stages for a single action_package.
        """
        t_start = time.monotonic()
        alert_id = payload.get('alert_id')
        customer_id = payload.get('customer_id', 'UNKNOWN')
        verdict = payload.get('raa_verdict', 'ALLOW')

        _log(f"START | package_id={package_id} | alert_id={alert_id} | verdict={verdict}")

        stages_completed = []
        result = {
            'aba_gateway_action': None,
            'aba_actions_executed': [],
            'aba_case_id': None,
        }

        try:
            # ── Stage 1: Package Loader ──────────────────────────────────────
            # Already loaded from get_unconsumed_packages()
            stages_completed.append('S1_PACKAGE_LOADER')
            _log(f"  S1 Package Loader: OK | customer_id={customer_id}")

            # ── Stage 2: Gateway Controller ──────────────────────────────────
            gateway_result = determine_gateway_action(payload)
            result['aba_gateway_action'] = gateway_result['gateway_action']
            stages_completed.append('S2_GATEWAY_CONTROLLER')
            _log(f"  S2 Gateway Controller: {gateway_result['gateway_action']}")

            # ── Stage 3: Action Executor ─────────────────────────────────────
            action_result = execute_verdict_actions(payload, gateway_result)
            result['aba_actions_executed'] = action_result['actions_executed']
            stages_completed.append('S3_ACTION_EXECUTOR')
            _log(f"  S3 Action Executor: {len(action_result['actions_executed'])} actions")

            # ── Stage 4: Notification Dispatcher ─────────────────────────────
            notif_result = dispatch_notifications(payload, verdict)
            stages_completed.append('S4_NOTIFICATION_DISPATCHER')
            _log(f"  S4 Notification Dispatcher: {notif_result['notifications_queued']} queued")

            # ── Stage 5: Account Controller ──────────────────────────────────
            # (Already handled in action_executor for BLOCK verdicts)
            stages_completed.append('S5_ACCOUNT_CONTROLLER')
            _log(f"  S5 Account Controller: frozen={action_result.get('account_frozen', False)}")

            # ── Stage 6: Regulatory Router ───────────────────────────────────
            reg_result = queue_regulatory_filings(payload)
            stages_completed.append('S6_REGULATORY_ROUTER')
            _log(f"  S6 Regulatory Router: CTR={reg_result['ctr_filed']}, STR={reg_result['str_queued']}")

            # ── Stage 7: Case Manager ────────────────────────────────────────
            case_result = create_fraud_case(payload, package_id)
            if case_result.get('case_created'):
                result['aba_case_id'] = case_result['case_id']
            stages_completed.append('S7_CASE_MANAGER')
            _log(f"  S7 Case Manager: created={case_result.get('case_created', False)}")

            # ── Finalize ─────────────────────────────────────────────────────
            self._finalize(package_id, payload, result=result)

        except Exception as e:
            _log(f"PIPELINE ERROR at {stages_completed[-1] if stages_completed else 'INIT'}: {e}")
            traceback.print_exc()
            self._finalize(package_id, payload, result=result, error=str(e))

        elapsed_ms = round((time.monotonic() - t_start) * 1000, 1)
        _log(f"DONE | package_id={package_id} | {elapsed_ms}ms | stages={len(stages_completed)}")

    def _finalize(self, package_id: str, payload: dict, result: dict = None, error: str = None):
        """
        Marks package as consumed and writes results to fraud_alerts.
        Always called, even on errors, to prevent infinite retry loops.
        """
        result = result or {}

        try:
            # Mark action_package as consumed
            mark_aba_consumed(package_id)
        except Exception as e:
            _log(f"CRITICAL: Could not mark aba_consumed=1: {e}")

        try:
            # Update fraud_alerts with ABA results
            alert_id = payload.get('alert_id')
            if alert_id:
                update_fraud_alert_aba(alert_id, result)
        except Exception as e:
            _log(f"ERROR updating fraud_alerts: {e}")

        try:
            # Write execution log for audit
            save_execution_log({
                'package_id': package_id,
                'alert_id': payload.get('alert_id'),
                'customer_id': payload.get('customer_id', 'UNKNOWN'),
                'verdict': payload.get('raa_verdict', 'UNKNOWN'),
                'gateway_action': result.get('aba_gateway_action', 'UNKNOWN'),
                'actions_executed': result.get('aba_actions_executed', []),
                'execution_time_ms': 0,  # Not tracked here
                'error_message': error,
            })
        except Exception as e:
            _log(f"ERROR saving execution log: {e}")


def _log(msg: str):
    print(f"[ABA] {msg}")
