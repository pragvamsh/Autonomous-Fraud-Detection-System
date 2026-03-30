"""
test_tier_engine.py
────────────────────
Unit tests for RAA tier_engine module.

Tests:
  - CRITICAL demotion rule
  - T1/T2/T3/T4 classification conditions
  - Fallback to T2
  - Database error handling
"""

import unittest
from unittest.mock import patch, MagicMock


class TestClassifyTier(unittest.TestCase):
    """Tests for tier_engine.classify_tier function."""

    @patch('et_service.raa.tier_engine.get_customer_account_stats')
    def test_critical_pra_verdict_forces_t1_regardless_of_history(self, mock_stats):
        """CRITICAL pra_verdict always returns T1, regardless of stats."""
        from et_service.raa.tier_engine import classify_tier

        # Even T4-level stats
        mock_stats.return_value = {
            'tx_count': 500,
            'account_age_days': 365,
            'fraud_flag_count_total': 0,
            'fraud_flag_count_30d': 0,
            'fraud_flag_count_90d': 0,
        }

        data = {
            'customer_id': 'C12345',
            'pra_verdict': 'CRITICAL',
        }

        with patch('builtins.print'):
            tier = classify_tier(data)

        self.assertEqual(tier, 'T1')

    @patch('et_service.raa.tier_engine.get_customer_account_stats')
    def test_critical_checked_before_db_lookup(self, mock_stats):
        """CRITICAL returns T1 without crashing even if DB fails."""
        from et_service.raa.tier_engine import classify_tier

        # DB lookup will fail
        mock_stats.side_effect = Exception("Database error")

        data = {
            'customer_id': 'C12345',
            'pra_verdict': 'CRITICAL',
        }

        with patch('builtins.print'):
            tier = classify_tier(data)

        # CRITICAL check happens first
        self.assertEqual(tier, 'T1')

    @patch('et_service.raa.tier_engine.get_customer_account_stats')
    def test_t4_veteran_all_conditions_met(self, mock_stats):
        """T4 classification when all veteran conditions met."""
        from et_service.raa.tier_engine import classify_tier

        mock_stats.return_value = {
            'tx_count': 250,           # >= 200
            'account_age_days': 200,   # >= 180
            'fraud_flag_count_total': 0,
            'fraud_flag_count_30d': 0,
            'fraud_flag_count_90d': 0,  # == 0
        }

        data = {
            'customer_id': 'C12345',
            'pra_verdict': 'MAINTAIN',
        }

        with patch('builtins.print'):
            tier = classify_tier(data)

        self.assertEqual(tier, 'T4')

    @patch('et_service.raa.tier_engine.get_customer_account_stats')
    def test_t4_checked_before_t3_prevents_misclassification(self, mock_stats):
        """T4-eligible customer is not classified as T3."""
        from et_service.raa.tier_engine import classify_tier

        # Customer qualifies for both T4 and T3 conditions
        mock_stats.return_value = {
            'tx_count': 250,           # >= 200 (T4) and >= 50 (T3)
            'account_age_days': 200,   # >= 180 (T4) and >= 60 (T3)
            'fraud_flag_count_total': 0,
            'fraud_flag_count_30d': 0,
            'fraud_flag_count_90d': 0,
        }

        data = {'customer_id': 'C12345', 'pra_verdict': 'ESCALATE'}

        with patch('builtins.print'):
            tier = classify_tier(data)

        # T4 should be checked first
        self.assertEqual(tier, 'T4')

    @patch('et_service.raa.tier_engine.get_customer_account_stats')
    def test_t3_mature_conditions(self, mock_stats):
        """T3 classification when mature conditions met."""
        from et_service.raa.tier_engine import classify_tier

        mock_stats.return_value = {
            'tx_count': 60,            # >= 50
            'account_age_days': 90,    # >= 60
            'fraud_flag_count_total': 1,  # Some total flags
            'fraud_flag_count_30d': 0,    # == 0 in last 30d
            'fraud_flag_count_90d': 1,
        }

        data = {'customer_id': 'C12345', 'pra_verdict': 'MAINTAIN'}

        with patch('builtins.print'):
            tier = classify_tier(data)

        self.assertEqual(tier, 'T3')

    @patch('et_service.raa.tier_engine.get_customer_account_stats')
    def test_t2_growing_conditions(self, mock_stats):
        """T2 classification when growing conditions met."""
        from et_service.raa.tier_engine import classify_tier

        mock_stats.return_value = {
            'tx_count': 20,            # >= 15
            'account_age_days': 20,    # >= 14
            'fraud_flag_count_total': 0,  # == 0 total
            'fraud_flag_count_30d': 0,
            'fraud_flag_count_90d': 0,
        }

        data = {'customer_id': 'C12345', 'pra_verdict': 'MAINTAIN'}

        with patch('builtins.print'):
            tier = classify_tier(data)

        self.assertEqual(tier, 'T2')

    @patch('et_service.raa.tier_engine.get_customer_account_stats')
    def test_t1_new_with_fraud_flags(self, mock_stats):
        """T1 classification for new customer with fraud flags."""
        from et_service.raa.tier_engine import classify_tier

        mock_stats.return_value = {
            'tx_count': 5,             # < 15
            'account_age_days': 7,     # < 14
            'fraud_flag_count_total': 2,  # > 0
            'fraud_flag_count_30d': 2,
            'fraud_flag_count_90d': 2,
        }

        data = {'customer_id': 'C12345', 'pra_verdict': 'ESCALATE'}

        with patch('builtins.print'):
            tier = classify_tier(data)

        self.assertEqual(tier, 'T1')

    @patch('et_service.raa.tier_engine.get_customer_account_stats')
    def test_fallback_to_t2_when_no_tier_matches(self, mock_stats):
        """Moderate customer with some flags gets T2 fallback."""
        from et_service.raa.tier_engine import classify_tier

        # Customer doesn't fit cleanly into any tier
        mock_stats.return_value = {
            'tx_count': 30,             # Between tiers
            'account_age_days': 45,     # Between tiers
            'fraud_flag_count_total': 1,  # Some flags
            'fraud_flag_count_30d': 1,
            'fraud_flag_count_90d': 1,
        }

        data = {'customer_id': 'C12345', 'pra_verdict': 'MAINTAIN'}

        with patch('builtins.print'):
            tier = classify_tier(data)

        self.assertEqual(tier, 'T2')

    @patch('et_service.raa.tier_engine.get_customer_account_stats')
    def test_db_error_defaults_to_t1(self, mock_stats):
        """Database error defaults to T1 (conservative)."""
        from et_service.raa.tier_engine import classify_tier

        mock_stats.side_effect = Exception("Database connection failed")

        data = {'customer_id': 'C12345', 'pra_verdict': 'ESCALATE'}

        with patch('builtins.print'):
            tier = classify_tier(data)

        self.assertEqual(tier, 'T1')


class TestTierConstants(unittest.TestCase):
    """Tests for tier-related constants."""

    def test_tier_floors_defined(self):
        """TIER_FLOORS has all expected tiers."""
        from et_service.raa.tier_engine import TIER_FLOORS

        self.assertIn('T1', TIER_FLOORS)
        self.assertIn('T2', TIER_FLOORS)
        self.assertIn('T3', TIER_FLOORS)
        self.assertIn('T4', TIER_FLOORS)

        # T1 should have highest floor, T4 lowest
        self.assertGreater(TIER_FLOORS['T1'], TIER_FLOORS['T4'])

    def test_tier_weights_defined(self):
        """TIER_WEIGHTS has all expected tiers with dimension weights."""
        from et_service.raa.tier_engine import TIER_WEIGHTS

        for tier in ['T1', 'T2', 'T3', 'T4']:
            self.assertIn(tier, TIER_WEIGHTS)
            weights = TIER_WEIGHTS[tier]
            # Should have 5 dimension weights
            self.assertEqual(len(weights), 5)
            # Weights should sum to ~1.0
            self.assertAlmostEqual(sum(weights.values()), 1.0, places=2)


if __name__ == '__main__':
    unittest.main()
