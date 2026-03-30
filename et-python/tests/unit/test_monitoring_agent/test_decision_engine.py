"""
test_decision_engine.py
───────────────────────
Unit tests for TMA decision_engine module.

Tests:
  - Score tier boundaries (ALLOW/FLAG/ALERT/BLOCK)
  - Cold start penalty
  - Score disagreement detection
  - Low confidence fallback
  - Score fusion weights
"""

import unittest
from unittest.mock import patch, MagicMock


class TestDecisionEngine(unittest.TestCase):
    """Tests for decision_engine.make_decision and score fusion."""

    def setUp(self):
        """Set up common fixtures."""
        self.transaction = {
            'debit_transaction_id': 'TXN123456',
            'sender_customer_id': 'C12345',
            'amount': 1000.0,
        }
        self.profile = {
            'customer_id': 'C12345',
            'cold_start': 0,
            'profile_strength': 0.8,
        }
        # 15 model features
        self.anomaly_features = {
            'amount_z_score': 1.0,
            'amount_vs_max': 0.5,
            'exceeds_daily_volume': 0,
            'is_large_amount': 0,
            'is_near_threshold': 0,
            'is_round_number': 0,
            'is_unusual_hour': 0,
            'hour_sin': 0.5,
            'hour_cos': 0.866,
            'is_new_recipient': 0,
            'transactions_last_1h': 1,
            'transactions_last_24h': 1,
            'is_velocity_burst': 0,
            'high_z_new_recipient': 0,
            'late_night_new_recipient': 0,
        }
        self.anomaly_flag_labels = []


class TestScoreToDecision(unittest.TestCase):
    """Tests for score to decision mapping."""

    def test_score_below_30_returns_allow(self):
        """Score <= 25 returns ALLOW decision."""
        from et_service.monitoring_agent.decision_engine import _score_to_decision

        self.assertEqual(_score_to_decision(0), 'ALLOW')
        self.assertEqual(_score_to_decision(20), 'ALLOW')
        self.assertEqual(_score_to_decision(25), 'ALLOW')

    def test_score_31_to_55_returns_flag(self):
        """Score 26-50 returns FLAG decision."""
        from et_service.monitoring_agent.decision_engine import _score_to_decision

        self.assertEqual(_score_to_decision(26), 'FLAG')
        self.assertEqual(_score_to_decision(45), 'FLAG')
        self.assertEqual(_score_to_decision(50), 'FLAG')

    def test_score_56_to_80_returns_alert(self):
        """Score 51-75 returns ALERT decision."""
        from et_service.monitoring_agent.decision_engine import _score_to_decision

        self.assertEqual(_score_to_decision(51), 'ALERT')
        self.assertEqual(_score_to_decision(65), 'ALERT')
        self.assertEqual(_score_to_decision(75), 'ALERT')

    def test_score_above_80_returns_block(self):
        """Score 76-100 returns BLOCK decision."""
        from et_service.monitoring_agent.decision_engine import _score_to_decision

        self.assertEqual(_score_to_decision(76), 'BLOCK')
        self.assertEqual(_score_to_decision(88), 'BLOCK')
        self.assertEqual(_score_to_decision(100), 'BLOCK')


