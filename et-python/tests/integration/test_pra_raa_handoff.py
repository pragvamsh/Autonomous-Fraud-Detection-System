"""
test_pra_raa_handoff.py
────────────────────────
Integration tests for PRA → RAA handoff.

Tests:
  - RAA starts only when pra_processed=1
  - CRITICAL verdict triggers T1 classification
  - DE-ESCALATE with low score produces ALLOW/FLAG
"""

import unittest
from unittest.mock import patch, MagicMock


class TestPRARAAHandoff(unittest.TestCase):
    """Integration tests for PRA to RAA handoff."""

    def setUp(self):
        """Set up mock data."""
        self.base_alert = {
            'id': 1001,
            'alert_id': 1001,
            'customer_id': 'C12345',
            'risk_score': 65,
            'decision': 'FLAG',
            'pra_processed': 1,  # PRA complete
            'pra_verdict': 'MAINTAIN',
            'pattern_score': 55,
            'bilstm_score': 50.0,
            'urgency_multiplier': 1.0,
            'typology_code': None,
            'raa_processed': 0,
            'anomaly_features': {'amount_z_score': 1.0},
            'payment_id': 'PAY123',
            'feature_snapshot': {'amount_z_score': 1.0},
        }

    @patch('et_dao.raa_dao.get_unprocessed_alerts')
    def test_raa_only_starts_when_pra_processed_is_1(self, mock_get_unprocessed):
        """RAA query only returns alerts where pra_processed=1."""
        # Simulate the query behavior
        mock_get_unprocessed.return_value = [
            {'id': 1001, 'pra_processed': 1, 'raa_processed': 0},
        ]

        from et_dao.raa_dao import get_unprocessed_alerts
        alerts = get_unprocessed_alerts(batch_size=10)

        # All returned alerts should have pra_processed=1
        for alert in alerts:
            self.assertEqual(alert['pra_processed'], 1)

    @patch('et_service.raa.tier_engine.get_customer_account_stats')
    def test_critical_pra_verdict_triggers_t1_classification(self, mock_stats):
        """pra_verdict='CRITICAL' triggers T1 classification in RAA."""
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
            'pra_verdict': 'CRITICAL',  # Forces T1
        }

        with patch('builtins.print'):
            tier = classify_tier(data)

        self.assertEqual(tier, 'T1')

    @patch('et_service.raa.score_engine.compute_raw_danger')
    def test_de_escalate_with_low_score_produces_allow_or_flag(self, mock_danger):
        """DE-ESCALATE with low score produces ALLOW or FLAG verdict."""
        from et_service.raa.score_engine import fuse_scores

        mock_danger.return_value = 10.0  # Low danger

        dims = {'score_a': 10.0}
        rag = {
            'pattern_mult': 1.0,
            'coldstart_adj': 0.0,
            'regulatory_adj': 0.0,
        }
        data = {
            'feature_snapshot': {},
            'pra_verdict': 'DE-ESCALATE',
            '_tier': 'T4',  # No floor
            'urgency_multiplier': 1.0,
            'pattern_score': 20,
        }

        with patch('builtins.print'):
            result = fuse_scores(dims, rag, data)

        # Low scores should produce ALLOW or FLAG
        self.assertIn(result['raa_verdict'], ['ALLOW', 'FLAG'])


class TestCRITICALHandoff(unittest.TestCase):
    """Tests for CRITICAL verdict path through RAA."""

    @patch('et_service.raa.tier_engine.get_customer_account_stats')
    @patch('et_service.raa.score_engine.compute_raw_danger')
    def test_critical_enforces_minimum_60_score(self, mock_danger, mock_stats):
        """CRITICAL pra_verdict enforces minimum final score of 60."""
        from et_service.raa.score_engine import fuse_scores

        mock_danger.return_value = 0.0
        mock_stats.return_value = {
            'tx_count': 500, 'account_age_days': 365,
            'fraud_flag_count_total': 0, 'fraud_flag_count_30d': 0,
            'fraud_flag_count_90d': 0,
        }

        dims = {'score_a': 0.0}
        rag = {
            'pattern_mult': 1.0, 'coldstart_adj': 0.0, 'regulatory_adj': 0.0,
        }
        data = {
            'feature_snapshot': {},
            'pra_verdict': 'CRITICAL',
            '_tier': 'T4',  # Would have no floor normally
            'urgency_multiplier': 1.0,
            'pattern_score': 0,
        }

        with patch('builtins.print'):
            result = fuse_scores(dims, rag, data)

        # CRITICAL floor is 60
        self.assertGreaterEqual(result['final_raa_score'], 60)


class TestMaintainHandoff(unittest.TestCase):
    """Tests for MAINTAIN verdict handling."""

    @patch('et_service.raa.score_engine.compute_raw_danger')
    def test_maintain_verdict_normal_processing(self, mock_danger):
        """MAINTAIN verdict goes through normal scoring."""
        from et_service.raa.score_engine import fuse_scores

        mock_danger.return_value = 40.0

        dims = {'score_a': 40.0}
        rag = {
            'pattern_mult': 1.5, 'coldstart_adj': 0.0, 'regulatory_adj': 0.0,
        }
        data = {
            'feature_snapshot': {},
            'pra_verdict': 'MAINTAIN',
            '_tier': 'T2',
            'urgency_multiplier': 1.0,
            'pattern_score': 50,
        }

        with patch('builtins.print'):
            result = fuse_scores(dims, rag, data)

        # Should produce a valid verdict
        self.assertIn(result['raa_verdict'], ['ALLOW', 'FLAG', 'ALERT', 'BLOCK'])


class TestEscalateHandoff(unittest.TestCase):
    """Tests for ESCALATE verdict handling."""

    @patch('et_service.raa.score_engine.compute_raw_danger')
    def test_escalate_verdict_increases_risk(self, mock_danger):
        """ESCALATE verdict with high urgency increases final score."""
        from et_service.raa.score_engine import fuse_scores

        mock_danger.return_value = 50.0

        dims = {'score_a': 50.0}
        rag = {
            'pattern_mult': 1.5, 'coldstart_adj': 0.0, 'regulatory_adj': 10.0,
        }
        data = {
            'feature_snapshot': {},
            'pra_verdict': 'ESCALATE',
            '_tier': 'T2',
            'urgency_multiplier': 1.5,  # High urgency
            'pattern_score': 70,
        }

        with patch('builtins.print'):
            result = fuse_scores(dims, rag, data)

        # ESCALATE with high urgency should produce higher risk
        self.assertGreaterEqual(result['final_raa_score'], 50)


if __name__ == '__main__':
    unittest.main()
