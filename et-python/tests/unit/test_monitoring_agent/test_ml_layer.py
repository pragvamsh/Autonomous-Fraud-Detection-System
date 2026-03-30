"""
test_ml_layer.py
─────────────────
Unit tests for TMA ml_layer module.

Tests:
  - Isolation Forest model loading and prediction
  - Anomaly detection (is_anomaly flag)
  - Score normalization
  - Fallback when model unavailable
  - Error handling for model mismatch
"""

import unittest
from unittest.mock import patch, MagicMock
import numpy as np


class TestMLLayer(unittest.TestCase):
    """Tests for ml_layer.get_ml_risk_score function."""

    def setUp(self):
        """Set up common fixtures."""
        # Standard 15-feature anomaly dict
        self.standard_features = {
            'amount_z_score': 1.5,
            'amount_vs_max': 0.8,
            'exceeds_daily_volume': 0,
            'is_large_amount': 0,
            'is_near_threshold': 0,
            'is_round_number': 0,
            'is_unusual_hour': 0,
            'hour_sin': 0.5,
            'hour_cos': 0.866,
            'is_new_recipient': 0,
            'transactions_last_1h': 1,
            'transactions_last_24h': 3,
            'is_velocity_burst': 0,
            'high_z_new_recipient': 0,
            'late_night_new_recipient': 0,
        }

    @patch('et_service.monitoring_agent.ml_layer._load_payload')
    def test_ml_score_loaded_model_is_anomaly(self, mock_load):
        """Model predicts anomaly (-1) returns is_anomaly=True, ml_score >= 60."""
        from et_service.monitoring_agent.ml_layer import get_ml_risk_score

        # Mock model pipeline
        mock_model = MagicMock()
        mock_model.predict.return_value = np.array([-1])  # -1 = anomaly
        mock_model.decision_function.return_value = np.array([-0.3])  # Low score = anomaly

        # Mock calibration dict
        mock_calibration = {
            'score_min': -0.5,
            'score_max': 0.5,
        }

        mock_load.return_value = {
            'model': mock_model,
            'calibration': mock_calibration,
        }

        result = get_ml_risk_score(self.standard_features)

        self.assertTrue(result['is_anomaly'])
        self.assertGreaterEqual(result['ml_score'], 60)
        self.assertTrue(result['model_loaded'])

    @patch('et_service.monitoring_agent.ml_layer._load_payload')
    def test_ml_score_loaded_model_normal(self, mock_load):
        """Model predicts normal (1) returns is_anomaly=False, ml_score <= 40."""
        from et_service.monitoring_agent.ml_layer import get_ml_risk_score

        mock_model = MagicMock()
        mock_model.predict.return_value = np.array([1])  # 1 = normal
        mock_model.decision_function.return_value = np.array([0.3])  # High score = normal

        mock_calibration = {
            'score_min': -0.5,
            'score_max': 0.5,
        }

        mock_load.return_value = {
            'model': mock_model,
            'calibration': mock_calibration,
        }

        result = get_ml_risk_score(self.standard_features)

        self.assertFalse(result['is_anomaly'])
        self.assertLessEqual(result['ml_score'], 40)
        self.assertTrue(result['model_loaded'])

    @patch('et_service.monitoring_agent.ml_layer._load_payload')
    def test_ml_score_model_not_loaded_falls_back(self, mock_load):
        """Model not found returns fallback score with model_loaded=False."""
        from et_service.monitoring_agent.ml_layer import get_ml_risk_score

        # Mock FileNotFoundError
        mock_load.side_effect = FileNotFoundError("Model not found")

        result = get_ml_risk_score(self.standard_features)

        self.assertEqual(result['model_loaded'], False)
        # Fallback should still return a score
        self.assertIn('ml_score', result)
        self.assertIsInstance(result['ml_score'], int)

    @patch('et_service.monitoring_agent.ml_layer._load_payload')
    def test_ml_score_sklearn_version_mismatch_falls_back(self, mock_load):
        """sklearn version mismatch returns fallback score."""
        from et_service.monitoring_agent.ml_layer import get_ml_risk_score

        mock_model = MagicMock()
        mock_model.predict.side_effect = AttributeError("_sklearn_version")

        mock_load.return_value = {
            'model': mock_model,
            'calibration': {'score_min': -0.5, 'score_max': 0.5},
        }

        result = get_ml_risk_score(self.standard_features)

        # Should fall back gracefully
        self.assertEqual(result['model_loaded'], False)
        self.assertIn('ml_score', result)


