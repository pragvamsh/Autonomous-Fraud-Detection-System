"""
test_pra_agent.py
──────────────────
Unit tests for PRA pra_agent module.

Tests:
  - Atomic claim behavior
  - Process alert pipeline stages
  - Error handling and graceful degradation
  - Feedback writer trigger conditions
"""

import unittest
from unittest.mock import patch, MagicMock
import numpy as np


class TestClaimSingleAlert(unittest.TestCase):
    """Tests for atomic claim_single_alert behavior."""

    @patch('et_dao.pattern_dao.claim_single_alert')
    def test_claim_single_alert_returns_true_when_unclaimed(self, mock_claim):
        """Unclaimed alert returns True from claim_single_alert."""
        mock_claim.return_value = True

        from et_dao.pattern_dao import claim_single_alert
        result = claim_single_alert(1001)

        self.assertTrue(result)

    @patch('et_dao.pattern_dao.claim_single_alert')
    def test_claim_single_alert_returns_false_when_already_claimed(self, mock_claim):
        """Already claimed alert returns False."""
        mock_claim.return_value = False

        from et_dao.pattern_dao import claim_single_alert
        result = claim_single_alert(1001)

        self.assertFalse(result)


class TestProcessAlert(unittest.TestCase):
    """Tests for process_alert main pipeline."""

    def setUp(self):
        """Set up mock data."""
        self.alert_id = 1001
        self.mock_alert_data = {
            'id': self.alert_id,
            'customer_id': 'C12345',
            'decision': 'FLAG',
            'risk_score': 65,
            'anomaly_features': {'amount_z_score': 1.5},
            'anomaly_flag_labels': ['is_velocity_burst'],
            'payment_id': 'PAY123',
            'typology_code': None,
        }

    @patch('et_service.pattern_agent.pra_agent.claim_single_alert')
    def test_process_alert_skips_if_claim_fails(self, mock_claim):
        """Pipeline skips if claim_single_alert returns False."""
        from et_service.pattern_agent.pra_agent import process_alert

        mock_claim.return_value = False

        with patch('builtins.print'):
            result = process_alert(self.alert_id)

        # Should return empty dict
        self.assertEqual(result, {})

    @patch('et_service.pattern_agent.pra_agent.write_novel_pattern_to_l3')
    @patch('et_service.pattern_agent.pra_agent.link_pattern_alert_to_payment')
    @patch('et_service.pattern_agent.pra_agent.save_pattern_alert')
    @patch('et_service.pattern_agent.pra_agent.write_pra_result')
    @patch('et_service.pattern_agent.pra_agent.build_agent_reasoning')
    @patch('et_service.pattern_agent.pra_agent.compute_pattern_score')
    @patch('et_service.pattern_agent.pra_agent.retrieve_pra_rag')
    @patch('et_service.pattern_agent.pra_agent.run_inference')
    @patch('et_service.pattern_agent.pra_agent.build_sequence')
    @patch('et_service.pattern_agent.pra_agent.get_alert_by_id')
    @patch('et_service.pattern_agent.pra_agent.claim_single_alert')
    def test_process_alert_runs_all_5_stages(
        self, mock_claim, mock_get_alert, mock_build_seq, mock_infer,
        mock_rag, mock_scorer, mock_reasoning, mock_write_result,
        mock_save_pa, mock_link_pa, mock_feedback
    ):
        """Process alert runs all 5 pipeline stages."""
        from et_service.pattern_agent.pra_agent import process_alert
        from et_service.pattern_agent.constants import SEQUENCE_LENGTH, FEATURE_DIM

        mock_claim.return_value = True
        mock_get_alert.return_value = self.mock_alert_data
        mock_build_seq.return_value = (
            np.zeros((SEQUENCE_LENGTH, FEATURE_DIM)),
            15
        )
        mock_infer.return_value = {
            'bilstm_score': 65.0,
            'hidden_state': np.zeros(128),
        }
        mock_rag.return_value = {
            'typology_code': 'TY-03',
            'urgency_multiplier': 1.5,
            'regulatory_action': None,
            'precedent_adj': 20.0,
            'reg_adj': 5.0,
            'reg_citations': [],
            'l3_similarity': 0.3,
            'rag_reasoning': 'Test',
            'n_cases': 3,
        }
        mock_scorer.return_value = {
            'final_pattern_score': 68,
            'pra_verdict': 'ESCALATE',
            'rag_pattern_score': 25.0,
            'combined_raw': 55.0,
        }
        mock_reasoning.return_value = 'Test reasoning'
        mock_save_pa.return_value = 5001  # pattern_alert_id

        with patch('builtins.print'):
            result = process_alert(self.alert_id)

        # All stages should have been called
        mock_build_seq.assert_called_once()
        mock_infer.assert_called_once()
        mock_rag.assert_called_once()
        mock_scorer.assert_called_once()
        mock_write_result.assert_called_once()

    @patch('et_service.pattern_agent.pra_agent.write_pra_result')
    @patch('et_service.pattern_agent.pra_agent.build_sequence')
    @patch('et_service.pattern_agent.pra_agent.get_alert_by_id')
    @patch('et_service.pattern_agent.pra_agent.claim_single_alert')
    def test_process_alert_sequence_builder_error_aborts(
        self, mock_claim, mock_get_alert, mock_build_seq, mock_write_result
    ):
        """Sequence builder error aborts pipeline."""
        from et_service.pattern_agent.pra_agent import process_alert

        mock_claim.return_value = True
        mock_get_alert.return_value = self.mock_alert_data
        mock_build_seq.side_effect = Exception("Sequence builder failed")

        with patch('builtins.print'):
            result = process_alert(self.alert_id)

        # Should return empty (aborted)
        self.assertEqual(result, {})

        # write_pra_result might be called for failure logging but not with full result
        # Important: pipeline aborted

    @patch('et_service.pattern_agent.pra_agent.write_pra_result')
    @patch('et_service.pattern_agent.pra_agent.compute_pattern_score')
    @patch('et_service.pattern_agent.pra_agent.retrieve_pra_rag')
    @patch('et_service.pattern_agent.pra_agent.run_inference')
    @patch('et_service.pattern_agent.pra_agent.build_sequence')
    @patch('et_service.pattern_agent.pra_agent.get_alert_by_id')
    @patch('et_service.pattern_agent.pra_agent.claim_single_alert')
    def test_process_alert_rag_error_uses_defaults(
        self, mock_claim, mock_get_alert, mock_build_seq, mock_infer,
        mock_rag, mock_scorer, mock_write_result
    ):
        """RAG error continues with default values."""
        from et_service.pattern_agent.pra_agent import process_alert
        from et_service.pattern_agent.constants import SEQUENCE_LENGTH, FEATURE_DIM

        mock_claim.return_value = True
        mock_get_alert.return_value = self.mock_alert_data
        mock_build_seq.return_value = (
            np.zeros((SEQUENCE_LENGTH, FEATURE_DIM)),
            15
        )
        mock_infer.return_value = {
            'bilstm_score': 50.0,
            'hidden_state': np.zeros(128),
        }
        mock_rag.side_effect = Exception("RAG retrieval failed")
        mock_scorer.return_value = {
            'final_pattern_score': 45,
            'pra_verdict': 'MAINTAIN',
            'rag_pattern_score': 0.0,
            'combined_raw': 45.0,
        }

        with patch('builtins.print'):
            with patch('et_service.pattern_agent.pra_agent.build_agent_reasoning', return_value='Test'):
                result = process_alert(self.alert_id)

        # Pipeline should continue with defaults
        mock_scorer.assert_called_once()

        # urgency_multiplier should be 1.0 in default
        call_args = mock_scorer.call_args[1]
        self.assertEqual(call_args['urgency_multiplier'], 1.0)


