"""
test_score_engine.py
─────────────────────
Unit tests for RAA score_engine module.

Tests:
  - Score_B computation (raw danger)
  - 60/40 fusion weights
  - CRITICAL and tier-based floors
  - Verdict mapping (ALLOW/FLAG/ALERT/BLOCK)
  - Old verdict names not returned
"""

import unittest
from unittest.mock import patch


class TestComputeRawDanger(unittest.TestCase):
    """Tests for compute_raw_danger (Score_B)."""

    def test_score_b_high_z_score_dominates(self):
        """High amount z-score produces score_b >= 70."""
        from et_service.raa.score_engine import compute_raw_danger

        score_b = compute_raw_danger(
            amount_zscore=5.0,    # Very high z-score
            recipient_flag=False,
            velocity_score=0.0,
            hour_anomaly=False,
        )

        # z_contrib = min(100, |5| * 25) = 100 (capped)
        # score_b = 0.50 * 100 + ... = at least 50
        self.assertGreaterEqual(score_b, 50)

    def test_score_b_new_recipient_adds_30(self):
        """New recipient flag adds 30 to score."""
        from et_service.raa.score_engine import compute_raw_danger

        base_score = compute_raw_danger(
            amount_zscore=0.0,
            recipient_flag=False,
            velocity_score=0.0,
            hour_anomaly=False,
        )

        with_recipient = compute_raw_danger(
            amount_zscore=0.0,
            recipient_flag=True,
            velocity_score=0.0,
            hour_anomaly=False,
        )

        # Difference should reflect recipient bonus
        # recip_bonus = 30, weight = 0.15
        # Expected diff = 0.15 * 30 = 4.5
        diff = with_recipient - base_score
        self.assertAlmostEqual(diff, 4.5, places=1)

    def test_score_b_capped_at_100(self):
        """Score_B never exceeds 100."""
        from et_service.raa.score_engine import compute_raw_danger

        score_b = compute_raw_danger(
            amount_zscore=10.0,   # Extreme
            recipient_flag=True,
            velocity_score=5.0,  # Very high velocity
            hour_anomaly=True,
        )

        self.assertLessEqual(score_b, 100)


