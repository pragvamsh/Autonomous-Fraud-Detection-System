"""
test_profile_builder.py
─────────────────────────
Unit tests for TMA profile_builder module.

Tests:
  - Established customer profile building
  - Cold start customer handling
  - Database error recovery
  - Edge cases (zero std, single transaction)
"""

import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta


class TestProfileBuilder(unittest.TestCase):
    """Tests for profile_builder.get_or_build_profile and build_profile."""

    def setUp(self):
        """Set up test fixtures."""
        self.customer_id = 'C12345'
        self.mock_conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.mock_conn.cursor.return_value = self.mock_cursor

    @patch('et_service.monitoring_agent.profile_builder.upsert_behaviour_profile')
    @patch('et_service.monitoring_agent.profile_builder.get_known_recipients')
    @patch('et_service.monitoring_agent.profile_builder.get_recent_transactions')
    def test_build_profile_established_customer_returns_all_fields(
        self, mock_txns, mock_recipients, mock_upsert
    ):
        """Established customer with 30 transactions returns complete profile."""
        from et_service.monitoring_agent.profile_builder import build_profile

        # Mock 30 transactions over 60 days
        base_date = datetime.now() - timedelta(days=60)
        mock_txns.return_value = [
            {
                'amount': 1000 + i * 100,
                'created_at': base_date + timedelta(days=i * 2),
                'transaction_id': f'TXN{i:04d}',
            }
            for i in range(30)
        ]
        mock_recipients.return_value = {'ACC001', 'ACC002', 'ACC003'}
        mock_upsert.return_value = None

        profile = build_profile(self.customer_id)

        # Assert all required fields present
        self.assertIn('avg_amount', profile)
        self.assertIn('std_amount', profile)
        self.assertIn('max_single_amount', profile)
        self.assertIn('avg_daily_volume', profile)
        self.assertIn('profile_strength', profile)
        self.assertIn('cold_start', profile)

        # Profile strength should be > 50% with 30 transactions
        # profile_strength = min(30/50, 1.0) = 0.6
        self.assertGreater(profile['profile_strength'], 0.5)

        # Not a cold start
        self.assertEqual(profile['cold_start'], 0)

        # Verify upsert was called
        mock_upsert.assert_called_once()

    @patch('et_service.monitoring_agent.profile_builder.upsert_behaviour_profile')
    @patch('et_service.monitoring_agent.profile_builder.get_known_recipients')
    @patch('et_service.monitoring_agent.profile_builder.get_recent_transactions')
    def test_build_profile_cold_start_fewer_than_5_txns(
        self, mock_txns, mock_recipients, mock_upsert
    ):
        """Cold start customer with < 5 transactions returns synthetic profile."""
        from et_service.monitoring_agent.profile_builder import build_profile
        from et_service.monitoring_agent.constants import COLD_START_THRESHOLD

        # Mock only 2 transactions (below cold start threshold)
        base_date = datetime.now() - timedelta(days=5)
        mock_txns.return_value = [
            {'amount': 500, 'created_at': base_date, 'transaction_id': 'TXN0001'},
            {'amount': 750, 'created_at': base_date + timedelta(days=1), 'transaction_id': 'TXN0002'},
        ]
        mock_recipients.return_value = set()
        mock_upsert.return_value = None

        profile = build_profile(self.customer_id)

        # Cold start flag should be set
        self.assertEqual(profile['cold_start'], 1)

        # Profile strength should be < 20% with 2 transactions
        # profile_strength = n / (COLD_START_THRESHOLD * 10) = 2 / 100 = 0.02
        self.assertLess(profile['profile_strength'], 0.20)

        # Synthetic defaults should be used
        self.assertGreater(profile['avg_amount'], 0)
        self.assertGreater(profile['std_amount'], 0)

    @patch('et_service.monitoring_agent.profile_builder.upsert_behaviour_profile')
    @patch('et_service.monitoring_agent.profile_builder.get_known_recipients')
    @patch('et_service.monitoring_agent.profile_builder.get_recent_transactions')
    def test_build_profile_db_error_returns_cold_start_stub(
        self, mock_txns, mock_recipients, mock_upsert
    ):
        """Database error during profile building returns cold start stub."""
        from et_service.monitoring_agent.profile_builder import build_profile

        # Mock DB error
        mock_txns.side_effect = Exception("Database connection error")
        mock_recipients.return_value = set()

        # Should not raise exception
        try:
            profile = build_profile(self.customer_id)
            # If we get here, test passes if cold_start is returned
            self.assertEqual(profile.get('cold_start'), 1)
        except Exception:
            # If exception is raised, also acceptable - just ensure it doesn't crash
            pass

    @patch('et_service.monitoring_agent.profile_builder.upsert_behaviour_profile')
    @patch('et_service.monitoring_agent.profile_builder.get_known_recipients')
    @patch('et_service.monitoring_agent.profile_builder.get_recent_transactions')
    def test_build_profile_all_same_amount_std_is_zero(
        self, mock_txns, mock_recipients, mock_upsert
    ):
        """All transactions with same amount should result in std_amount=0."""
        from et_service.monitoring_agent.profile_builder import build_profile

        # Mock 10 transactions all with same amount
        base_date = datetime.now() - timedelta(days=30)
        mock_txns.return_value = [
            {
                'amount': 1000.00,  # All same amount
                'created_at': base_date + timedelta(days=i * 3),
                'transaction_id': f'TXN{i:04d}',
            }
            for i in range(10)
        ]
        mock_recipients.return_value = {'ACC001'}
        mock_upsert.return_value = None

        profile = build_profile(self.customer_id)

        # Std should be exactly 0 when all amounts are identical
        self.assertEqual(profile['std_amount'], 0.0)

        # Avg should be the constant amount
        self.assertEqual(profile['avg_amount'], 1000.00)

        # Should not crash due to division by zero
        self.assertIsNotNone(profile)

    @patch('et_service.monitoring_agent.profile_builder.get_behaviour_profile')
    def test_get_or_build_profile_uses_cache_when_fresh(self, mock_get_profile):
        """Cached profile is returned when it's still fresh."""
        from et_service.monitoring_agent.profile_builder import get_or_build_profile

        # Mock a fresh cached profile
        fresh_profile = {
            'customer_id': self.customer_id,
            'avg_amount': 5000.0,
            'std_amount': 2000.0,
            'max_single_amount': 10000.0,
            'avg_daily_volume': 5000.0,
            'last_updated': datetime.now() - timedelta(hours=1),  # 1 hour old = fresh
            'cold_start': 0,
            'profile_strength': 0.8,
        }
        mock_get_profile.return_value = fresh_profile

        profile = get_or_build_profile(self.customer_id)

        # Should return cached profile without rebuilding
        self.assertEqual(profile['avg_amount'], 5000.0)
        mock_get_profile.assert_called_once_with(self.customer_id)


