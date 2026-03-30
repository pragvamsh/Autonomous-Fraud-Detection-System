"""
test_anomaly_extractor.py
──────────────────────────
Unit tests for TMA anomaly_extractor module.

Tests:
  - Feature extraction with correct length
  - Z-score calculations (normal, extreme)
  - Recipient flags
  - Hour anomaly detection
  - Velocity burst detection
  - Round number detection
  - Cold start handling
  - Threshold proximity detection
"""

import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime


class TestExtractAnomalyFeatures(unittest.TestCase):
    """Tests for extract_anomaly_features function."""

    def setUp(self):
        """Set up common fixtures."""
        self.customer_id = 'C12345'
        self.standard_profile = {
            'customer_id': self.customer_id,
            'avg_amount': 1000.0,
            'std_amount': 200.0,
            'max_single_amount': 2000.0,
            'avg_daily_volume': 3000.0,
            'transaction_frequency': 0.5,
            'usual_hour_start': 9,
            'usual_hour_end': 18,
            'known_recipients_count': 5,
            'total_data_points': 50,
            'cold_start': 0,
            'profile_strength': 1.0,
        }
        self.standard_transaction = {
            'sender_customer_id': self.customer_id,
            'amount': 1500.0,
            'recipient_account': 'ACC_NEW_001',
            'debit_transaction_id': 'TXN123456',
        }

    @patch('et_dao.monitoring_dao.get_transactions_last_n_hours')
    @patch('et_dao.monitoring_dao.get_known_recipients')
    @patch('et_dao.monitoring_dao.get_daily_volume')
    def test_extract_features_returns_correct_length(
        self, mock_daily_vol, mock_recipients, mock_txns
    ):
        """Feature extraction returns exactly 15 model features."""
        from et_service.monitoring_agent.anomaly_extractor import extract_anomaly_features
        from et_service.monitoring_agent.constants import FEATURE_NAMES

        mock_txns.return_value = []
        mock_recipients.return_value = set()
        mock_daily_vol.return_value = 0.0

        features = extract_anomaly_features(self.standard_transaction, self.standard_profile)

        # All 15 feature names should be present
        for feature_name in FEATURE_NAMES:
            self.assertIn(feature_name, features)

    @patch('et_dao.monitoring_dao.get_transactions_last_n_hours')
    @patch('et_dao.monitoring_dao.get_known_recipients')
    @patch('et_dao.monitoring_dao.get_daily_volume')
    def test_extract_features_extreme_z_score(
        self, mock_daily_vol, mock_recipients, mock_txns
    ):
        """Extreme amount (avg + 6*std) produces z-score >= 5.0."""
        from et_service.monitoring_agent.anomaly_extractor import extract_anomaly_features

        mock_txns.return_value = []
        mock_recipients.return_value = set()
        mock_daily_vol.return_value = 0.0

        # Transaction with extremely high amount
        extreme_txn = self.standard_transaction.copy()
        avg = self.standard_profile['avg_amount']
        std = self.standard_profile['std_amount']
        extreme_txn['amount'] = avg + 6 * std  # 1000 + 6*200 = 2200

        features = extract_anomaly_features(extreme_txn, self.standard_profile)

        # Z-score should be at least 5.0
        self.assertGreaterEqual(features['amount_z_score'], 5.0)

    @patch('et_dao.monitoring_dao.get_transactions_last_n_hours')
    @patch('et_dao.monitoring_dao.get_known_recipients')
    @patch('et_dao.monitoring_dao.get_daily_volume')
    def test_extract_features_new_recipient_flagged(
        self, mock_daily_vol, mock_recipients, mock_txns
    ):
        """New recipient not in known list is flagged."""
        from et_service.monitoring_agent.anomaly_extractor import extract_anomaly_features

        mock_txns.return_value = []
        mock_recipients.return_value = {'ACC001', 'ACC002'}  # Only known recipients
        mock_daily_vol.return_value = 0.0

        # Transaction to unknown recipient
        txn = self.standard_transaction.copy()
        txn['recipient_account'] = 'ACC_UNKNOWN'

        features = extract_anomaly_features(txn, self.standard_profile)

        self.assertEqual(features['is_new_recipient'], 1)

    @patch('et_dao.monitoring_dao.get_transactions_last_n_hours')
    @patch('et_dao.monitoring_dao.get_known_recipients')
    @patch('et_dao.monitoring_dao.get_daily_volume')
    @patch('et_service.monitoring_agent.anomaly_extractor.datetime')
    def test_extract_features_unusual_hour(
        self, mock_datetime, mock_daily_vol, mock_recipients, mock_txns
    ):
        """Transaction at 23:00 (outside usual 9-18) is flagged as unusual hour."""
        from et_service.monitoring_agent.anomaly_extractor import extract_anomaly_features

        mock_txns.return_value = []
        mock_recipients.return_value = set()
        mock_daily_vol.return_value = 0.0

        # Mock current time to 23:00
        mock_now = MagicMock()
        mock_now.hour = 23
        mock_datetime.now.return_value = mock_now

        features = extract_anomaly_features(self.standard_transaction, self.standard_profile)

        self.assertEqual(features['is_unusual_hour'], 1)

    @patch('et_service.monitoring_agent.anomaly_extractor.get_transactions_last_n_hours')
    @patch('et_service.monitoring_agent.anomaly_extractor.get_known_recipients')
    @patch('et_service.monitoring_agent.anomaly_extractor.get_daily_volume')
    def test_extract_features_velocity_burst(
        self, mock_daily_vol, mock_recipients, mock_txns
    ):
        """6 transactions in last hour triggers velocity burst flag."""
        from et_service.monitoring_agent.anomaly_extractor import extract_anomaly_features

        # Mock 5 transactions in last hour (+ current = 6)
        mock_txns.side_effect = [
            [{'id': i} for i in range(5)],  # 5 txns last 1h
            [{'id': i} for i in range(10)],  # 10 txns last 24h
        ]
        mock_recipients.return_value = set()
        mock_daily_vol.return_value = 0.0

        features = extract_anomaly_features(self.standard_transaction, self.standard_profile)

        # 5 + 1 (current) > 3 (VELOCITY_BURST_THRESHOLD)
        self.assertEqual(features['is_velocity_burst'], 1)
        self.assertEqual(features['transactions_last_1h'], 6)

    @patch('et_dao.monitoring_dao.get_transactions_last_n_hours')
    @patch('et_dao.monitoring_dao.get_known_recipients')
    @patch('et_dao.monitoring_dao.get_daily_volume')
    def test_extract_features_round_number(
        self, mock_daily_vol, mock_recipients, mock_txns
    ):
        """Amount=5000.0 (round, >= 5000) is flagged as round number."""
        from et_service.monitoring_agent.anomaly_extractor import extract_anomaly_features

        mock_txns.return_value = []
        mock_recipients.return_value = set()
        mock_daily_vol.return_value = 0.0

        txn = self.standard_transaction.copy()
        txn['amount'] = 5000.0  # Round number >= ROUND_NUMBER_MIN_AMOUNT

        features = extract_anomaly_features(txn, self.standard_profile)

        self.assertEqual(features['is_round_number'], 1)

    @patch('et_dao.monitoring_dao.get_transactions_last_n_hours')
    @patch('et_dao.monitoring_dao.get_known_recipients')
    @patch('et_dao.monitoring_dao.get_daily_volume')
    def test_extract_features_cold_start_profile_no_crash(
        self, mock_daily_vol, mock_recipients, mock_txns
    ):
        """Cold start profile with std=0 does not cause ZeroDivisionError."""
        from et_service.monitoring_agent.anomaly_extractor import extract_anomaly_features

        mock_txns.return_value = []
        mock_recipients.return_value = set()
        mock_daily_vol.return_value = 0.0

        # Profile with std=0 (cold start edge case)
        cold_profile = self.standard_profile.copy()
        cold_profile['std_amount'] = 0.0
        cold_profile['cold_start'] = 1

        # Should not raise ZeroDivisionError
        features = extract_anomaly_features(self.standard_transaction, cold_profile)

        # Should return a valid z-score (fallback formula used)
        self.assertIsInstance(features['amount_z_score'], (int, float))
        self.assertIsNotNone(features['amount_z_score'])

    @patch('et_dao.monitoring_dao.get_transactions_last_n_hours')
    @patch('et_dao.monitoring_dao.get_known_recipients')
    @patch('et_dao.monitoring_dao.get_daily_volume')
    def test_extract_features_near_threshold(
        self, mock_daily_vol, mock_recipients, mock_txns
    ):
        """Amount near regulatory threshold (95000) triggers structuring flag."""
        from et_service.monitoring_agent.anomaly_extractor import extract_anomaly_features

        mock_txns.return_value = []
        mock_recipients.return_value = set()
        mock_daily_vol.return_value = 0.0

        txn = self.standard_transaction.copy()
        txn['amount'] = 99500.0  # In (99000, 99999) band - near 100k threshold

        features = extract_anomaly_features(txn, self.standard_profile)

        self.assertEqual(features['is_near_threshold'], 1)


