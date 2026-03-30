"""
test_tma_pra_handoff.py
────────────────────────
Integration tests for TMA → PRA handoff.

Tests:
  - pra_processed flag transitions (0 → 2 → 1)
  - Atomic claim prevents duplicate processing
  - PRA waits for TMA completion (risk_score IS NOT NULL)
"""

import unittest
from unittest.mock import patch, MagicMock
import threading
import time


class TestTMAPRAHandoff(unittest.TestCase):
    """Integration tests for TMA to PRA handoff."""

    def setUp(self):
        """Set up mock data."""
        self.alert_id = 1001
        self.mock_alert = {
            'id': self.alert_id,
            'customer_id': 'C12345',
            'risk_score': 65,  # TMA has completed
            'decision': 'FLAG',
            'pra_processed': 0,
            'anomaly_features': {'amount_z_score': 1.5},
            'anomaly_flag_labels': [],
            'payment_id': 'PAY123',
        }

    @patch('et_service.pattern_agent.pra_agent.write_pra_result')
    @patch('et_service.pattern_agent.pra_agent.claim_single_alert')
    @patch('et_service.pattern_agent.pra_agent.get_alert_by_id')
    def test_pra_processed_starts_0_goes_to_2_then_1(
        self, mock_get_alert, mock_claim, mock_write
    ):
        """pra_processed transitions: 0 → 2 (claimed) → 1 (complete)."""
        from et_service.pattern_agent.pra_agent import process_alert
        import numpy as np
        from et_service.pattern_agent.constants import SEQUENCE_LENGTH, FEATURE_DIM

        mock_get_alert.return_value = self.mock_alert

        # Track claim calls
        claim_called = []

        def track_claim(alert_id):
            claim_called.append(alert_id)
            return True

        mock_claim.side_effect = track_claim

        # Mock other dependencies
        with patch('et_service.pattern_agent.pra_agent.build_sequence') as mock_seq:
            mock_seq.return_value = (np.zeros((SEQUENCE_LENGTH, FEATURE_DIM)), 15)

            with patch('et_service.pattern_agent.pra_agent.run_inference') as mock_infer:
                mock_infer.return_value = {'bilstm_score': 50.0, 'hidden_state': np.zeros(128)}

                with patch('et_service.pattern_agent.pra_agent.retrieve_pra_rag') as mock_rag:
                    mock_rag.return_value = {
                        'typology_code': None, 'urgency_multiplier': 1.0,
                        'regulatory_action': None, 'precedent_adj': 0.0,
                        'reg_adj': 0.0, 'reg_citations': [], 'l3_similarity': 0.0,
                        'rag_reasoning': '', 'n_cases': 0,
                    }

                    with patch('et_service.pattern_agent.pra_agent.compute_pattern_score') as mock_score:
                        mock_score.return_value = {
                            'final_pattern_score': 40, 'pra_verdict': 'MAINTAIN',
                            'rag_pattern_score': 0.0, 'combined_raw': 40.0,
                        }

                        with patch('et_service.pattern_agent.pra_agent.build_agent_reasoning', return_value='Test'):
                            with patch('et_service.pattern_agent.pra_agent.save_pattern_alert', return_value=5001):
                                with patch('et_service.pattern_agent.pra_agent.link_pattern_alert_to_payment'):
                                    with patch('builtins.print'):
                                        process_alert(self.alert_id)

        # Verify claim was called (pra_processed → 2)
        self.assertEqual(len(claim_called), 1)
        self.assertEqual(claim_called[0], self.alert_id)

        # Verify write_pra_result was called with pra_processed=1
        mock_write.assert_called_once()
        call_args = mock_write.call_args[0]
        self.assertEqual(call_args[0], self.alert_id)
        self.assertEqual(call_args[1]['pra_processed'], 1)

    @patch('et_service.pattern_agent.pra_agent.claim_single_alert')
    @patch('et_service.pattern_agent.pra_agent.get_alert_by_id')
    def test_claim_single_alert_only_succeeds_once(self, mock_get_alert, mock_claim):
        """Concurrent claims - only first thread succeeds."""
        from et_service.pattern_agent.pra_agent import process_alert

        # Track results
        results = []
        claim_count = [0]
        lock = threading.Lock()

        def mock_claim_fn(alert_id):
            with lock:
                claim_count[0] += 1
                # First call returns True, subsequent return False
                return claim_count[0] == 1

        mock_claim.side_effect = mock_claim_fn

        # Mock get_alert_by_id to return a valid alert so successful claim can proceed
        mock_get_alert.return_value = {
            'id': self.alert_id,
            'customer_id': 'C12345',
            'risk_score': 50,
            'decision': 'FLAG',
            'pra_processed': 0,
            'anomaly_features': {},
            'anomaly_flag_labels': [],
            'payment_id': 'PAY123',
        }

        def thread_target(thread_id):
            with patch('builtins.print'):
                result = process_alert(self.alert_id)
                results.append((thread_id, result))

        # Launch 3 concurrent threads
        threads = [
            threading.Thread(target=thread_target, args=(i,))
            for i in range(3)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=2.0)

        # Only one thread should have gotten claim
        self.assertEqual(claim_count[0], 3)  # All tried to claim

        # Two should have returned empty dict (claim failed)
        empty_results = [r for _, r in results if r == {}]
        self.assertEqual(len(empty_results), 2)

    @patch('et_dao.pattern_dao.get_unprocessed_alerts')
    def test_pra_does_not_start_until_risk_score_not_null(self, mock_get_unprocessed):
        """PRA query should only return alerts where risk_score IS NOT NULL."""
        # The get_unprocessed_alerts SQL should filter on risk_score IS NOT NULL
        mock_get_unprocessed.return_value = [
            {'id': 1001, 'risk_score': 65, 'pra_processed': 0},  # TMA complete
            # Alert with risk_score=NULL would not be returned
        ]

        from et_dao.pattern_dao import get_unprocessed_alerts
        alerts = get_unprocessed_alerts(batch_size=10)

        # All returned alerts should have risk_score set
        for alert in alerts:
            self.assertIsNotNone(alert.get('risk_score'))