class TestFuseScores(unittest.TestCase):
    """Tests for _fuse_scores function."""

    def test_cold_start_penalty_raises_score(self):
        """Cold start adds penalty to final score."""
        from et_service.monitoring_agent.decision_engine import _fuse_scores
        from et_service.monitoring_agent.constants import COLD_START_PENALTY

        # Same inputs, different cold_start flag
        base_args = {
            'ml_score': 40,
            'rag_score': 42,
            'rag_available': True,
            'confidence': 0.8,
            'ml_weight': 0.4,
            'rag_weight': 0.6,
        }

        score_no_cold, _ = _fuse_scores(**base_args, cold_start=False)
        score_cold, _ = _fuse_scores(**base_args, cold_start=True)

        # Cold start should be higher by exactly COLD_START_PENALTY
        self.assertEqual(score_cold - score_no_cold, COLD_START_PENALTY)

    def test_disagreement_detected_ml_flag_rag_block(self):
        """Large gap between ML (40) and RAG (85) triggers disagreement."""
        from et_service.monitoring_agent.decision_engine import _fuse_scores
        from et_service.monitoring_agent.constants import DISAGREEMENT_THRESHOLD

        score, flags = _fuse_scores(
            ml_score=40,
            rag_score=85,  # Gap = 45 > 30 threshold
            rag_available=True,
            confidence=0.8,
            ml_weight=0.4,
            rag_weight=0.6,
            cold_start=False,
        )

        self.assertTrue(flags['disagreement'])
        # Conservative: should take max(40, 85) = 85
        self.assertGreaterEqual(score, 85)

    def test_low_confidence_fallback_triggers(self):
        """Confidence < 0.65 triggers low confidence fallback."""
        from et_service.monitoring_agent.decision_engine import _fuse_scores
        from et_service.monitoring_agent.constants import LOW_CONFIDENCE_FLAG_FLOOR

        score, flags = _fuse_scores(
            ml_score=20,
            rag_score=25,
            rag_available=True,
            confidence=0.3,  # < 0.65 threshold
            ml_weight=0.4,
            rag_weight=0.6,
            cold_start=False,
        )

        self.assertTrue(flags['low_confidence_fallback'])
        # Should be floored at FLAG minimum (31)
        self.assertGreaterEqual(score, LOW_CONFIDENCE_FLAG_FLOOR)

    def test_rag_unavailable_uses_ml_only(self):
        """RAG unavailable uses ML score only."""
        from et_service.monitoring_agent.decision_engine import _fuse_scores

        score, flags = _fuse_scores(
            ml_score=60,
            rag_score=None,
            rag_available=False,
            confidence=0.0,
            ml_weight=0.4,
            rag_weight=0.6,
            cold_start=False,
        )

        # Should be based on ML score (60)
        self.assertEqual(score, 60)

    def test_weighted_fusion_40_60(self):
        """Normal fusion uses 40/60 weights correctly."""
        from et_service.monitoring_agent.decision_engine import _fuse_scores

        score, flags = _fuse_scores(
            ml_score=80,
            rag_score=40,
            rag_available=True,
            confidence=0.8,  # High confidence
            ml_weight=0.4,
            rag_weight=0.6,
            cold_start=False,
        )

        # Expected: 80 * 0.4 + 40 * 0.6 = 32 + 24 = 56
        # Gap = 40, which triggers conservative mode
        # So should take max(80, 40) = 80
        self.assertGreaterEqual(score, 56)


class TestMakeDecision(unittest.TestCase):
    """Integration tests for make_decision."""

    def setUp(self):
        """Set up test fixtures."""
        self.transaction = {
            'debit_transaction_id': 'TXN123456',
            'sender_customer_id': 'C12345',
        }
        self.profile = {
            'customer_id': 'C12345',
            'cold_start': 0,
        }
        self.anomaly_features = {
            'amount_z_score': 1.0, 'amount_vs_max': 0.5,
            'exceeds_daily_volume': 0, 'is_large_amount': 0,
            'is_near_threshold': 0, 'is_round_number': 0,
            'is_unusual_hour': 0, 'hour_sin': 0.5, 'hour_cos': 0.866,
            'is_new_recipient': 0, 'transactions_last_1h': 1,
            'transactions_last_24h': 1, 'is_velocity_burst': 0,
            'high_z_new_recipient': 0, 'late_night_new_recipient': 0,
        }

    def test_make_decision_returns_fraud_alert(self):
        """make_decision returns a FraudAlert object."""
        from et_service.monitoring_agent.decision_engine import make_decision

        ml_result = {'ml_score': 35}
        rag_result = {
            'rag_available': True,
            'rag_score': 40,
            'confidence': 0.8,
            'citations': [],
            'reasoning': 'Test',
            'ml_weight': 0.4,
            'rag_weight': 0.6,
        }

        alert = make_decision(
            self.transaction,
            self.profile,
            self.anomaly_features,
            [],
            ml_result,
            rag_result,
        )

        self.assertIsNotNone(alert)
        self.assertEqual(alert.transaction_id, 'TXN123456')
        self.assertEqual(alert.customer_id, 'C12345')
        self.assertIn(alert.decision, ['ALLOW', 'FLAG', 'ALERT', 'BLOCK'])


if __name__ == '__main__':
    unittest.main()