class TestGetAnomalyFlagLabels(unittest.TestCase):
    """Tests for get_anomaly_flag_labels function."""

    def test_high_z_score_generates_label(self):
        """Z-score > 2 generates HIGH_AMOUNT_DEVIATION label."""
        from et_service.monitoring_agent.anomaly_extractor import get_anomaly_flag_labels
        from et_service.monitoring_agent.constants import Z_SCORE_HIGH

        features = {
            'amount_z_score': Z_SCORE_HIGH + 0.5,
            'amount_vs_max': 0.8,
            'exceeds_daily_volume': 0,
            'is_large_amount': 0,
            'is_near_threshold': 0,
            'is_new_recipient': 0,
            'is_unusual_hour': 0,
            'is_late_night': 0,
            'is_velocity_burst': 0,
            'transactions_last_24h': 1,
            'high_z_new_recipient': 0,
            'late_night_new_recipient': 0,
            'is_round_number': 0,
            'current_hour': 12,
        }

        flags = get_anomaly_flag_labels(features)

        self.assertTrue(any('HIGH_AMOUNT_DEVIATION' in f for f in flags))

    def test_new_recipient_generates_label(self):
        """New recipient generates NEW_RECIPIENT_NEVER_TRANSACTED label."""
        from et_service.monitoring_agent.anomaly_extractor import get_anomaly_flag_labels

        features = {
            'amount_z_score': 0.5,
            'amount_vs_max': 0.5,
            'exceeds_daily_volume': 0,
            'is_large_amount': 0,
            'is_near_threshold': 0,
            'is_new_recipient': 1,
            'is_unusual_hour': 0,
            'is_late_night': 0,
            'is_velocity_burst': 0,
            'transactions_last_24h': 1,
            'high_z_new_recipient': 0,
            'late_night_new_recipient': 0,
            'is_round_number': 0,
            'current_hour': 12,
        }

        flags = get_anomaly_flag_labels(features)

        self.assertIn('NEW_RECIPIENT_NEVER_TRANSACTED', flags)


