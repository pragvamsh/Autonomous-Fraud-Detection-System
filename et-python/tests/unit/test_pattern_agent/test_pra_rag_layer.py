"""
test_pra_rag_layer.py
──────────────────────
Unit tests for PRA pra_rag_layer module.

Tests:
  - L3 typology retrieval and urgency multiplier
  - L2 fraud case precedent adjustment
  - L1 regulatory adjustment
  - Hidden state projection to L3 dimension
  - Empty collection handling
"""

import unittest
from unittest.mock import patch, MagicMock
import numpy as np


class TestStepL3(unittest.TestCase):
    """Tests for L3 pattern library retrieval."""

    @patch('et_service.pattern_agent.pra_rag_layer._search_vector')
    @patch('et_service.pattern_agent.pra_rag_layer._project_hidden_to_l3')
    def test_step_l3_above_threshold_sets_urgency_multiplier(
        self, mock_project, mock_search
    ):
        """L3 similarity >= 0.60 sets urgency_multiplier > 1.0."""
        from et_service.pattern_agent.pra_rag_layer import _step_l3

        hidden_state = np.random.rand(128).astype(np.float32)

        mock_project.return_value = np.random.rand(384).astype(np.float32)
        mock_search.return_value = (
            [{'fiu_ind_code': 'TY-03', 'urgency_multiplier': 1.8}],
            np.array([0.75], dtype=np.float32),  # similarity = 1 - 0.25 = 0.75
        )

        result = _step_l3(hidden_state)

        self.assertGreater(result['urgency_multiplier'], 1.0)
        self.assertEqual(result['urgency_multiplier'], 1.8)
        self.assertEqual(result['typology_code'], 'TY-03')

    @patch('et_service.pattern_agent.pra_rag_layer._search_vector')
    @patch('et_service.pattern_agent.pra_rag_layer._project_hidden_to_l3')
    def test_step_l3_below_threshold_urgency_stays_1(
        self, mock_project, mock_search
    ):
        """L3 similarity < 0.60 keeps urgency_multiplier at 1.0."""
        from et_service.pattern_agent.pra_rag_layer import _step_l3

        hidden_state = np.random.rand(128).astype(np.float32)

        mock_project.return_value = np.random.rand(384).astype(np.float32)
        mock_search.return_value = (
            [{'fiu_ind_code': 'TY-07', 'urgency_multiplier': 2.0}],
            np.array([0.3], dtype=np.float32),  # Below 0.60 threshold
        )

        result = _step_l3(hidden_state)

        # Typology identified but urgency not applied
        self.assertEqual(result['urgency_multiplier'], 1.0)
        self.assertEqual(result['typology_code'], 'TY-07')

    @patch('et_service.pattern_agent.pra_rag_layer._search_vector')
    @patch('et_service.pattern_agent.pra_rag_layer._project_hidden_to_l3')
    def test_step_l3_empty_collection_returns_defaults(
        self, mock_project, mock_search
    ):
        """Empty L3 collection returns default values."""
        from et_service.pattern_agent.pra_rag_layer import _step_l3

        hidden_state = np.random.rand(128).astype(np.float32)

        mock_project.return_value = np.random.rand(384).astype(np.float32)
        mock_search.return_value = ([], np.array([], dtype=np.float32))

        result = _step_l3(hidden_state)

        self.assertIsNone(result['typology_code'])
        self.assertEqual(result['urgency_multiplier'], 1.0)
        self.assertEqual(result['l3_similarity'], 0.0)


class TestStepL2(unittest.TestCase):
    """Tests for L2 fraud case retrieval."""

    @patch('et_service.pattern_agent.pra_rag_layer._search_vector')
    def test_step_l2_computes_precedent_adj_correctly(self, mock_search):
        """Weighted average of severity scores computed correctly."""
        from et_service.pattern_agent.pra_rag_layer import _step_l2

        hidden_state = np.random.rand(128).astype(np.float32)

        # 5 cases with known severity scores and similarities
        mock_search.return_value = (
            [
                {'confirmed_pattern_severity': 80},
                {'confirmed_pattern_severity': 60},
                {'confirmed_pattern_severity': 70},
                {'confirmed_pattern_severity': 50},
                {'confirmed_pattern_severity': 40},
            ],
            np.array([0.9, 0.8, 0.7, 0.6, 0.5], dtype=np.float32),
        )

        result = _step_l2(hidden_state)

        # Manual calculation:
        # weighted_sum = 80*0.9 + 60*0.8 + 70*0.7 + 50*0.6 + 40*0.5
        #              = 72 + 48 + 49 + 30 + 20 = 219
        # total_weight = 0.9 + 0.8 + 0.7 + 0.6 + 0.5 = 3.5
        # precedent_adj = 219 / 3.5 = 62.57
        expected = (80*0.9 + 60*0.8 + 70*0.7 + 50*0.6 + 40*0.5) / 3.5

        self.assertAlmostEqual(result['precedent_adj'], round(expected, 2), places=1)
        self.assertEqual(result['n_cases'], 5)

    @patch('et_service.pattern_agent.pra_rag_layer._search_vector')
    def test_step_l2_empty_returns_zero(self, mock_search):
        """Empty L2 returns precedent_adj = 0."""
        from et_service.pattern_agent.pra_rag_layer import _step_l2

        hidden_state = np.random.rand(128).astype(np.float32)
        mock_search.return_value = ([], np.array([], dtype=np.float32))

        result = _step_l2(hidden_state)

        self.assertEqual(result['precedent_adj'], 0.0)
        self.assertEqual(result['n_cases'], 0)