class TestEncodeFeatures(unittest.TestCase):
    """Tests for encode_features function."""

    def test_encode_features_returns_correct_shape(self):
        """encode_features returns (1, 15) numpy array."""
        from et_service.monitoring_agent.ml_layer import encode_features

        features = {
            'amount_z_score': 1.0,
            'amount_vs_max': 0.5,
            'exceeds_daily_volume': 0,
            'is_large_amount': 0,
            'is_near_threshold': 0,
            'is_round_number': 0,
            'is_unusual_hour': 0,
            'hour_sin': 0.0,
            'hour_cos': 1.0,
            'is_new_recipient': 0,
            'transactions_last_1h': 1,
            'transactions_last_24h': 1,
            'is_velocity_burst': 0,
            'high_z_new_recipient': 0,
            'late_night_new_recipient': 0,
        }

        result = encode_features(features)

        self.assertEqual(result.shape, (1, 15))

    def test_encode_features_handles_missing_features(self):
        """Missing features default to 0."""
        from et_service.monitoring_agent.ml_layer import encode_features

        # Only partial features
        features = {
            'amount_z_score': 2.0,
            'is_new_recipient': 1,
        }

        result = encode_features(features)

        # Should still return (1, 15) with zeros for missing
        self.assertEqual(result.shape, (1, 15))


class TestFallbackScore(unittest.TestCase):
    """Tests for _fallback_score function."""

    def test_fallback_score_base_is_flag_floor(self):
        """Fallback base score starts at FLAG floor (31)."""
        from et_service.monitoring_agent.ml_layer import _fallback_score
        from et_service.monitoring_agent.constants import LOW_CONFIDENCE_FLAG_FLOOR

        # Zero features - should return base score
        features = {
            'amount_z_score': 0,
            'is_new_recipient': 0,
            'is_unusual_hour': 0,
            'is_velocity_burst': 0,
            'exceeds_daily_volume': 0,
            'is_near_threshold': 0,
            'high_z_new_recipient': 0,
        }

        result = _fallback_score(features)

        # Base is FLAG floor (31)
        self.assertGreaterEqual(result['ml_score'], LOW_CONFIDENCE_FLAG_FLOOR)

    def test_fallback_score_high_z_adds_30(self):
        """Z-score > 3 adds 30 to fallback score."""
        from et_service.monitoring_agent.ml_layer import _fallback_score
        from et_service.monitoring_agent.constants import LOW_CONFIDENCE_FLAG_FLOOR

        features = {
            'amount_z_score': 3.5,  # > 3
            'is_new_recipient': 0,
            'is_unusual_hour': 0,
            'is_velocity_burst': 0,
            'exceeds_daily_volume': 0,
            'is_near_threshold': 0,
            'high_z_new_recipient': 0,
        }

        result = _fallback_score(features)

        # Base (31) + 30 for high z = at least 61
        self.assertGreaterEqual(result['ml_score'], LOW_CONFIDENCE_FLAG_FLOOR + 30)

    def test_fallback_score_capped_at_100(self):
        """Fallback score never exceeds 100."""
        from et_service.monitoring_agent.ml_layer import _fallback_score

        # All risk flags triggered
        features = {
            'amount_z_score': 5.0,  # > 3 = +30
            'is_new_recipient': 1,  # +15
            'is_unusual_hour': 1,   # +10
            'is_velocity_burst': 1,  # +15
            'exceeds_daily_volume': 1,  # +10
            'is_near_threshold': 1,  # +10
            'high_z_new_recipient': 1,  # +10
        }

        result = _fallback_score(features)

        # Should be capped at 100
        self.assertLessEqual(result['ml_score'], 100)


class TestRawToScore(unittest.TestCase):
    """Tests for _raw_to_score calibration function."""

    def test_raw_to_score_maps_normal_to_low_risk(self):
        """High raw score (normal) maps to low risk score."""
        from et_service.monitoring_agent.ml_layer import _raw_to_score

        calibration = {'score_min': -0.5, 'score_max': 0.5}

        # Raw = 0.5 (max, most normal) should map to 0 risk
        score = _raw_to_score(0.5, calibration)
        self.assertLessEqual(score, 10)

    def test_raw_to_score_maps_anomaly_to_high_risk(self):
        """Low raw score (anomaly) maps to high risk score."""
        from et_service.monitoring_agent.ml_layer import _raw_to_score

        calibration = {'score_min': -0.5, 'score_max': 0.5}

        # Raw = -0.5 (min, most anomalous) should map to ~100 risk
        score = _raw_to_score(-0.5, calibration)
        self.assertGreaterEqual(score, 90)

    def test_raw_to_score_handles_degenerate_range(self):
        """Zero range returns neutral 50."""
        from et_service.monitoring_agent.ml_layer import _raw_to_score

        calibration = {'score_min': 0.0, 'score_max': 0.0}  # Degenerate

        score = _raw_to_score(0.0, calibration)
        self.assertEqual(score, 50)


if __name__ == '__main__':
    unittest.main()
