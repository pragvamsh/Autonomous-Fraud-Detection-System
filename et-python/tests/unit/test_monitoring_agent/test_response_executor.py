"""
test_response_executor.py
──────────────────────────
Unit tests for TMA response_executor module.

Tests:
  - Alert saving and ID return
  - Verdict-based notifications
  - Block verdict rejection flow
  - Allow verdict silent handling
"""

import unittest
from unittest.mock import patch, MagicMock


class TestResponseExecutor(unittest.TestCase):
    """Tests for response_executor.execute_response function."""

    def setUp(self):
        """Set up common fixtures."""
        self.mock_alert = MagicMock()
        self.mock_alert.transaction_id = 'TXN123456'
        self.mock_alert.customer_id = 'C12345'
        self.mock_alert.risk_score = 65
        self.mock_alert.ml_score = 60
        self.mock_alert.rag_score = 70
        self.mock_alert.decision = 'FLAG'
        self.mock_alert.fraud_flag = 1
        self.mock_alert.agent_status = 'EVALUATED'
        self.mock_alert.anomaly_flags_list = ['TEST_FLAG']
        self.mock_alert.agent_reasoning = 'Test reasoning'
        self.mock_alert.fallback_mode = False
        self.mock_alert.cold_start_profile = False
        self.mock_alert.to_db_dict.return_value = {'alert': 'dict'}

    @patch('et_service.monitoring_agent.response_executor._fire_pattern_agent_for_alert')
    @patch('et_service.monitoring_agent.response_executor.backfill_tma_result')
    @patch('et_service.monitoring_agent.response_executor.update_payment_fraud_result')
    @patch('et_service.monitoring_agent.response_executor.update_transaction_after_evaluation')
    @patch('et_service.monitoring_agent.response_executor.save_fraud_alert')
    def test_execute_saves_alert_returns_alert_id(
        self, mock_save, mock_update_txn, mock_update_pmt, mock_backfill, mock_fire_pra
    ):
        """execute_response saves alert and returns alert_id."""
        from et_service.monitoring_agent.response_executor import execute_response

        mock_save.return_value = 42  # alert_id
        mock_backfill.return_value = False
        mock_fire_pra.return_value = None

        with patch('builtins.print'):
            result = execute_response(self.mock_alert, 'PAY123')

        self.assertEqual(result['alert_id'], 42)
        mock_save.assert_called_once()

    @patch('et_service.monitoring_agent.response_executor._fire_pattern_agent_for_alert')
    @patch('et_service.monitoring_agent.response_executor.backfill_tma_result')
    @patch('et_service.monitoring_agent.response_executor.update_payment_fraud_result')
    @patch('et_service.monitoring_agent.response_executor.update_transaction_after_evaluation')
    @patch('et_service.monitoring_agent.response_executor.save_fraud_alert')
    def test_execute_alert_verdict_triggers_notification(
        self, mock_save, mock_update_txn, mock_update_pmt, mock_backfill, mock_fire_pra
    ):
        """ALERT verdict triggers customer notification logging."""
        from et_service.monitoring_agent.response_executor import execute_response

        mock_save.return_value = 42
        mock_backfill.return_value = False
        self.mock_alert.decision = 'ALERT'

        with patch('builtins.print') as mock_print:
            result = execute_response(self.mock_alert, 'PAY123')

        # Should print alert notification
        self.assertEqual(result['action_taken'], 'CUSTOMER_ALERT_TRIGGERED')

    @patch('et_service.monitoring_agent.response_executor._fire_pattern_agent_for_alert')
    @patch('et_service.monitoring_agent.response_executor.backfill_tma_result')
    @patch('et_service.monitoring_agent.response_executor.update_payment_fraud_result')
    @patch('et_service.monitoring_agent.response_executor.update_transaction_after_evaluation')
    @patch('et_service.monitoring_agent.response_executor.save_fraud_alert')
    def test_execute_block_verdict_calls_reversal(
        self, mock_save, mock_update_txn, mock_update_pmt, mock_backfill, mock_fire_pra
    ):
        """BLOCK verdict initiates reversal and restriction."""
        from et_service.monitoring_agent.response_executor import execute_response

        mock_save.return_value = 42
        mock_backfill.return_value = False
        self.mock_alert.decision = 'BLOCK'
        self.mock_alert.risk_score = 85
        self.mock_alert.disagreement = False

        with patch('builtins.print'):
            result = execute_response(self.mock_alert, 'PAY123')

        self.assertEqual(result['action_taken'], 'BLOCK_AND_REVERSAL_INITIATED')

    @patch('et_service.monitoring_agent.response_executor._fire_pattern_agent_for_alert')
    @patch('et_service.monitoring_agent.response_executor.backfill_tma_result')
    @patch('et_service.monitoring_agent.response_executor.update_payment_fraud_result')
    @patch('et_service.monitoring_agent.response_executor.update_transaction_after_evaluation')
    @patch('et_service.monitoring_agent.response_executor.save_fraud_alert')
    def test_execute_allow_verdict_no_notification_sent(
        self, mock_save, mock_update_txn, mock_update_pmt, mock_backfill, mock_fire_pra
    ):
        """ALLOW verdict does silent log only - no notification."""
        from et_service.monitoring_agent.response_executor import execute_response

        mock_save.return_value = 42
        mock_backfill.return_value = False
        self.mock_alert.decision = 'ALLOW'
        self.mock_alert.risk_score = 20

        with patch('builtins.print'):
            result = execute_response(self.mock_alert, 'PAY123')

        self.assertEqual(result['action_taken'], 'SILENT_LOG')


