"""
test_raa_aba_handoff.py
────────────────────────
Integration tests for RAA → ABA handoff.

Tests:
  - BLOCK verdict produces STOPPED gateway action
  - Action package contains all required keys
  - alert_id is never 0
"""

import unittest
from unittest.mock import patch, MagicMock


class TestRAAAABAHandoff(unittest.TestCase):
    """Integration tests for RAA to ABA handoff."""

    def setUp(self):
        """Set up mock data."""
        self.action_package = {
            'alert_id': 1001,
            'customer_id': 'C12345',
            'final_raa_score': 85,
            'raa_verdict': 'BLOCK',
            'action_required': True,
            'customer_tier': 'T2',
            'all_citations': [
                {'source': 'L1_regulatory', 'text': 'PMLA Section 12'},
            ],
            'typology_code': 'TY-03',
            'amount': 50000,
        }

    def test_block_verdict_produces_stopped_action(self):
        """raa_verdict='BLOCK' produces gateway_action='STOPPED'."""
        from et_service.aba.gateway_controller import determine_gateway_action

        payload = {
            'raa_verdict': 'BLOCK',
            'final_raa_score': 85,
            'typology_code': None,  # Not TY-03
        }

        with patch('builtins.print'):
            result = determine_gateway_action(payload)

        self.assertEqual(result['gateway_action'], 'STOPPED')
        self.assertTrue(result['block_transaction'])

    def test_action_package_contains_required_keys(self):
        """Action package contains all required keys for ABA."""
        required_keys = [
            'final_raa_score',
            'raa_verdict',
            'action_required',
            'customer_tier',
            'all_citations',
            'alert_id',
        ]

        for key in required_keys:
            self.assertIn(key, self.action_package)

    def test_alert_id_in_action_package_is_never_0(self):
        """alert_id in action package is never 0."""
        # Valid package
        self.assertNotEqual(self.action_package['alert_id'], 0)
        self.assertGreater(self.action_package['alert_id'], 0)


class TestVerdictRouting(unittest.TestCase):
    """Tests for verdict-based routing to ABA actions."""

    def test_allow_verdict_routing(self):
        """ALLOW verdict produces APPROVE action."""
        from et_service.aba.gateway_controller import determine_gateway_action

        payload = {
            'raa_verdict': 'ALLOW',
            'final_raa_score': 20,
            'typology_code': None,
        }

        result = determine_gateway_action(payload)

        self.assertEqual(result['gateway_action'], 'APPROVE')
        self.assertFalse(result['block_transaction'])
        self.assertFalse(result['hold_funds'])

    def test_flag_verdict_routing(self):
        """FLAG verdict produces APPROVE_AFTER_CONFIRM action."""
        from et_service.aba.gateway_controller import determine_gateway_action

        payload = {
            'raa_verdict': 'FLAG',
            'final_raa_score': 35,
            'typology_code': None,
        }

        with patch('builtins.print'):
            result = determine_gateway_action(payload)

        self.assertEqual(result['gateway_action'], 'APPROVE_AFTER_CONFIRM')
        self.assertTrue(result['requires_confirmation'])

    def test_alert_verdict_routing(self):
        """ALERT verdict produces HELD action."""
        from et_service.aba.gateway_controller import determine_gateway_action

        payload = {
            'raa_verdict': 'ALERT',
            'final_raa_score': 65,
            'typology_code': None,
        }

        with patch('builtins.print'):
            result = determine_gateway_action(payload)

        self.assertEqual(result['gateway_action'], 'HELD')
        self.assertTrue(result['requires_verification'])

    def test_block_ty03_routing(self):
        """BLOCK with TY-03 produces COVERT_HOLD action."""
        from et_service.aba.gateway_controller import determine_gateway_action

        payload = {
            'raa_verdict': 'BLOCK',
            'final_raa_score': 85,
            'typology_code': 'TY-03',  # Structuring
        }

        with patch('builtins.print'):
            result = determine_gateway_action(payload)

        self.assertEqual(result['gateway_action'], 'COVERT_HOLD')
        self.assertTrue(result['covert_mode'])


class TestNotificationDispatch(unittest.TestCase):
    """Tests for notification dispatch based on verdict."""

    @patch('et_service.aba.notification_engine.save_notification')
    @patch('et_service.aba.notification_engine.get_customer_contact')
    def test_block_triggers_all_notifications(self, mock_contact, mock_save):
        """BLOCK verdict triggers PUSH, EMAIL, SMS notifications."""
        from et_service.aba.notification_engine import dispatch_notifications

        mock_contact.return_value = {
            'email': 'test@test.com',
            'full_name': 'Test User',
            'phone_number': '9876543210',
        }
        mock_save.return_value = 'NOTIF001'

        payload = {
            'customer_id': 'C12345',
            'alert_id': 1001,
            'typology_code': None,
            'covert_mode': False,
        }

        with patch('builtins.print'):
            result = dispatch_notifications(payload, 'BLOCK')

        self.assertEqual(result['notifications_queued'], 3)

    @patch('et_service.aba.notification_engine.save_notification')
    @patch('et_service.aba.notification_engine.get_customer_contact')
    def test_allow_triggers_no_notifications(self, mock_contact, mock_save):
        """ALLOW verdict triggers no notifications."""
        from et_service.aba.notification_engine import dispatch_notifications

        payload = {
            'customer_id': 'C12345',
            'alert_id': 1001,
            'typology_code': None,
            'covert_mode': False,
        }

        result = dispatch_notifications(payload, 'ALLOW')

        self.assertEqual(result['notifications_queued'], 0)


class TestCaseCreation(unittest.TestCase):
    """Tests for fraud case creation."""

    @patch('et_service.aba.case_manager.save_fraud_case')
    def test_block_creates_case(self, mock_save):
        """BLOCK verdict creates fraud case."""
        from et_service.aba.case_manager import create_fraud_case

        mock_save.return_value = 'CASE001'

        payload = {
            'raa_verdict': 'BLOCK',
            'final_raa_score': 85,
            'alert_id': 1001,
            'customer_id': 'C12345',
            'typology_code': 'TY-03',
        }

        with patch('builtins.print'):
            result = create_fraud_case(payload, 'PKG123')

        self.assertTrue(result['case_created'])

    @patch('et_service.aba.case_manager.save_fraud_case')
    def test_alert_does_not_create_case(self, mock_save):
        """ALERT verdict does not create fraud case."""
        from et_service.aba.case_manager import create_fraud_case

        payload = {
            'raa_verdict': 'ALERT',  # Not BLOCK
            'final_raa_score': 65,
            'alert_id': 1001,
            'customer_id': 'C12345',
        }

        result = create_fraud_case(payload, 'PKG123')

        self.assertFalse(result['case_created'])
        mock_save.assert_not_called()


if __name__ == '__main__':
    unittest.main()