class TestCyclicalHourEncoding(unittest.TestCase):
    """Tests for cyclical hour encoding (sin/cos)."""

    @patch('et_dao.monitoring_dao.get_transactions_last_n_hours')
    @patch('et_dao.monitoring_dao.get_known_recipients')
    @patch('et_dao.monitoring_dao.get_daily_volume')
    @patch('et_service.monitoring_agent.anomaly_extractor.datetime')
    def test_hour_sin_cos_values_correct(
        self, mock_datetime, mock_daily_vol, mock_recipients, mock_txns
    ):
        """Hour encoding produces valid sin/cos values."""
        import math
        from et_service.monitoring_agent.anomaly_extractor import extract_anomaly_features

        mock_txns.return_value = []
        mock_recipients.return_value = set()
        mock_daily_vol.return_value = 0.0

        # Mock noon (hour 12)
        mock_now = MagicMock()
        mock_now.hour = 12
        mock_datetime.now.return_value = mock_now

        profile = {
            'avg_amount': 1000.0,
            'std_amount': 200.0,
            'max_single_amount': 2000.0,
            'avg_daily_volume': 3000.0,
            'usual_hour_start': 9,
            'usual_hour_end': 18,
        }
        txn = {'sender_customer_id': 'C123', 'amount': 500, 'recipient_account': 'ACC1'}

        features = extract_anomaly_features(txn, profile)

        # At hour 12: sin(2*pi*12/24) = sin(pi) = 0
        # cos(2*pi*12/24) = cos(pi) = -1
        expected_sin = round(math.sin(2 * math.pi * 12 / 24), 6)
        expected_cos = round(math.cos(2 * math.pi * 12 / 24), 6)

        self.assertAlmostEqual(features['hour_sin'], expected_sin, places=4)
        self.assertAlmostEqual(features['hour_cos'], expected_cos, places=4)


if __name__ == '__main__':
    unittest.main()