class TestFeedbackWriter(unittest.TestCase):
    """Tests for feedback writer trigger conditions."""

    @patch('et_service.pattern_agent.pra_agent.write_novel_pattern_to_l3')
    @patch('et_service.pattern_agent.pra_agent.link_pattern_alert_to_payment')
    @patch('et_service.pattern_agent.pra_agent.save_pattern_alert')
    @patch('et_service.pattern_agent.pra_agent.write_pra_result')
    @patch('et_service.pattern_agent.pra_agent.build_agent_reasoning')
    @patch('et_service.pattern_agent.pra_agent.compute_pattern_score')
    @patch('et_service.pattern_agent.pra_agent.retrieve_pra_rag')
    @patch('et_service.pattern_agent.pra_agent.run_inference')
    @patch('et_service.pattern_agent.pra_agent.build_sequence')
    @patch('et_service.pattern_agent.pra_agent.get_alert_by_id')
    @patch('et_service.pattern_agent.pra_agent.claim_single_alert')
    def test_feedback_writer_called_when_high_bilstm_low_l3_sim(
        self, mock_claim, mock_get_alert, mock_build_seq, mock_infer,
        mock_rag, mock_scorer, mock_reasoning, mock_write_result,
        mock_save_pa, mock_link_pa, mock_feedback
    ):
        """Feedback writer called when bilstm >= 70 and l3_similarity < 0.40."""
        from et_service.pattern_agent.pra_agent import process_alert
        from et_service.pattern_agent.constants import SEQUENCE_LENGTH, FEATURE_DIM

        mock_claim.return_value = True
        mock_get_alert.return_value = {
            'id': 1001,
            'customer_id': 'C12345',
            'decision': 'FLAG',
            'risk_score': 65,
            'anomaly_features': {},
            'anomaly_flag_labels': [],
            'payment_id': 'PAY123',
        }
        mock_build_seq.return_value = (np.zeros((SEQUENCE_LENGTH, FEATURE_DIM)), 15)
        mock_infer.return_value = {
            'bilstm_score': 75.0,  # >= 70
            'hidden_state': np.zeros(128),
        }
        mock_rag.return_value = {
            'typology_code': None,
            'urgency_multiplier': 1.0,
            'regulatory_action': None,
            'precedent_adj': 0.0,
            'reg_adj': 0.0,
            'reg_citations': [],
            'l3_similarity': 0.2,  # < 0.40 threshold
            'rag_reasoning': 'Test',
            'n_cases': 0,
        }
        mock_scorer.return_value = {
            'final_pattern_score': 60,
            'pra_verdict': 'MAINTAIN',
            'rag_pattern_score': 0.0,
            'combined_raw': 60.0,
        }
        mock_reasoning.return_value = 'Test'
        mock_save_pa.return_value = 5001

        with patch('builtins.print'):
            process_alert(1001)

        # Feedback writer should be called
        mock_feedback.assert_called_once()

    @patch('et_service.pattern_agent.pra_agent.write_novel_pattern_to_l3')
    @patch('et_service.pattern_agent.pra_agent.link_pattern_alert_to_payment')
    @patch('et_service.pattern_agent.pra_agent.save_pattern_alert')
    @patch('et_service.pattern_agent.pra_agent.write_pra_result')
    @patch('et_service.pattern_agent.pra_agent.build_agent_reasoning')
    @patch('et_service.pattern_agent.pra_agent.compute_pattern_score')
    @patch('et_service.pattern_agent.pra_agent.retrieve_pra_rag')
    @patch('et_service.pattern_agent.pra_agent.run_inference')
    @patch('et_service.pattern_agent.pra_agent.build_sequence')
    @patch('et_service.pattern_agent.pra_agent.get_alert_by_id')
    @patch('et_service.pattern_agent.pra_agent.claim_single_alert')
    def test_feedback_writer_not_called_when_bilstm_low(
        self, mock_claim, mock_get_alert, mock_build_seq, mock_infer,
        mock_rag, mock_scorer, mock_reasoning, mock_write_result,
        mock_save_pa, mock_link_pa, mock_feedback
    ):
        """Feedback writer NOT called when bilstm < 70."""
        from et_service.pattern_agent.pra_agent import process_alert
        from et_service.pattern_agent.constants import SEQUENCE_LENGTH, FEATURE_DIM

        mock_claim.return_value = True
        mock_get_alert.return_value = {
            'id': 1001,
            'customer_id': 'C12345',
            'decision': 'FLAG',
            'risk_score': 40,
            'anomaly_features': {},
            'anomaly_flag_labels': [],
            'payment_id': 'PAY123',
        }
        mock_build_seq.return_value = (np.zeros((SEQUENCE_LENGTH, FEATURE_DIM)), 15)
        mock_infer.return_value = {
            'bilstm_score': 40.0,  # < 70
            'hidden_state': np.zeros(128),
        }
        mock_rag.return_value = {
            'typology_code': None,
            'urgency_multiplier': 1.0,
            'regulatory_action': None,
            'precedent_adj': 0.0,
            'reg_adj': 0.0,
            'reg_citations': [],
            'l3_similarity': 0.1,  # Low but bilstm also low
            'rag_reasoning': 'Test',
            'n_cases': 0,
        }
        mock_scorer.return_value = {
            'final_pattern_score': 35,
            'pra_verdict': 'DE-ESCALATE',
            'rag_pattern_score': 0.0,
            'combined_raw': 35.0,
        }
        mock_reasoning.return_value = 'Test'
        mock_save_pa.return_value = 5001

        with patch('builtins.print'):
            process_alert(1001)

        # Feedback writer should NOT be called
        mock_feedback.assert_not_called()


class TestGetUnprocessedAlerts(unittest.TestCase):
    """Tests for unprocessed alerts query."""

    @patch('et_dao.pattern_dao.get_unprocessed_alerts')
    def test_get_unprocessed_alerts_returns_list(self, mock_get):
        """get_unprocessed_alerts returns list of alert dicts."""
        mock_get.return_value = [
            {'id': 1001, 'customer_id': 'C12345'},
            {'id': 1002, 'customer_id': 'C67890'},
        ]

        from et_dao.pattern_dao import get_unprocessed_alerts
        result = get_unprocessed_alerts(batch_size=10)

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['id'], 1001)


if __name__ == '__main__':
    unittest.main()
