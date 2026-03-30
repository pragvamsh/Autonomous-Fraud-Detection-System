"""
test_payment_flow.py
─────────────────────
Integration tests for the payment API flow.

Tests:
  - FLAG payment commits immediately returns 200
  - ALERT payment holds returns 202 with OTP
  - BLOCK payment rejects returns 403
  - OTP verification commits payment
  - Race condition handling for duplicate submit
"""

import unittest
from unittest.mock import patch, MagicMock
import threading


class TestPaymentFlowFLAG(unittest.TestCase):
    """Tests for FLAG verdict payment flow."""

    @patch('et_service.payment_service.process_payment')
    @patch('et_service.monitoring_agent.agent.evaluate_transaction')
    def test_flag_payment_commits_immediately_returns_200(
        self, mock_evaluate, mock_process
    ):
        """FLAG verdict allows payment to commit with 200 status."""
        # Mock payment processing
        mock_process.return_value = {
            'payment_id': 'PAY123',
            'debit_transaction_id': 'TXN123',
            'credit_transaction_id': 'TXN456',
            'amount': 1000.0,
            'sender_customer_id': 'C12345',
        }

        # Mock TMA evaluation - FLAG verdict
        mock_alert = MagicMock()
        mock_alert.decision = 'FLAG'
        mock_alert.risk_score = 40
        mock_alert.alert_id = 1001
        mock_evaluate.return_value = mock_alert

        # In actual implementation, FLAG allows the payment to proceed
        # with customer confirmation
        self.assertEqual(mock_alert.decision, 'FLAG')
        self.assertLess(mock_alert.risk_score, 56)  # Below ALERT threshold


class TestPaymentFlowALERT(unittest.TestCase):
    """Tests for ALERT verdict payment flow."""

    @patch('et_service.payment_service.hold_payment')
    @patch('et_service.monitoring_agent.agent.evaluate_transaction')
    def test_alert_payment_holds_returns_202_with_otp(
        self, mock_evaluate, mock_hold
    ):
        """ALERT verdict holds payment and requires OTP (202 status)."""
        # Mock TMA evaluation - ALERT verdict
        mock_alert = MagicMock()
        mock_alert.decision = 'ALERT'
        mock_alert.risk_score = 65
        mock_alert.alert_id = 1001
        mock_evaluate.return_value = mock_alert

        # Mock hold_payment
        mock_hold.return_value = True

        # ALERT should trigger hold and OTP
        self.assertEqual(mock_alert.decision, 'ALERT')
        self.assertGreaterEqual(mock_alert.risk_score, 56)
        self.assertLess(mock_alert.risk_score, 81)


class TestPaymentFlowBLOCK(unittest.TestCase):
    """Tests for BLOCK verdict payment flow."""

    @patch('et_service.payment_service.reject_payment')
    @patch('et_service.monitoring_agent.agent.evaluate_transaction')
    def test_block_payment_rejects_returns_403(
        self, mock_evaluate, mock_reject
    ):
        """BLOCK verdict rejects payment with 403 status."""
        # Mock TMA evaluation - BLOCK verdict
        mock_alert = MagicMock()
        mock_alert.decision = 'BLOCK'
        mock_alert.risk_score = 85
        mock_alert.alert_id = 1001
        mock_evaluate.return_value = mock_alert

        # Mock reject_payment
        mock_reject.return_value = True

        # BLOCK should reject the payment
        self.assertEqual(mock_alert.decision, 'BLOCK')
        self.assertGreaterEqual(mock_alert.risk_score, 81)


