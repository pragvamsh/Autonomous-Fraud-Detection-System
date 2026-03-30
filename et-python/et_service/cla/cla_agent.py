"""
CLA Agent — Citation & Legal Archive Agent

Background polling agent that:
  1. Polls fraud_cases for unclaimed cases (cla_consumed = 0)
  2. Retrieves case evidence and alert data
  3. Archives citations from RAG results
  4. Assembles STR/CTR documents
  5. Determines filing action (auto-file, pending approval, reject)
  6. Updates regulatory_queue and marks case as consumed

Runs as a background thread with 500ms polling interval.
"""

import time
import threading
import json
from datetime import datetime
from typing import Dict, Any, Optional, List

from et_dao.cla_dao import (
    get_unclaimed_cases,
    mark_case_consumed,
    get_case_by_id,
    insert_archive
)
from et_dao.monitoring_dao import get_alert_by_id, get_transaction_by_id
from et_dao.customer_dao import get_customer_by_id
from et_dao.raa_dao import insert_regulatory_filing

from et_service.cla.citation_archiver import archive_from_alert_citations
from et_service.cla.str_assembler import assemble_str, assemble_ctr, validate_str_document
from et_service.cla.constants import (
    STR_AUTO_THRESHOLD,
    STR_APPROVAL_THRESHOLD,
    CTR_AMOUNT_THRESHOLD
)


