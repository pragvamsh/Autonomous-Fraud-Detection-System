"""
test_sequence_builder.py
─────────────────────────
Unit tests for PRA sequence_builder module.

Tests:
  - Sequence matrix shape
  - Padding for short history
  - Feature dimension handling
  - Fallback to extractor when snapshot missing
  - Error handling
"""

import unittest
from unittest.mock import patch, MagicMock
import numpy as np


class TestBuildSequence(unittest.TestCase):
    """Tests for sequence_builder.build_sequence function."""

    def setUp(self):
        """Set up common fixtures."""
        self.customer_id = 'C12345'
        self.alert_id = 1001

    @patch('et_service.pattern_agent.sequence_builder._get_behaviour_profile')
    @patch('et_service.pattern_agent.sequence_builder._safe_get_alert_row')
    @patch('et_service.pattern_agent.sequence_builder.get_last_n_debits')
    def test_build_sequence_returns_correct_shape(
        self, mock_debits, mock_alert_row, mock_profile
    ):
        """Sequence matrix has shape (30, 17)."""
        from et_service.pattern_agent.sequence_builder import build_sequence
        from et_service.pattern_agent.constants import SEQUENCE_LENGTH, FEATURE_DIM

        # Mock 30 transactions with feature snapshots
        mock_debits.return_value = [
            {
                'transaction_id': f'TXN{i:04d}',
                'customer_id': self.customer_id,
                'amount': 1000 + i * 100,
            }
            for i in range(30)
        ]

        # Mock alert rows with proper feature snapshots as lists (17 features)
        def get_alert_row(txn_id):
            return {
                'feature_snapshot': [0.1 * i for i in range(FEATURE_DIM)]
            }

        mock_alert_row.side_effect = get_alert_row
        mock_profile.return_value = None

        matrix, seq_length = build_sequence(self.customer_id, self.alert_id)

        self.assertEqual(matrix.shape, (SEQUENCE_LENGTH, FEATURE_DIM))
        self.assertEqual(seq_length, 30)

    @patch('et_service.pattern_agent.sequence_builder._get_behaviour_profile')
    @patch('et_service.pattern_agent.sequence_builder._safe_get_alert_row')
    @patch('et_service.pattern_agent.sequence_builder.get_last_n_debits')
    def test_build_sequence_pads_short_history(
        self, mock_debits, mock_alert_row, mock_profile
    ):
        """Short history (5 txns) is left-padded with zeros."""
        from et_service.pattern_agent.sequence_builder import build_sequence
        from et_service.pattern_agent.constants import SEQUENCE_LENGTH, FEATURE_DIM

        # Only 5 transactions
        mock_debits.return_value = [
            {'transaction_id': f'TXN{i:04d}', 'customer_id': self.customer_id, 'amount': 1000}
            for i in range(5)
        ]

        # Feature snapshots for 5 transactions as lists
        def get_alert_row(txn_id):
            return {'feature_snapshot': [0.5] * FEATURE_DIM}

        mock_alert_row.side_effect = get_alert_row
        mock_profile.return_value = None

        matrix, seq_length = build_sequence(self.customer_id, self.alert_id)

        # First 25 rows should be zeros (padding)
        self.assertTrue(np.allclose(matrix[:25], 0))

        # Last 5 rows should be populated
        self.assertFalse(np.allclose(matrix[25:], 0))

        self.assertEqual(seq_length, 5)

    @patch('et_service.pattern_agent.sequence_builder._safe_get_alert_row')
    @patch('et_service.pattern_agent.sequence_builder.get_last_n_debits')
    def test_build_sequence_feature_dim_17_accepted(
        self, mock_debits, mock_alert_row
    ):
        """17-feature snapshot is accepted and used directly."""
        from et_service.pattern_agent.sequence_builder import build_sequence
        from et_service.pattern_agent.constants import FEATURE_DIM

        mock_debits.return_value = [
            {'transaction_id': 'TXN0001', 'customer_id': self.customer_id, 'amount': 1000}
        ]

        # Exactly FEATURE_DIM (17) features
        mock_alert_row.return_value = {
            'feature_snapshot': [0.1] * FEATURE_DIM
        }

        matrix, seq_length = build_sequence(self.customer_id, self.alert_id)

        # Row should be populated (not zeros)
        self.assertFalse(np.allclose(matrix[-1], 0))
        self.assertEqual(seq_length, 1)

    @patch('et_service.pattern_agent.sequence_builder._safe_get_alert_row')
    @patch('et_service.pattern_agent.sequence_builder.get_last_n_debits')
    def test_build_sequence_feature_dim_15_truncated_not_discarded(
        self, mock_debits, mock_alert_row
    ):
        """15-feature snapshot is zero-padded to 17, not discarded."""
        from et_service.pattern_agent.sequence_builder import build_sequence
        from et_service.pattern_agent.constants import FEATURE_DIM

        mock_debits.return_value = [
            {'transaction_id': 'TXN0001', 'customer_id': self.customer_id, 'amount': 1000}
        ]

        # Only 15 features (less than FEATURE_DIM=17)
        mock_alert_row.return_value = {
            'feature_snapshot': [0.5] * 15
        }

        matrix, seq_length = build_sequence(self.customer_id, self.alert_id)

        # First 15 elements should be 0.5
        self.assertTrue(np.allclose(matrix[-1, :15], 0.5))

        # Row should not be all zeros (not discarded)
        self.assertFalse(np.allclose(matrix[-1], 0))
        self.assertEqual(seq_length, 1)

    @patch('et_service.pattern_agent.sequence_builder._safe_extract_features')
    @patch('et_service.pattern_agent.sequence_builder._safe_get_alert_row')
    @patch('et_service.pattern_agent.sequence_builder.get_last_n_debits')
    def test_build_sequence_none_snapshot_falls_back_to_extractor(
        self, mock_debits, mock_alert_row, mock_extract
    ):
        """Missing feature_snapshot falls back to anomaly extractor."""
        from et_service.pattern_agent.sequence_builder import build_sequence
        from et_service.pattern_agent.constants import FEATURE_DIM

        mock_debits.return_value = [
            {'transaction_id': 'TXN0001', 'customer_id': self.customer_id, 'amount': 1000}
        ]

        # No feature snapshot
        mock_alert_row.return_value = {'feature_snapshot': None}

        # Extractor returns valid features
        mock_extract.return_value = np.array([0.3] * FEATURE_DIM, dtype=np.float32)

        matrix, seq_length = build_sequence(self.customer_id, self.alert_id)

        # Extractor should have been called
        mock_extract.assert_called_once()
        self.assertEqual(seq_length, 1)

    @patch('et_service.pattern_agent.sequence_builder._safe_extract_features')
    @patch('et_service.pattern_agent.sequence_builder._safe_get_alert_row')
    @patch('et_service.pattern_agent.sequence_builder.get_last_n_debits')
    def test_build_sequence_extractor_error_leaves_row_zeros(
        self, mock_debits, mock_alert_row, mock_extract
    ):
        """Extractor error leaves row as zeros (no crash)."""
        from et_service.pattern_agent.sequence_builder import build_sequence

        mock_debits.return_value = [
            {'transaction_id': 'TXN0001', 'customer_id': self.customer_id, 'amount': 1000}
        ]

        mock_alert_row.return_value = {'feature_snapshot': None}
        mock_extract.return_value = None  # Extraction failed

        matrix, seq_length = build_sequence(self.customer_id, self.alert_id)

        # Row should be zeros (extraction failed)
        self.assertTrue(np.allclose(matrix[-1], 0))

        # No crash
        self.assertIsNotNone(matrix)

    @patch('et_service.pattern_agent.sequence_builder._get_behaviour_profile')
    @patch('et_service.pattern_agent.sequence_builder._safe_get_alert_row')
    @patch('et_service.pattern_agent.sequence_builder.get_last_n_debits')
    def test_build_sequence_returns_sequence_length_equal_to_filled_count(
        self, mock_debits, mock_alert_row, mock_profile
    ):
        """sequence_length matches actual number of filled rows."""
        from et_service.pattern_agent.sequence_builder import build_sequence
        from et_service.pattern_agent.constants import FEATURE_DIM

        # 12 transactions
        mock_debits.return_value = [
            {'transaction_id': f'TXN{i:04d}', 'customer_id': self.customer_id, 'amount': 1000}
            for i in range(12)
        ]

        def get_alert_row(txn_id):
            return {
                'feature_snapshot': [0.5] * FEATURE_DIM
            }

        mock_alert_row.side_effect = get_alert_row
        mock_profile.return_value = None

        matrix, seq_length = build_sequence(self.customer_id, self.alert_id)

        self.assertEqual(seq_length, 12)