class TestExecuteAction(unittest.TestCase):
    """Tests for _execute_action internal function."""

    def test_action_allow_returns_silent_log(self):
        """ALLOW decision returns SILENT_LOG action."""
        from et_service.monitoring_agent.response_executor import _execute_action

        alert = MagicMock()
        alert.decision = 'ALLOW'
        alert.risk_score = 20
        alert.transaction_id = 'TXN123'
        alert.ml_score = 18
        alert.rag_score = 22
        alert.fallback_mode = False
        alert.cold_start_profile = False
        alert.anomaly_flags_list = []
        alert.agent_reasoning = ''

        with patch('builtins.print'):
            result = _execute_action(alert)

        self.assertEqual(result, 'SILENT_LOG')

    def test_action_flag_returns_review_queue(self):
        """FLAG decision returns ADDED_TO_REVIEW_QUEUE action."""
        from et_service.monitoring_agent.response_executor import _execute_action

        alert = MagicMock()
        alert.decision = 'FLAG'
        alert.risk_score = 40
        alert.transaction_id = 'TXN123'
        alert.ml_score = 38
        alert.rag_score = 42
        alert.fallback_mode = False
        alert.cold_start_profile = False
        alert.anomaly_flags_list = []
        alert.agent_reasoning = ''

        with patch('builtins.print'):
            result = _execute_action(alert)

        self.assertEqual(result, 'ADDED_TO_REVIEW_QUEUE')

    def test_action_unknown_decision(self):
        """Unknown decision returns UNKNOWN_DECISION."""
        from et_service.monitoring_agent.response_executor import _execute_action

        alert = MagicMock()
        alert.decision = 'UNKNOWN'

        with patch('builtins.print'):
            result = _execute_action(alert)

        self.assertEqual(result, 'UNKNOWN_DECISION')


class TestFirePatternAgent(unittest.TestCase):
    """Tests for _fire_pattern_agent_for_alert."""

    @patch('threading.Thread')
    def test_fire_pattern_agent_starts_thread(self, mock_thread_class):
        """Pattern agent is fired in a daemon thread."""
        from et_service.monitoring_agent.response_executor import _fire_pattern_agent_for_alert

        mock_thread = MagicMock()
        mock_thread_class.return_value = mock_thread

        _fire_pattern_agent_for_alert(alert_id=42, payment_id='PAY123')

        # Thread should be created and started
        mock_thread_class.assert_called_once()
        mock_thread.start.assert_called_once()


if __name__ == '__main__':
    unittest.main()