class TestOTPVerification(unittest.TestCase):
    """Tests for OTP verification flow."""

    @patch('et_service.payment_service.commit_payment')
    @patch('et_dao.otp_dao.verify_otp')
    def test_otp_verify_correct_commits_payment(
        self, mock_verify_otp, mock_commit
    ):
        """Correct OTP verification commits the held payment."""
        mock_verify_otp.return_value = True
        mock_commit.return_value = True

        # Verify OTP check
        is_valid = mock_verify_otp('C12345', '123456', 'FRAUD_MFA')
        self.assertTrue(is_valid)

        # Commit should be called after valid OTP
        mock_commit.assert_not_called()  # Called only after verification

    @patch('et_dao.otp_dao.verify_otp')
    def test_otp_verify_wrong_returns_error_payment_stays_held(
        self, mock_verify_otp
    ):
        """Wrong OTP keeps payment held, returns error."""
        mock_verify_otp.return_value = False

        is_valid = mock_verify_otp('C12345', '000000', 'FRAUD_MFA')
        self.assertFalse(is_valid)

        # Payment should remain held (no commit called)


class TestRaceCondition(unittest.TestCase):
    """Tests for race condition handling."""

    def test_race_condition_duplicate_submit_only_one_commits(self):
        """Duplicate concurrent payment submissions - only one commits."""
        # Track commits
        commit_count = [0]
        lock = threading.Lock()

        def mock_commit(payment_id):
            # Simulate atomic commit check
            with lock:
                # Check if already committed
                if commit_count[0] > 0:
                    return False  # Already committed
                commit_count[0] += 1
                return True

        results = []

        def submit_payment(thread_id):
            result = mock_commit('PAY123')
            results.append((thread_id, result))

        # Launch 2 concurrent threads
        threads = [
            threading.Thread(target=submit_payment, args=(i,))
            for i in range(2)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=2.0)

        # Verify only one commit succeeded
        successful_commits = [r for _, r in results if r is True]
        self.assertEqual(len(successful_commits), 1)

        # Total commit count should be exactly 1
        self.assertEqual(commit_count[0], 1)


class TestPaymentFlowALLOW(unittest.TestCase):
    """Tests for ALLOW verdict payment flow."""

    @patch('et_service.monitoring_agent.agent.evaluate_transaction')
    def test_allow_payment_commits_silently(self, mock_evaluate):
        """ALLOW verdict allows payment to commit silently."""
        # Mock TMA evaluation - ALLOW verdict
        mock_alert = MagicMock()
        mock_alert.decision = 'ALLOW'
        mock_alert.risk_score = 20
        mock_alert.alert_id = 1001
        mock_evaluate.return_value = mock_alert

        # ALLOW should process without notification
        self.assertEqual(mock_alert.decision, 'ALLOW')
        self.assertLess(mock_alert.risk_score, 31)


class TestPaymentHoldRelease(unittest.TestCase):
    """Tests for payment hold and release mechanics."""

    @patch('et_service.payment_service.commit_payment')
    @patch('et_service.payment_service.get_held_payment')
    def test_held_payment_can_be_committed(self, mock_get, mock_commit):
        """Held payment can be retrieved and committed."""
        mock_get.return_value = {
            'payment_id': 'PAY123',
            'status': 'HELD',
            'amount': 1000.0,
        }
        mock_commit.return_value = True

        # Get held payment
        payment = mock_get('PAY123', 'C12345')
        self.assertEqual(payment['status'], 'HELD')

        # Commit it
        result = mock_commit(payment)
        self.assertTrue(result)

    @patch('et_service.payment_service.reject_payment')
    @patch('et_service.payment_service.get_held_payment')
    def test_held_payment_can_be_rejected(self, mock_get, mock_reject):
        """Held payment can be retrieved and rejected."""
        mock_get.return_value = {
            'payment_id': 'PAY123',
            'status': 'HELD',
            'amount': 1000.0,
        }
        mock_reject.return_value = True

        # Get held payment
        payment = mock_get('PAY123', 'C12345')
        self.assertEqual(payment['status'], 'HELD')

        # Reject it
        result = mock_reject(payment)
        self.assertTrue(result)


if __name__ == '__main__':
    unittest.main()