class TestParseFeatureSnapshot(unittest.TestCase):
    """Tests for _parse_feature_snapshot helper."""

    def test_parse_list_snapshot(self):
        """List snapshot is converted to numpy array."""
        from et_service.pattern_agent.sequence_builder import _parse_feature_snapshot
        from et_service.pattern_agent.constants import FEATURE_DIM

        snapshot = [0.1] * FEATURE_DIM
        result = _parse_feature_snapshot(snapshot)

        self.assertIsInstance(result, np.ndarray)
        self.assertEqual(result.dtype, np.float32)

    def test_parse_dict_snapshot_with_feature_names(self):
        """Dict with feature names is parsed correctly."""
        from et_service.pattern_agent.sequence_builder import _parse_feature_snapshot
        from et_service.monitoring_agent.constants import FEATURE_NAMES

        snapshot = {name: 0.5 for name in FEATURE_NAMES}
        result = _parse_feature_snapshot(snapshot)

        self.assertIsInstance(result, np.ndarray)
        self.assertEqual(len(result), 15)  # TMA has 15 features

    def test_parse_json_string_snapshot(self):
        """JSON string is parsed correctly."""
        import json
        from et_service.pattern_agent.sequence_builder import _parse_feature_snapshot
        from et_service.pattern_agent.constants import FEATURE_DIM

        snapshot = json.dumps([0.2] * FEATURE_DIM)
        result = _parse_feature_snapshot(snapshot)

        self.assertIsInstance(result, np.ndarray)


if __name__ == '__main__':
    unittest.main()