class TestStepL1(unittest.TestCase):
    """Tests for L1 regulatory retrieval."""

    @patch('et_service.pattern_agent.pra_rag_layer._search_text')
    def test_step_l1_no_flags_returns_zero_adj(self, mock_search):
        """Empty flag list returns reg_adj = 0."""
        from et_service.pattern_agent.pra_rag_layer import _step_l1

        result = _step_l1([])

        self.assertEqual(result['reg_adj'], 0.0)
        self.assertEqual(result['citations'], [])

    @patch('et_service.pattern_agent.pra_rag_layer._search_text')
    def test_step_l1_velocity_flag_returns_nonzero_adj(self, mock_search):
        """is_velocity_burst flag triggers regulatory lookup."""
        from et_service.pattern_agent.pra_rag_layer import _step_l1

        mock_search.return_value = (
            [
                {'risk_adjustment_value': 5.0, 'source': 'PMLA-S12', 'text': 'Test rule'},
                {'risk_adjustment_value': 3.0, 'source': 'RBI-2023', 'text': 'Another rule'},
            ],
            np.array([0.85, 0.70], dtype=np.float32),
        )

        result = _step_l1(['is_velocity_burst'])

        # reg_adj = 5.0 + 3.0 = 8.0
        self.assertEqual(result['reg_adj'], 8.0)
        self.assertEqual(len(result['citations']), 2)


class TestProjectHiddenToL3(unittest.TestCase):
    """Tests for hidden state projection to L3 dimension."""

    @patch('torch.load')
    def test_project_hidden_to_l3_zero_pad_fallback(self, mock_torch_load):
        """Missing projection matrix falls back to zero-padding."""
        from et_service.pattern_agent.pra_rag_layer import _project_hidden_to_l3
        from et_service.pattern_agent.constants import RAG_L3_HIDDEN_PROJ_DIM

        # No l3_projection in state dict
        mock_torch_load.return_value = {}

        hidden = np.random.rand(128).astype(np.float32)
        result = _project_hidden_to_l3(hidden)

        # Output should be 384-d
        self.assertEqual(result.shape, (RAG_L3_HIDDEN_PROJ_DIM,))

        # First 128 elements should match input
        self.assertTrue(np.allclose(result[:128], hidden))

        # Remaining elements should be zero
        self.assertTrue(np.allclose(result[128:], 0))

    @patch('torch.load')
    def test_project_hidden_to_l3_wrong_projection_shape_uses_fallback(
        self, mock_torch_load
    ):
        """Wrong projection matrix shape triggers fallback."""
        import torch
        from et_service.pattern_agent.pra_rag_layer import _project_hidden_to_l3
        from et_service.pattern_agent.constants import RAG_L3_HIDDEN_PROJ_DIM

        # Wrong shape projection matrix
        mock_torch_load.return_value = {
            'l3_projection': torch.randn(384, 128)  # Wrong: should be (256, 128)
        }

        hidden = np.random.rand(128).astype(np.float32)

        with patch('builtins.print'):
            result = _project_hidden_to_l3(hidden)

        # Should fallback to zero-padding
        self.assertEqual(result.shape, (RAG_L3_HIDDEN_PROJ_DIM,))
        self.assertTrue(np.allclose(result[:128], hidden))


class TestRetrievePraRag(unittest.TestCase):
    """Tests for main retrieve_pra_rag function."""

    @patch('et_service.pattern_agent.pra_rag_layer._step_l1')
    @patch('et_service.pattern_agent.pra_rag_layer._step_l2')
    @patch('et_service.pattern_agent.pra_rag_layer._step_l3')
    def test_retrieve_pra_rag_combines_all_layers(
        self, mock_l3, mock_l2, mock_l1
    ):
        """retrieve_pra_rag combines L1, L2, L3 results."""
        from et_service.pattern_agent.pra_rag_layer import retrieve_pra_rag

        mock_l3.return_value = {
            'typology_code': 'TY-03',
            'urgency_multiplier': 1.5,
            'regulatory_action': 'HOLD',
            'l3_similarity': 0.75,
        }
        mock_l2.return_value = {
            'precedent_adj': 25.5,
            'n_cases': 3,
        }
        mock_l1.return_value = {
            'reg_adj': 5.0,
            'citations': [{'source': 'PMLA-S12'}],
        }

        hidden = np.random.rand(128).astype(np.float32)
        features = {}
        flags = ['is_velocity_burst']

        result = retrieve_pra_rag(hidden, features, flags)

        self.assertEqual(result['typology_code'], 'TY-03')
        self.assertEqual(result['urgency_multiplier'], 1.5)
        self.assertEqual(result['precedent_adj'], 25.5)
        self.assertEqual(result['reg_adj'], 5.0)
        self.assertIn('rag_reasoning', result)


if __name__ == '__main__':
    unittest.main()