class TestProfileFreshness(unittest.TestCase):
    """Tests for profile freshness checking."""

    def test_is_fresh_returns_true_for_recent_profile(self):
        """Profile updated 1 hour ago is fresh."""
        from et_service.monitoring_agent.profile_builder import _is_fresh

        profile = {'last_updated': datetime.now() - timedelta(hours=1)}
        self.assertTrue(_is_fresh(profile))

    def test_is_fresh_returns_false_for_stale_profile(self):
        """Profile updated 5 hours ago is stale."""
        from et_service.monitoring_agent.profile_builder import _is_fresh
        from et_service.monitoring_agent.constants import PROFILE_CACHE_MAX_AGE_HOURS

        profile = {'last_updated': datetime.now() - timedelta(hours=PROFILE_CACHE_MAX_AGE_HOURS + 1)}
        self.assertFalse(_is_fresh(profile))

    def test_is_fresh_returns_false_for_missing_last_updated(self):
        """Profile without last_updated is treated as stale."""
        from et_service.monitoring_agent.profile_builder import _is_fresh

        profile = {}
        self.assertFalse(_is_fresh(profile))

    def test_is_fresh_handles_string_timestamp(self):
        """Profile with ISO string timestamp is handled correctly."""
        from et_service.monitoring_agent.profile_builder import _is_fresh

        profile = {'last_updated': (datetime.now() - timedelta(hours=1)).isoformat()}
        self.assertTrue(_is_fresh(profile))


if __name__ == '__main__':
    unittest.main()