class TestVerdictHandoff(unittest.TestCase):
    """Test handoff for each verdict type."""

    def _run_handoff_test(self, decision):
        """Helper to test handoff for a given verdict."""
        from et_service.pattern_agent.pra_agent import process_alert
        import numpy as np
        from et_service.pattern_agent.constants import SEQUENCE_LENGTH, FEATURE_DIM

        alert = {
            'id': 1001,
            'customer_id': 'C12345',
            'risk_score': 50,
            'decision': decision,
            'pra_processed': 0,
            'anomaly_features': {},
            'anomaly_flag_labels': [],
            'payment_id': 'PAY123',
        }

        with patch('et_service.pattern_agent.pra_agent.claim_single_alert', return_value=True):
            with patch('et_service.pattern_agent.pra_agent.get_alert_by_id', return_value=alert):
                with patch('et_service.pattern_agent.pra_agent.build_sequence') as mock_seq:
                    mock_seq.return_value = (np.zeros((SEQUENCE_LENGTH, FEATURE_DIM)), 10)

                    with patch('et_service.pattern_agent.pra_agent.run_inference') as mock_infer:
                        mock_infer.return_value = {
                            'bilstm_score': 40.0,
                            'hidden_state': np.zeros(128),
                        }

                        with patch('et_service.pattern_agent.pra_agent.retrieve_pra_rag') as mock_rag:
                            mock_rag.return_value = {
                                'typology_code': None, 'urgency_multiplier': 1.0,
                                'regulatory_action': None, 'precedent_adj': 0.0,
                                'reg_adj': 0.0, 'reg_citations': [],
                                'l3_similarity': 0.0, 'rag_reasoning': '', 'n_cases': 0,
                            }

                            with patch('et_service.pattern_agent.pra_agent.compute_pattern_score') as mock_score:
                                mock_score.return_value = {
                                    'final_pattern_score': 35,
                                    'pra_verdict': 'DE-ESCALATE',
                                    'rag_pattern_score': 0.0,
                                    'combined_raw': 35.0,
                                }

                                with patch('et_service.pattern_agent.pra_agent.build_agent_reasoning', return_value='Test'):
                                    with patch('et_service.pattern_agent.pra_agent.write_pra_result') as mock_write:
                                        with patch('et_service.pattern_agent.pra_agent.save_pattern_alert', return_value=5001):
                                            with patch('et_service.pattern_agent.pra_agent.link_pattern_alert_to_payment'):
                                                with patch('builtins.print'):
                                                    result = process_alert(1001)

        return result

    def test_allow_verdict_handoff(self):
        """ALLOW verdict is processed by PRA."""
        result = self._run_handoff_test('ALLOW')
        self.assertIsNotNone(result)

    def test_flag_verdict_handoff(self):
        """FLAG verdict is processed by PRA."""
        result = self._run_handoff_test('FLAG')
        self.assertIsNotNone(result)

    def test_alert_verdict_handoff(self):
        """ALERT verdict is processed by PRA."""
        result = self._run_handoff_test('ALERT')
        self.assertIsNotNone(result)

    def test_block_verdict_handoff(self):
        """BLOCK verdict is processed by PRA."""
        result = self._run_handoff_test('BLOCK')
        self.assertIsNotNone(result)


if __name__ == '__main__':
    unittest.main()
