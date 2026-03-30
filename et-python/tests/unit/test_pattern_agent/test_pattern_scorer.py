"""
test_pattern_scorer.py
───────────────────────
Unit tests for PRA pattern_scorer module.

Tests:
  - Score to verdict mapping (DE-ESCALATE/MAINTAIN/ESCALATE/CRITICAL)
  - Urgency multiplier amplification
  - Score clamping at 100
"""

import unittest
from unittest.mock import patch


class TestComputePatternScore(unittest.TestCase):
    """Tests for compute_pattern_score function."""

    def test_score_0_35_returns_de_escalate(self):
        """Score <= 35 returns DE-ESCALATE verdict."""
        from et_service.pattern_agent.pattern_scorer import compute_pattern_score

        result = compute_pattern_score(
            bilstm_score=30.0,
            precedent_adj=5.0,
            reg_adj=2.0,
            urgency_multiplier=1.0,
        )

        self.assertEqual(result['pra_verdict'], 'DE-ESCALATE')
        self.assertLessEqual(result['final_pattern_score'], 35)

    def test_score_36_60_returns_maintain(self):
        """Score 36-60 returns MAINTAIN verdict."""
        from et_service.pattern_agent.pattern_scorer import compute_pattern_score

        # Formula: combined_raw = 0.55 * bilstm + 0.45 * (precedent_adj + reg_adj)
        # For score ~50: 0.55*70 + 0.45*26 = 38.5 + 11.7 = 50.2
        result = compute_pattern_score(
            bilstm_score=70.0,
            precedent_adj=20.0,
            reg_adj=6.0,
            urgency_multiplier=1.0,
        )

        self.assertEqual(result['pra_verdict'], 'MAINTAIN')
        self.assertGreaterEqual(result['final_pattern_score'], 36)
        self.assertLessEqual(result['final_pattern_score'], 60)

    def test_score_61_80_returns_escalate(self):
        """Score 61-80 returns ESCALATE verdict."""
        from et_service.pattern_agent.pattern_scorer import compute_pattern_score

        # Formula: combined_raw = 0.55 * bilstm + 0.45 * (precedent_adj + reg_adj)
        # For score ~70: 0.55*90 + 0.45*46 = 49.5 + 20.7 = 70.2
        result = compute_pattern_score(
            bilstm_score=90.0,
            precedent_adj=35.0,
            reg_adj=11.0,
            urgency_multiplier=1.0,
        )

        self.assertEqual(result['pra_verdict'], 'ESCALATE')
        self.assertGreaterEqual(result['final_pattern_score'], 61)
        self.assertLessEqual(result['final_pattern_score'], 80)

    def test_score_81_100_returns_critical(self):
        """Score 81-100 returns CRITICAL verdict."""
        from et_service.pattern_agent.pattern_scorer import compute_pattern_score

        result = compute_pattern_score(
            bilstm_score=90.0,
            precedent_adj=30.0,
            reg_adj=15.0,
            urgency_multiplier=1.2,
        )

        self.assertEqual(result['pra_verdict'], 'CRITICAL')
        self.assertGreaterEqual(result['final_pattern_score'], 81)

    def test_urgency_multiplier_amplifies_score(self):
        """Higher urgency_multiplier produces higher final score."""
        from et_service.pattern_agent.pattern_scorer import compute_pattern_score

        base_args = {
            'bilstm_score': 50.0,
            'precedent_adj': 15.0,
            'reg_adj': 5.0,
        }

        result_low = compute_pattern_score(**base_args, urgency_multiplier=1.0)
        result_high = compute_pattern_score(**base_args, urgency_multiplier=1.8)

        self.assertGreater(
            result_high['final_pattern_score'],
            result_low['final_pattern_score']
        )

    def test_urgency_multiplier_clamped_at_100(self):
        """Very high inputs are clamped at 100."""
        from et_service.pattern_agent.pattern_scorer import compute_pattern_score

        result = compute_pattern_score(
            bilstm_score=100.0,
            precedent_adj=50.0,
            reg_adj=30.0,
            urgency_multiplier=2.0,  # Would produce > 200 without clamping
        )

        self.assertLessEqual(result['final_pattern_score'], 100)


