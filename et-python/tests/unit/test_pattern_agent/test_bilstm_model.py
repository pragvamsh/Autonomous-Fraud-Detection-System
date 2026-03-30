"""
test_bilstm_model.py
─────────────────────
Unit tests for PRA bilstm_model module.

Tests:
  - Inference returns score and hidden state
  - Model not found runs with random weights
  - Hidden state shape is 128
  - Input tensor shape is correct
"""

import unittest
from unittest.mock import patch, MagicMock
import numpy as np
import torch


class TestRunInference(unittest.TestCase):
    """Tests for bilstm_model.run_inference function."""

    def setUp(self):
        """Set up common fixtures."""
        from et_service.pattern_agent.constants import SEQUENCE_LENGTH, FEATURE_DIM
        self.input_matrix = np.random.rand(SEQUENCE_LENGTH, FEATURE_DIM).astype(np.float32)

    @patch('et_service.pattern_agent.bilstm_model._load_model')
    def test_run_inference_returns_score_and_hidden_state(self, mock_load):
        """Inference returns bilstm_score in [0, 100] and hidden_state."""
        from et_service.pattern_agent.bilstm_model import run_inference

        # Mock model that returns valid score and hidden state
        mock_model = MagicMock()
        mock_model.return_value = (
            torch.tensor([[65.0]]),  # score
            torch.zeros(1, 128),     # hidden state
        )

        mock_load.return_value = (mock_model, torch.device('cpu'))

        result = run_inference(self.input_matrix)

        self.assertIn('bilstm_score', result)
        self.assertIn('hidden_state', result)
        self.assertGreaterEqual(result['bilstm_score'], 0)
        self.assertLessEqual(result['bilstm_score'], 100)

    @patch('torch.load')
    @patch('et_service.pattern_agent.bilstm_model._model', new=None)
    def test_run_inference_model_not_found_runs_random_weights(self, mock_torch_load):
        """FileNotFoundError runs with random weights, still returns score."""
        from et_service.pattern_agent.bilstm_model import run_inference, FraudBiLSTM

        # Force model reload
        import et_service.pattern_agent.bilstm_model as bm
        bm._model = None
        bm._device = None

        mock_torch_load.side_effect = FileNotFoundError("Model not found")

        # Should not crash, should return valid result
        with patch('builtins.print'):  # Suppress warning
            result = run_inference(self.input_matrix)

        self.assertIn('bilstm_score', result)
        self.assertIn('hidden_state', result)

    @patch('et_service.pattern_agent.bilstm_model._load_model')
    def test_run_inference_hidden_state_shape_is_128(self, mock_load):
        """Hidden state has shape (128,)."""
        from et_service.pattern_agent.bilstm_model import run_inference

        mock_model = MagicMock()
        mock_model.return_value = (
            torch.tensor([[50.0]]),
            torch.randn(1, 128),  # Shape (1, 128) -> squeezed to (128,)
        )

        mock_load.return_value = (mock_model, torch.device('cpu'))

        result = run_inference(self.input_matrix)

        self.assertEqual(result['hidden_state'].shape, (128,))

    @patch('et_service.pattern_agent.bilstm_model._load_model')
    def test_run_inference_input_shape_correct(self, mock_load):
        """Model is called with tensor shape (1, 30, 17)."""
        from et_service.pattern_agent.bilstm_model import run_inference
        from et_service.pattern_agent.constants import SEQUENCE_LENGTH, FEATURE_DIM

        mock_model = MagicMock()
        mock_model.return_value = (
            torch.tensor([[50.0]]),
            torch.zeros(1, 128),
        )

        mock_load.return_value = (mock_model, torch.device('cpu'))

        run_inference(self.input_matrix)

        # Check model was called with correct shape
        call_args = mock_model.call_args[0][0]
        self.assertEqual(call_args.shape, (1, SEQUENCE_LENGTH, FEATURE_DIM))


class TestFraudBiLSTM(unittest.TestCase):
    """Tests for FraudBiLSTM model architecture."""

    def test_model_forward_returns_score_and_hidden(self):
        """Forward pass returns score and hidden state."""
        from et_service.pattern_agent.bilstm_model import FraudBiLSTM
        from et_service.pattern_agent.constants import SEQUENCE_LENGTH, FEATURE_DIM

        model = FraudBiLSTM()
        model.eval()

        # Input: (batch, seq_len, features)
        x = torch.randn(1, SEQUENCE_LENGTH, FEATURE_DIM)

        with torch.no_grad():
            score, hidden = model(x)

        # Score shape (batch, 1)
        self.assertEqual(score.shape, (1, 1))

        # Hidden shape (batch, 128)
        self.assertEqual(hidden.shape, (1, 128))

        # Score is in [0, 100]
        self.assertGreaterEqual(score.item(), 0)
        self.assertLessEqual(score.item(), 100)

    def test_model_batch_inference(self):
        """Model handles batch size > 1."""
        from et_service.pattern_agent.bilstm_model import FraudBiLSTM
        from et_service.pattern_agent.constants import SEQUENCE_LENGTH, FEATURE_DIM

        model = FraudBiLSTM()
        model.eval()

        batch_size = 4
        x = torch.randn(batch_size, SEQUENCE_LENGTH, FEATURE_DIM)

        with torch.no_grad():
            score, hidden = model(x)

        self.assertEqual(score.shape, (batch_size, 1))
        self.assertEqual(hidden.shape, (batch_size, 128))


class TestModelLoading(unittest.TestCase):
    """Tests for model singleton loading."""

    @patch('os.path.exists')
    @patch('torch.load')
    def test_load_model_success(self, mock_torch_load, mock_exists):
        """Model loads successfully from file."""
        from et_service.pattern_agent.bilstm_model import FraudBiLSTM

        mock_exists.return_value = True

        # Create a valid state dict
        model = FraudBiLSTM()
        mock_torch_load.return_value = model.state_dict()

        # Force reload
        import et_service.pattern_agent.bilstm_model as bm
        bm._model = None
        bm._device = None

        with patch('builtins.print'):
            loaded_model, device = bm._load_model()

        self.assertIsNotNone(loaded_model)


if __name__ == '__main__':
    unittest.main()