class CLAAgent:
    """
    Citation & Legal Archive Agent - processes fraud cases and generates STR/CTR filings.
    """

    def __init__(self, poll_interval_ms: int = 500):
        self._poll_interval_ms = poll_interval_ms
        self._running = False
        self._poller_thread: Optional[threading.Thread] = None

    @classmethod
    def create(cls, poll_interval_ms: int = 500) -> 'CLAAgent':
        """
        Factory method to create and start a CLA agent.
        """
        agent = cls(poll_interval_ms)
        agent.start()
        return agent

    def start(self):
        """
        Starts the background polling thread.
        """
        if self._running:
            print("[CLAAgent] Already running.")
            return

        self._running = True
        self._poller_thread = threading.Thread(target=self._poll_loop, daemon=True, name="CLA-Poller")
        self._poller_thread.start()
        print(f"[CLAAgent] Started background poller (interval={self._poll_interval_ms}ms)")

    def stop(self):
        """
        Stops the background polling thread.
        """
        self._running = False
        if self._poller_thread:
            self._poller_thread.join(timeout=2.0)
        print("[CLAAgent] Stopped.")

    def _poll_loop(self):
        """
        Main polling loop - runs continuously in background thread.
        """
        while self._running:
            try:
                self._poll_once()
            except Exception as e:
                print(f"[CLAAgent] Poll error: {e}")
                import traceback
                traceback.print_exc()

            time.sleep(self._poll_interval_ms / 1000.0)

    def _poll_once(self):
        """
        Single poll iteration - fetches unclaimed cases and processes each one.
        """
        cases = get_unclaimed_cases(limit=5)
        for case in cases:
            try:
                self.process_case(case['case_id'])
            except Exception as e:
                print(f"[CLAAgent] Error processing case {case['case_id']}: {e}")

    def process_case(self, case_id: str) -> Optional[str]:
        """
        Processes a single fraud case:
          1. Retrieve case, alert, transaction, customer data
          2. Archive citations from alert
          3. Assemble STR document
          4. Determine filing action
          5. Update regulatory_queue
          6. Archive STR in cla_archive
          7. Mark case as consumed

        Returns filing_id on success, None on failure.
        """
        try:
            print(f"[CLAAgent] Processing case {case_id}")

            # Step 1: Retrieve case data
            case_data = get_case_by_id(case_id)
            if not case_data:
                print(f"[CLAAgent] Case {case_id} not found")
                return None

            alert_id = case_data['alert_id']
            customer_id = case_data['customer_id']

            # Retrieve alert data
            alert_data = get_alert_by_id(alert_id)
            if not alert_data:
                print(f"[CLAAgent] Alert {alert_id} not found for case {case_id}")
                return None

            # Retrieve transaction data
            transaction_id = alert_data['transaction_id']
            transaction_data = get_transaction_by_id(transaction_id)
            if not transaction_data:
                print(f"[CLAAgent] Transaction {transaction_id} not found")
                return None

            # Retrieve customer data
            customer_data = get_customer_by_id(customer_id)
            if not customer_data:
                print(f"[CLAAgent] Customer {customer_id} not found")
                return None

            # Step 2: Archive citations from alert
            citation_ids = self._archive_alert_citations(alert_data)

            # Step 3: Determine if this is STR or CTR
            amount = float(transaction_data['amount'])
            final_raa_score = float(alert_data.get('final_raa_score', 0))

            if amount >= CTR_AMOUNT_THRESHOLD:
                # CTR filing (high-value transaction)
                filing_type = 'CTR'
                str_content = assemble_ctr(transaction_data, customer_data)
            else:
                # STR filing (suspicious activity)
                filing_type = 'STR'
                str_content = assemble_str(
                    case_data=case_data,
                    alert_data=alert_data,
                    transaction_data=transaction_data,
                    customer_data=customer_data,
                    citation_ids=citation_ids
                )

            if not str_content:
                print(f"[CLAAgent] Failed to assemble {filing_type} for case {case_id}")
                return None

            # Step 4: Determine filing action
            if filing_type == 'STR':
                filing_status = self._determine_str_status(final_raa_score)
            else:
                filing_status = 'AUTO_FILED'  # CTR auto-filed

            filing_id = str_content.get('filing_id')

            # Step 5: Insert into regulatory_queue
            investigation_note = str_content.get('investigation_note', 'Auto-generated by CLA')
            filing_success = insert_regulatory_filing(
                filing_id=filing_id,
                filing_type=filing_type,
                alert_id=alert_id,
                customer_id=customer_id,
                amount=amount,
                status=filing_status,
                draft_content=str_content,
                investigation_note=investigation_note
            )

            if not filing_success:
                print(f"[CLAAgent] Failed to insert regulatory filing for case {case_id}")
                return None

            # Step 6: Archive STR in cla_archive
            archive_success = insert_archive(
                filing_id=filing_id,
                case_id=case_id,
                alert_id=alert_id,
                customer_id=customer_id,
                filing_type=filing_type,
                str_content=str_content,
                citations_used=citation_ids,
                pdf_path=None,  # PDF generated on-demand
                filed_by='CLA_AUTO'
            )

            if not archive_success:
                print(f"[CLAAgent] Failed to archive {filing_type} for case {case_id}")

            # Step 7: Mark case as consumed
            mark_case_consumed(case_id)

            print(f"[CLAAgent] ✅ Case {case_id} processed → {filing_type} {filing_id} ({filing_status})")
            return filing_id

        except Exception as e:
            print(f"[CLAAgent] Error processing case {case_id}: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _archive_alert_citations(self, alert_data: Dict[str, Any]) -> List[str]:
        """
        Archives citations from fraud_alerts.rag_citations and raa_citations.
        Returns list of citation_ids.
        """
        all_citation_ids = []

        try:
            # Archive TMA citations (rag_citations)
            rag_citations = alert_data.get('rag_citations')
            if rag_citations:
                if isinstance(rag_citations, str):
                    rag_citations = json.loads(rag_citations)
                citation_ids = archive_from_alert_citations(rag_citations)
                all_citation_ids.extend(citation_ids)

            # Archive RAA citations (raa_citations)
            raa_citations = alert_data.get('raa_citations')
            if raa_citations:
                if isinstance(raa_citations, str):
                    raa_citations = json.loads(raa_citations)
                citation_ids = archive_from_alert_citations(raa_citations)
                all_citation_ids.extend(citation_ids)

            # Archive PRA regulatory citations (pra_reg_citations)
            pra_reg_citations = alert_data.get('pra_reg_citations')
            if pra_reg_citations:
                if isinstance(pra_reg_citations, str):
                    pra_reg_citations = json.loads(pra_reg_citations)
                citation_ids = archive_from_alert_citations(pra_reg_citations)
                all_citation_ids.extend(citation_ids)

        except Exception as e:
            print(f"[CLAAgent] Error archiving citations: {e}")

        return list(set(all_citation_ids))  # Deduplicate

    def _determine_str_status(self, final_raa_score: float) -> str:
        """
        Determines STR filing status based on RAA score:
          - >= 85: AUTO_FILED
          - >= 70: PENDING_APPROVAL
          - < 70: REJECTED (not filed)

        Returns status string for regulatory_queue.
        """
        if final_raa_score >= STR_AUTO_THRESHOLD:
            return 'AUTO_FILED'
        elif final_raa_score >= STR_APPROVAL_THRESHOLD:
            return 'PENDING_APPROVAL'
        else:
            return 'REJECTED'


# ═════════════════════════════════════════════════════════════════════════════
# MANUAL PROCESSING API (for admin dashboard)
# ═════════════════════════════════════════════════════════════════════════════

def process_case_manually(case_id: str) -> Optional[str]:
    """
    Manually processes a case (for admin dashboard).
    Returns filing_id on success, None on failure.
    """
    agent = CLAAgent(poll_interval_ms=500)
    return agent.process_case(case_id)


# ═════════════════════════════════════════════════════════════════════════════
# BOOTSTRAP (called from app.py)
# ═════════════════════════════════════════════════════════════════════════════

_global_agent: Optional[CLAAgent] = None


def start_cla_agent() -> CLAAgent:
    """
    Starts the CLA agent background poller.
    Called from app.py during bootstrap.
    """
    global _global_agent
    if _global_agent is not None:
        print("[CLAAgent] Already started.")
        return _global_agent

    _global_agent = CLAAgent.create(poll_interval_ms=500)
    return _global_agent


def stop_cla_agent():
    """
    Stops the CLA agent (for graceful shutdown).
    """
    global _global_agent
    if _global_agent:
        _global_agent.stop()
        _global_agent = None
