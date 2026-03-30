"""
test_notification_engine.py
────────────────────────────
Unit tests for ABA notification_engine module.

Tests:
  - Verdict-based channel selection
  - Notification queueing
  - Covert mode handling
  - Error resilience
"""

import unittest
from unittest.mock import patch, MagicMock


class TestDispatchNotifications(unittest.TestCase):
    """Tests for dispatch_notifications function."""

    @patch('et_service.aba.notification_engine.save_notification')
    @patch('et_service.aba.notification_engine.get_customer_contact')
    def test_block_verdict_sends_push_email_sms(
        self, mock_contact, mock_save
    ):
        """BLOCK verdict sends PUSH, EMAIL, and SMS."""
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

        # BLOCK sends all 3 channels
        self.assertEqual(result['notifications_queued'], 3)
        self.assertIn('PUSH', result['channels'])
        self.assertIn('EMAIL', result['channels'])
        self.assertIn('SMS', result['channels'])

    @patch('et_service.aba.notification_engine.save_notification')
    @patch('et_service.aba.notification_engine.get_customer_contact')
    def test_alert_verdict_sends_push_only(self, mock_contact, mock_save):
        """ALERT verdict sends PUSH only."""
        from et_service.aba.notification_engine import dispatch_notifications
        from et_service.aba.constants import NOTIFICATION_CHANNELS

        mock_contact.return_value = {
            'email': 'test@test.com',
            'full_name': 'Test User',
        }
        mock_save.return_value = 'NOTIF001'

        payload = {
            'customer_id': 'C12345',
            'alert_id': 1001,
            'typology_code': None,
            'covert_mode': False,
        }

        with patch('builtins.print'):
            result = dispatch_notifications(payload, 'ALERT')

        # ALERT sends specific channels per constant
        expected_channels = NOTIFICATION_CHANNELS.get('ALERT', [])
        self.assertEqual(result['channels'], expected_channels)

    @patch('et_service.aba.notification_engine.save_notification')
    @patch('et_service.aba.notification_engine.get_customer_contact')
    def test_flag_verdict_sends_push_only(self, mock_contact, mock_save):
        """FLAG verdict sends PUSH only."""
        from et_service.aba.notification_engine import dispatch_notifications
        from et_service.aba.constants import NOTIFICATION_CHANNELS

        mock_contact.return_value = {
            'email': 'test@test.com',
            'full_name': 'Test User',
        }
        mock_save.return_value = 'NOTIF001'

        payload = {
            'customer_id': 'C12345',
            'alert_id': 1001,
            'typology_code': None,
            'covert_mode': False,
        }

        with patch('builtins.print'):
            result = dispatch_notifications(payload, 'FLAG')

        expected_channels = NOTIFICATION_CHANNELS.get('FLAG', [])
        self.assertEqual(result['channels'], expected_channels)

    @patch('et_service.aba.notification_engine.get_customer_contact')
    def test_allow_verdict_no_notification(self, mock_contact):
        """ALLOW verdict sends no notification."""
        from et_service.aba.notification_engine import dispatch_notifications

        payload = {
            'customer_id': 'C12345',
            'alert_id': 1001,
            'typology_code': None,
            'covert_mode': False,
        }

        result = dispatch_notifications(payload, 'ALLOW')

        self.assertEqual(result['notifications_queued'], 0)
        self.assertEqual(result['channels'], [])

    @patch('et_service.aba.notification_engine.save_notification')
    @patch('et_service.aba.notification_engine.get_customer_contact')
    def test_notification_queued_to_db(self, mock_contact, mock_save):
        """Notification is saved to database with correct fields."""
        from et_service.aba.notification_engine import dispatch_notifications

        mock_contact.return_value = {
            'email': 'test@test.com',
            'full_name': 'Test User',
            'phone_number': '9876543210',
        }
        mock_save.return_value = 'NOTIF_UUID'

        payload = {
            'customer_id': 'C12345',
            'alert_id': 1001,
            'typology_code': None,
            'covert_mode': False,
        }

        with patch('builtins.print'):
            dispatch_notifications(payload, 'FLAG')

        # Verify save_notification was called with correct structure
        mock_save.assert_called()
        call_args = mock_save.call_args[0][0]
        self.assertEqual(call_args['customer_id'], 'C12345')
        self.assertEqual(call_args['alert_id'], 1001)
        self.assertEqual(call_args['status'], 'PENDING')

    @patch('et_service.aba.notification_engine.save_notification')
    @patch('et_service.aba.notification_engine.get_customer_contact')
    def test_failed_push_does_not_crash_pipeline(
        self, mock_contact, mock_save
    ):
        """Failed PUSH notification doesn't crash - other channels continue."""
        from et_service.aba.notification_engine import dispatch_notifications

        mock_contact.return_value = {
            'email': 'test@test.com',
            'full_name': 'Test User',
            'phone_number': '9876543210',
        }

        # First call (PUSH) fails, others succeed
        mock_save.side_effect = [
            Exception("PUSH failed"),
            'NOTIF_EMAIL',
            'NOTIF_SMS',
        ]

        payload = {
            'customer_id': 'C12345',
            'alert_id': 1001,
            'typology_code': None,
            'covert_mode': False,
        }

        with patch('builtins.print'):
            result = dispatch_notifications(payload, 'BLOCK')

        # Should still queue some notifications despite PUSH failure
        # Actual count depends on which channels succeed
        self.assertIsNotNone(result)


class TestCovertModeNotification(unittest.TestCase):
    """Tests for TY-03 Covert Mode notifications."""

    @patch('et_service.aba.notification_engine.save_notification')
    def test_covert_mode_shows_technical_issue(self, mock_save):
        """Covert Mode shows 'technical issue' message, not fraud."""
        from et_service.aba.notification_engine import _dispatch_covert_notification

        mock_save.return_value = 'NOTIF_COVERT'

        payload = {
            'customer_id': 'C12345',
            'alert_id': 1001,
        }

        with patch('builtins.print'):
            result = _dispatch_covert_notification(payload)

        # Verify covert notification was queued
        self.assertTrue(result.get('covert_mode'))

        # Verify the notification content is covert
        call_args = mock_save.call_args[0][0]
        self.assertEqual(call_args['template'], 'COVERT_TECHNICAL_ISSUE')
        self.assertIn('technical', call_args['payload']['body'].lower())
        self.assertNotIn('fraud', call_args['payload']['body'].lower())


class TestQueueBlockNotifications(unittest.TestCase):
    """Tests for queue_block_notifications function."""

    @patch('et_service.aba.notification_engine.save_notification')
    @patch('et_service.aba.notification_engine.get_customer_contact')
    def test_block_queues_all_channels(self, mock_contact, mock_save):
        """queue_block_notifications queues PUSH, EMAIL, SMS."""
        from et_service.aba.notification_engine import queue_block_notifications

        mock_contact.return_value = {
            'email': 'test@test.com',
            'full_name': 'Test User',
            'phone_number': '9876543210',
        }
        mock_save.return_value = 'NOTIF_ID'

        payload = {
            'customer_id': 'C12345',
            'alert_id': 1001,
            'amount': 5000,
        }

        with patch('builtins.print'):
            result = queue_block_notifications(payload)

        # Should have 3 notifications (PUSH, EMAIL, SMS)
        self.assertEqual(len(result), 3)


if __name__ == '__main__':
    unittest.main()