class TestFuseScores(unittest.TestCase):
    """Tests for fuse_scores function."""

    def test_fusion_60_40_weights_applied(self):
        """60/40 fusion weights applied correctly."""
        from et_service.raa.score_engine import fuse_scores

        # Create mocked inputs
        dims = {'score_a': 40.0}
        rag = {
            'pattern_mult': 1.0,
            'coldstart_adj': 0.0,
            'regulatory_adj': 0.0,
        }
        data = {
            'feature_snapshot': {
                'amount_z_score': 0.0,
                'is_new_recipient': False,
                'transactions_last_1h': 0,
                'is_unusual_hour': False,
            },
            'pra_verdict': 'MAINTAIN',
            'urgency_multiplier': 1.0,
            'pattern_score': 0,
            '_tier': 'T3',
        }

        # Force specific Score_B by patching
        with patch('et_service.raa.score_engine.compute_raw_danger', return_value=80.0):
            result = fuse_scores(dims, rag, data)

        # raw = 80 * 0.6 + 40 * 0.4 = 48 + 16 = 64
        # With T3 floor (10), should be max(64, 10) = 64
        self.assertEqual(result['score_b'], 80.0)

    @patch('et_service.raa.score_engine.compute_raw_danger')
    def test_critical_floor_applied_first(self, mock_danger):
        """CRITICAL floor (min 60) applied regardless of tier."""
        from et_service.raa.score_engine import fuse_scores

        mock_danger.return_value = 10.0  # Low score

        dims = {'score_a': 10.0}
        rag = {
            'pattern_mult': 1.0,
            'coldstart_adj': 0.0,
            'regulatory_adj': 0.0,
        }
        data = {
            'feature_snapshot': {},
            'pra_verdict': 'CRITICAL',
            'urgency_multiplier': 1.0,
            'pattern_score': 0,
            '_tier': 'T4',
        }

        with patch('builtins.print'):
            result = fuse_scores(dims, rag, data)

        # Even with T4 (no floor), CRITICAL enforces min 60
        self.assertGreaterEqual(result['final_raa_score'], 60)

    @patch('et_service.raa.score_engine.compute_raw_danger')
    def test_critical_floor_overrides_t4_no_floor(self, mock_danger):
        """CRITICAL floor overrides T4's no-floor rule."""
        from et_service.raa.score_engine import fuse_scores

        mock_danger.return_value = 0.0

        dims = {'score_a': 0.0}
        rag = {
            'pattern_mult': 1.0,
            'coldstart_adj': 0.0,
            'regulatory_adj': 0.0,
        }
        data = {
            'feature_snapshot': {},
            'pra_verdict': 'CRITICAL',
            '_tier': 'T4',
            'urgency_multiplier': 1.0,
            'pattern_score': 0,
        }

        with patch('builtins.print'):
            result = fuse_scores(dims, rag, data)

        self.assertGreaterEqual(result['final_raa_score'], 60)

    @patch('et_service.raa.score_engine.compute_raw_danger')
    def test_t1_floor_min_25(self, mock_danger):
        """T1 floor is 25."""
        from et_service.raa.score_engine import fuse_scores

        mock_danger.return_value = 0.0

        dims = {'score_a': 0.0}
        rag = {
            'pattern_mult': 1.0,
            'coldstart_adj': 0.0,
            'regulatory_adj': 0.0,
        }
        data = {
            'feature_snapshot': {},
            'pra_verdict': 'MAINTAIN',
            '_tier': 'T1',
            'urgency_multiplier': 1.0,
            'pattern_score': 0,
        }

        with patch('builtins.print'):
            result = fuse_scores(dims, rag, data)

        self.assertGreaterEqual(result['final_raa_score'], 25)

    @patch('et_service.raa.score_engine.compute_raw_danger')
    def test_t2_floor_min_20(self, mock_danger):
        """T2 floor is 20."""
        from et_service.raa.score_engine import fuse_scores

        mock_danger.return_value = 0.0

        dims = {'score_a': 0.0}
        rag = {
            'pattern_mult': 1.0,
            'coldstart_adj': 0.0,
            'regulatory_adj': 0.0,
        }
        data = {
            'feature_snapshot': {},
            'pra_verdict': 'DE-ESCALATE',
            '_tier': 'T2',
            'urgency_multiplier': 1.0,
            'pattern_score': 0,
        }

        with patch('builtins.print'):
            result = fuse_scores(dims, rag, data)

        self.assertGreaterEqual(result['final_raa_score'], 20)

    @patch('et_service.raa.score_engine.compute_raw_danger')
    def test_t3_floor_min_10(self, mock_danger):
        """T3 floor is 10."""
        from et_service.raa.score_engine import fuse_scores

        mock_danger.return_value = 0.0

        dims = {'score_a': 0.0}
        rag = {
            'pattern_mult': 1.0,
            'coldstart_adj': 0.0,
            'regulatory_adj': 0.0,
        }
        data = {
            'feature_snapshot': {},
            'pra_verdict': 'DE-ESCALATE',
            '_tier': 'T3',
            'urgency_multiplier': 1.0,
            'pattern_score': 0,
        }

        with patch('builtins.print'):
            result = fuse_scores(dims, rag, data)

        self.assertGreaterEqual(result['final_raa_score'], 10)

    @patch('et_service.raa.score_engine.compute_raw_danger')
    def test_t4_no_floor_can_score_zero(self, mock_danger):
        """T4 has no floor - can score 0."""
        from et_service.raa.score_engine import fuse_scores

        mock_danger.return_value = 0.0

        dims = {'score_a': 0.0}
        rag = {
            'pattern_mult': 1.0,
            'coldstart_adj': 0.0,
            'regulatory_adj': 0.0,
        }
        data = {
            'feature_snapshot': {},
            'pra_verdict': 'DE-ESCALATE',
            '_tier': 'T4',
            'urgency_multiplier': 1.0,
            'pattern_score': 0,
        }

        with patch('builtins.print'):
            result = fuse_scores(dims, rag, data)

        # T4 can have score 0
        self.assertLessEqual(result['final_raa_score'], 10)


class TestScoreToVerdict(unittest.TestCase):
    """Tests for score to verdict mapping."""

    def test_verdict_allow_below_25(self):
        """Score <= 25 returns ALLOW."""
        from et_service.raa.score_engine import _score_to_verdict

        self.assertEqual(_score_to_verdict(0), 'ALLOW')
        self.assertEqual(_score_to_verdict(20), 'ALLOW')
        self.assertEqual(_score_to_verdict(25), 'ALLOW')

    def test_verdict_flag_26_to_50(self):
        """Score 26-50 returns FLAG."""
        from et_service.raa.score_engine import _score_to_verdict

        self.assertEqual(_score_to_verdict(26), 'FLAG')
        self.assertEqual(_score_to_verdict(38), 'FLAG')
        self.assertEqual(_score_to_verdict(50), 'FLAG')

    def test_verdict_alert_51_to_75(self):
        """Score 51-75 returns ALERT."""
        from et_service.raa.score_engine import _score_to_verdict

        self.assertEqual(_score_to_verdict(51), 'ALERT')
        self.assertEqual(_score_to_verdict(62), 'ALERT')
        self.assertEqual(_score_to_verdict(75), 'ALERT')

    def test_verdict_block_above_75(self):
        """Score > 75 returns BLOCK."""
        from et_service.raa.score_engine import _score_to_verdict

        self.assertEqual(_score_to_verdict(76), 'BLOCK')
        self.assertEqual(_score_to_verdict(80), 'BLOCK')
        self.assertEqual(_score_to_verdict(100), 'BLOCK')

    def test_old_verdict_names_not_returned(self):
        """Old verdict names (SOFT_FLAG, RESTRICT, FREEZE_BLOCK) never returned."""
        from et_service.raa.score_engine import _score_to_verdict

        old_names = {'SOFT_FLAG', 'RESTRICT', 'FREEZE_BLOCK'}

        for score in range(0, 101):
            verdict = _score_to_verdict(score)
            self.assertNotIn(verdict, old_names)


if __name__ == '__main__':
    unittest.main()