class TestScoreToVerdict(unittest.TestCase):
    """Tests for _score_to_verdict function."""

    def test_boundary_cases(self):
        """Test exact boundary values."""
        from et_service.pattern_agent.pattern_scorer import _score_to_verdict

        self.assertEqual(_score_to_verdict(0), 'DE-ESCALATE')
        self.assertEqual(_score_to_verdict(35), 'DE-ESCALATE')
        self.assertEqual(_score_to_verdict(36), 'MAINTAIN')
        self.assertEqual(_score_to_verdict(60), 'MAINTAIN')
        self.assertEqual(_score_to_verdict(61), 'ESCALATE')
        self.assertEqual(_score_to_verdict(80), 'ESCALATE')
        self.assertEqual(_score_to_verdict(81), 'CRITICAL')
        self.assertEqual(_score_to_verdict(100), 'CRITICAL')

    def test_safety_net_above_100(self):
        """Score > 100 returns CRITICAL (safety net)."""
        from et_service.pattern_agent.pattern_scorer import _score_to_verdict

        self.assertEqual(_score_to_verdict(150), 'CRITICAL')


class TestBuildAgentReasoning(unittest.TestCase):
    """Tests for build_agent_reasoning function."""

    def test_reasoning_includes_all_components(self):
        """Reasoning string includes all score components."""
        from et_service.pattern_agent.pattern_scorer import build_agent_reasoning

        reasoning = build_agent_reasoning(
            bilstm_score=65.0,
            precedent_adj=20.0,
            reg_adj=10.0,
            urgency_multiplier=1.5,
            typology_code='TY-03',
            l3_similarity=0.75,
            n_cases=5,
            final_pattern_score=75,
            pra_verdict='ESCALATE',
            reg_citations=[{'pmla_section': 'PMLA-S12'}],
        )

        # Should contain key info
        self.assertIn('75', reasoning)  # final score
        self.assertIn('ESCALATE', reasoning)
        self.assertIn('65', str(reasoning))  # bilstm
        self.assertIn('TY-03', reasoning)
        self.assertIn('1.5', str(reasoning))  # urgency

    def test_reasoning_no_typology(self):
        """Reasoning handles missing typology gracefully."""
        from et_service.pattern_agent.pattern_scorer import build_agent_reasoning

        reasoning = build_agent_reasoning(
            bilstm_score=40.0,
            precedent_adj=10.0,
            reg_adj=5.0,
            urgency_multiplier=1.0,
            typology_code=None,
            l3_similarity=0.0,
            n_cases=0,
            final_pattern_score=35,
            pra_verdict='DE-ESCALATE',
            reg_citations=[],
        )

        self.assertIn('No typology match', reasoning)


class TestScoreFusion(unittest.TestCase):
    """Tests for score fusion formula."""

    def test_weighted_sum_formula(self):
        """Verify weighted sum formula is applied correctly."""
        from et_service.pattern_agent.pattern_scorer import compute_pattern_score
        from et_service.pattern_agent.constants import BILSTM_WEIGHT, RAG_PATTERN_WEIGHT

        bilstm_score = 60.0
        precedent_adj = 20.0
        reg_adj = 10.0
        urgency = 1.0

        result = compute_pattern_score(
            bilstm_score=bilstm_score,
            precedent_adj=precedent_adj,
            reg_adj=reg_adj,
            urgency_multiplier=urgency,
        )

        # rag_pattern_score = precedent_adj + reg_adj = 30
        # combined_raw = BILSTM_WEIGHT * 60 + RAG_PATTERN_WEIGHT * 30
        #              = 0.55 * 60 + 0.45 * 30 = 33 + 13.5 = 46.5
        expected_rag = precedent_adj + reg_adj
        expected_combined = BILSTM_WEIGHT * bilstm_score + RAG_PATTERN_WEIGHT * expected_rag

        self.assertAlmostEqual(result['combined_raw'], expected_combined, places=1)


if __name__ == '__main__':
    unittest.main()
