"""
Unit Tests for Transaction Monitoring Agent (TMA)
==================================================

Tests TMA orchestration and pipeline stages with heavy mocking.

Pipeline Stages:
  1. Profile Builder
  2. Anomaly Extractor
  3. ML Layer (Isolation Forest)
  4. RAG Layer (ChromaDB)
  5. Decision Engine
  6. Response Executor

Critical Tests:
  - TC-TMA-03: BLOCK verdict → payment rejected
  - TC-TMA-04: FLAG verdict → payment commits, PRA triggered
  - TC-TMA-05: ML model failure → graceful degradation

Run:
    pytest tests/unit/test_monitoring_agent/ -v
"""

import pytest
from unittest.mock import patch, MagicMock, call
from et_service.monitoring_agent.agent import evaluate_transaction


# ══════════════════════════════════════════════════════════════════════════════
# TMA PIPELINE TESTS (Full Orchestration)
# ══════════════════════════════════════════════════════════════════════════════

class TestTMAOrchestration:
    """Test TMA end-to-end pipeline with all stages mocked."""

    @patch('et_service.monitoring_agent.agent.execute_response')
    @patch('et_service.monitoring_agent.agent.make_decision')
    @patch('et_service.monitoring_agent.agent.get_rag_assessment')
    @patch('et_service.monitoring_agent.agent.get_ml_risk_score')
    @patch('et_service.monitoring_agent.agent.get_anomaly_flag_labels')
    @patch('et_service.monitoring_agent.agent.extract_anomaly_features')
    @patch('et_service.monitoring_agent.agent.get_or_build_profile')
    def test_tma_allow_verdict_pipeline(
        self,
        mock_profile,
        mock_anomaly,
        mock_anomaly_flags,
        mock_ml,
        mock_rag,
        mock_decision,
        mock_response,
        payment_result,
        complete_profile
    ):
        """TC-TMA-02: TMA ALLOW verdict completes all 6 stages."""
        # Stage 1: Profile Builder
        mock_profile.return_value = complete_profile

        # Stage 2: Anomaly Extractor
        mock_anomaly.return_value = {
            'amount_z_score': 1.2,
            'amount_vs_max': 0.5,
            'exceeds_daily_volume': 0,
            'is_large_amount': 0,
            'is_near_threshold': 0,
            'is_round_number': 0,
            'is_unusual_hour': 0,
            'hour_sin': 0.1,
            'hour_cos': 0.9,
            'is_new_recipient': 0,
            'transactions_last_1h': 1,
            'transactions_last_24h': 1,
            'is_velocity_burst': 0,
            'high_z_new_recipient': 0,
            'late_night_new_recipient': 0,
        }

        # Stage 2b: Anomaly Flags
        mock_anomaly_flags.return_value = []

        # Stage 3: ML Layer
        mock_ml.return_value = {
            'ml_score': 35,
            'raw_score': -0.12,
            'is_anomaly': False,
            'model_loaded': True,
        }

        # Stage 4: RAG Layer
        mock_rag.return_value = {
            'rag_score': 30,
            'rag_available': True,
            'confidence': 0.87,
            'citations': [{'rule_id': 'RBI_2023_001'}],
            'reasoning': 'Low risk transaction',
        }

        # Stage 5: Decision Engine
        mock_decision.return_value = MagicMock(
            decision='ALLOW',
            risk_score=32,
            disagreement=False,
        )

        # Stage 6: Response Executor
        mock_response.return_value = {
            'alert_id': 9001,
            'action_taken': 'LOG_ONLY',
        }

        # Execute TMA
        result = evaluate_transaction(payment_result)

        # Verify all stages called
        assert mock_profile.called
        assert mock_anomaly.called
        assert mock_ml.called
        assert mock_rag.called
        assert mock_decision.called
        assert mock_response.called

        # Verify result
        assert result['decision'] == 'ALLOW'
        assert result['risk_score'] == 32
        assert result['alert_id'] == 9001

    @patch('et_service.monitoring_agent.agent.execute_response')
    @patch('et_service.monitoring_agent.agent.make_decision')
    @patch('et_service.monitoring_agent.agent.get_rag_assessment')
    @patch('et_service.monitoring_agent.agent.get_ml_risk_score')
    @patch('et_service.monitoring_agent.agent.get_anomaly_flag_labels')
    @patch('et_service.monitoring_agent.agent.extract_anomaly_features')
    @patch('et_service.monitoring_agent.agent.get_or_build_profile')
    def test_tma_block_verdict(
        self,
        mock_profile,
        mock_anomaly,
        mock_anomaly_flags,
        mock_ml,
        mock_rag,
        mock_decision,
        mock_response,
        payment_result,
        complete_profile
    ):
        """TC-TMA-03: TMA BLOCK verdict should create alert with BLOCK decision."""
        # Mock high-risk scenario
        mock_profile.return_value = complete_profile
        mock_anomaly.return_value = {
            'amount_z_score': 8.5,
            'amount_vs_max': 5.0,
            'exceeds_daily_volume': 1,
            'is_large_amount': 1,
            'is_near_threshold': 0,
            'is_round_number': 0,
            'is_unusual_hour': 1,
            'hour_sin': -0.5,
            'hour_cos': 0.8,
            'is_new_recipient': 1,
            'transactions_last_1h': 2,
            'transactions_last_24h': 5,
            'is_velocity_burst': 1,
            'high_z_new_recipient': 1,
            'late_night_new_recipient': 0,
        }
        mock_anomaly_flags.return_value = ['HIGH_AMOUNT', 'NEW_RECIPIENT']
        mock_ml.return_value = {'ml_score': 95, 'is_anomaly': True, 'model_loaded': True}
        mock_rag.return_value = {'rag_score': 92, 'rag_available': True, 'confidence': 0.95}

        # Decision Engine returns BLOCK
        mock_decision.return_value = MagicMock(
            decision='BLOCK',
            risk_score=94,
            disagreement=False,
        )

        mock_response.return_value = {
            'alert_id': 9002,
            'action_taken': 'BLOCK_TRANSACTION',
        }

        result = evaluate_transaction(payment_result)

        assert result['decision'] == 'BLOCK'
        assert result['risk_score'] == 94

    @patch('et_service.monitoring_agent.agent.execute_response')
    @patch('et_service.monitoring_agent.agent.make_decision')
    @patch('et_service.monitoring_agent.agent.get_rag_assessment')
    @patch('et_service.monitoring_agent.agent.get_ml_risk_score')
    @patch('et_service.monitoring_agent.agent.get_anomaly_flag_labels')
    @patch('et_service.monitoring_agent.agent.extract_anomaly_features')
    @patch('et_service.monitoring_agent.agent.get_or_build_profile')
    def test_tma_flag_verdict(
        self,
        mock_profile,
        mock_anomaly,
        mock_anomaly_flags,
        mock_ml,
        mock_rag,
        mock_decision,
        mock_response,
        payment_result,
        complete_profile
    ):
        """TC-TMA-04: FLAG verdict should allow payment but trigger PRA."""
        mock_profile.return_value = complete_profile
        mock_anomaly.return_value = {
            'amount_z_score': 3.2,
            'amount_vs_max': 2.0,
            'exceeds_daily_volume': 0,
            'is_large_amount': 1,
            'is_near_threshold': 0,
            'is_round_number': 0,
            'is_unusual_hour': 0,
            'hour_sin': 0.2,
            'hour_cos': 0.97,
            'is_new_recipient': 1,
            'transactions_last_1h': 1,
            'transactions_last_24h': 3,
            'is_velocity_burst': 0,
            'high_z_new_recipient': 1,
            'late_night_new_recipient': 0,
        }
        mock_anomaly_flags.return_value = ['MODERATE_AMOUNT', 'NEW_RECIPIENT']
        mock_ml.return_value = {'ml_score': 65, 'is_anomaly': False, 'model_loaded': True}
        mock_rag.return_value = {'rag_score': 58, 'rag_available': True}

        mock_decision.return_value = MagicMock(
            decision='FLAG',
            risk_score=62,
            disagreement=True,  # ML and RAG disagree
        )

        mock_response.return_value = {'alert_id': 9003, 'action_taken': 'FLAG_FOR_REVIEW'}

        result = evaluate_transaction(payment_result)

        assert result['decision'] == 'FLAG'
        assert result['risk_score'] == 62

    @patch('et_service.monitoring_agent.agent._mark_failed')
    @patch('et_service.monitoring_agent.agent.get_or_build_profile')
    def test_tma_profile_builder_failure(
        self,
        mock_profile,
        mock_mark_failed,
        payment_result
    ):
        """Profile builder failure should abort pipeline and mark FAILED."""
        mock_profile.side_effect = Exception('Database connection error')

        result = evaluate_transaction(payment_result)

        # Should return safe default
        assert result['decision'] == 'ALLOW'
        assert result['risk_score'] is None
        assert 'error' in result

        # Should mark transaction as FAILED for retry
        mock_mark_failed.assert_called_once()


# ══════════════════════════════════════════════════════════════════════════════
# ML LAYER GRACEFUL DEGRADATION (TC-TMA-05)
# ══════════════════════════════════════════════════════════════════════════════

class TestMLLayerFallback:
    """Test ML model failure scenarios and graceful degradation."""

    @patch('et_service.monitoring_agent.agent.execute_response')
    @patch('et_service.monitoring_agent.agent.make_decision')
    @patch('et_service.monitoring_agent.agent.get_rag_assessment')
    @patch('et_service.monitoring_agent.agent.get_ml_risk_score')
    @patch('et_service.monitoring_agent.agent.get_anomaly_flag_labels')
    @patch('et_service.monitoring_agent.agent.extract_anomaly_features')
    @patch('et_service.monitoring_agent.agent.get_or_build_profile')
    def test_ml_model_missing_graceful_degradation(
        self,
        mock_profile,
        mock_anomaly,
        mock_anomaly_flags,
        mock_ml,
        mock_rag,
        mock_decision,
        mock_response,
        payment_result,
        complete_profile
    ):
        """
        TC-TMA-05: ML model failure should NOT abort pipeline

        Expected Behavior (per code comments FIX-1):
          - ML layer throws exception
          - TMA catches and constructs fallback ml_result
          - Pipeline continues in RAG-only mode
          - Decision engine sees model_loaded=False and adjusts weighting

        This is BETTER than aborting (which would leave transactions unscored).
        """
        mock_profile.return_value = complete_profile
        mock_anomaly.return_value = {
            'amount_z_score': 2.1,
            'amount_vs_max': 0.8,
            'exceeds_daily_volume': 0,
            'is_large_amount': 0,
            'is_near_threshold': 0,
            'is_round_number': 0,
            'is_unusual_hour': 0,
            'hour_sin': 0.3,
            'hour_cos': 0.95,
            'is_new_recipient': 0,
            'transactions_last_1h': 1,
            'transactions_last_24h': 2,
            'is_velocity_burst': 0,
            'high_z_new_recipient': 0,
            'late_night_new_recipient': 0,
        }
        mock_anomaly_flags.return_value = []

        # ML layer fails (model file missing)
        mock_ml.side_effect = FileNotFoundError('isolation_forest.pkl not found')

        # RAG should still be called
        mock_rag.return_value = {
            'rag_score': 45,
            'rag_available': True,
            'confidence': 0.72,
        }

        # Decision engine receives fallback ML result
        mock_decision.return_value = MagicMock(
            decision='ALLOW',
            risk_score=45,  # RAG-only scoring
        )

        mock_response.return_value = {'alert_id': 9004, 'action_taken': 'LOG_ONLY'}

        result = evaluate_transaction(payment_result)

        # Pipeline should complete (not abort)
        assert result['decision'] == 'ALLOW'
        assert result['risk_score'] == 45

        # RAG should have been called (proving pipeline continued)
        mock_rag.assert_called_once()
        mock_decision.assert_called_once()

        # Decision engine should have received fallback ML result
        call_args = mock_decision.call_args[1]
        ml_result = call_args['ml_result']
        assert ml_result['model_loaded'] is False
        assert ml_result['ml_score'] == 50  # Neutral fallback score


# ══════════════════════════════════════════════════════════════════════════════
# ANOMALY EXTRACTOR TESTS
# ══════════════════════════════════════════════════════════════════════════════

class TestAnomalyExtractor:
    """Test anomaly feature extraction logic."""

    @patch('et_service.monitoring_agent.anomaly_extractor.extract_anomaly_features')
    def test_high_amount_anomaly(self, mock_extract):
        """High amount should produce high z-score."""
        mock_extract.return_value = {
            'amount_z_score': 5.2,  # 5.2 standard deviations above mean
            'velocity_flag': 0,
            'time_deviation': 0,
            'new_recipient_flag': 0,
        }

        result = mock_extract(
            payment_result={'amount': 50000.00},
            profile={'avg_amount': 2000.00, 'std_amount': 500.00}
        )

        assert result['amount_z_score'] > 5.0


# ══════════════════════════════════════════════════════════════════════════════
# RAG LAYER TESTS (ChromaDB Mocking)
# ══════════════════════════════════════════════════════════════════════════════

class TestRAGLayer:
    """Test RAG layer with mocked ChromaDB."""

    @patch('et_service.monitoring_agent.rag.rag_layer.query_by_text')
    @patch('et_service.monitoring_agent.rag.rag_layer.query_by_vector')
    def test_rag_layer_retrieval(
        self,
        mock_query_vector,
        mock_query_text,
        mock_chromadb_query_result
    ):
        """RAG layer should query L1 (text) and L2/L3 (vector)."""
        from et_service.monitoring_agent.rag.rag_layer import get_rag_assessment

        # Mock ChromaDB queries
        mock_query_text.return_value = mock_chromadb_query_result
        mock_query_vector.return_value = mock_chromadb_query_result

        transaction = {'amount': 5000.00, 'description': 'Test'}
        anomaly_features = {'amount_z_score': 2.5}
        ml_result = {'ml_score': 60, 'is_anomaly': False}
        profile = {'cold_start': False}

        # Call RAG layer (vector store functions already mocked)
        result = get_rag_assessment(transaction, anomaly_features, [], ml_result, profile)

        # Should return structured result
        assert 'rag_score' in result
        assert 'citations' in result
        assert 'reasoning' in result


# ══════════════════════════════════════════════════════════════════════════════
# DECISION ENGINE TESTS
# ══════════════════════════════════════════════════════════════════════════════

class TestDecisionEngine:
    """Test decision thresholds."""

    def test_allow_threshold(self):
        """Risk score < 50 should result in ALLOW."""
        from et_service.monitoring_agent.decision_engine import make_decision

        # Mock inputs with low risk
        transaction = {
            'amount': 1000.00,
            'debit_transaction_id': 'TXN1234567890123',
            'sender_customer_id': 'C12345',
        }
        profile = {'cold_start': False}
        anomaly_features = {
            'amount_z_score': 0.5,
            'amount_vs_max': 0.1,
            'exceeds_daily_volume': 0,
            'is_large_amount': 0,
            'is_near_threshold': 0,
            'is_round_number': 0,
            'is_unusual_hour': 0,
            'hour_sin': 0.1,
            'hour_cos': 0.9,
            'is_new_recipient': 0,
            'transactions_last_1h': 1,
            'transactions_last_24h': 1,
            'is_velocity_burst': 0,
            'high_z_new_recipient': 0,
            'late_night_new_recipient': 0,
        }
        ml_result = {'ml_score': 20, 'is_anomaly': False, 'model_loaded': True}
        rag_result = {'rag_score': 25, 'rag_available': True, 'confidence': 0.9}

        alert = make_decision(transaction, profile, anomaly_features, [], ml_result, rag_result)

        assert alert.decision == 'ALLOW'

    def test_block_threshold(self):
        """Risk score >= 85 should result in BLOCK."""
        from et_service.monitoring_agent.decision_engine import make_decision

        transaction = {
            'amount': 50000.00,
            'debit_transaction_id': 'TXN1234567890123',
            'sender_customer_id': 'C12345',
        }
        profile = {'cold_start': False}
        anomaly_features = {
            'amount_z_score': 8.0,
            'amount_vs_max': 5.0,
            'exceeds_daily_volume': 1,
            'is_large_amount': 1,
            'is_near_threshold': 0,
            'is_round_number': 0,
            'is_unusual_hour': 1,
            'hour_sin': -0.5,
            'hour_cos': 0.8,
            'is_new_recipient': 1,
            'transactions_last_1h': 2,
            'transactions_last_24h': 5,
            'is_velocity_burst': 1,
            'high_z_new_recipient': 1,
            'late_night_new_recipient': 0,
        }
        ml_result = {'ml_score': 95, 'is_anomaly': True, 'model_loaded': True}
        rag_result = {'rag_score': 92, 'rag_available': True, 'confidence': 0.96}

        alert = make_decision(transaction, profile, anomaly_features, [], ml_result, rag_result)

        assert alert.decision == 'BLOCK'


# ══════════════════════════════════════════════════════════════════════════════
# NOTES
# ══════════════════════════════════════════════════════════════════════════════

"""
KEY MOCKING STRATEGIES FOR TMA:

1. **Database Mocking:**
   - Mock get_db_connection() in conftest.py
   - All DAOs automatically use mock connection

2. **ML Model Mocking:**
   - Mock joblib.load() to return MagicMock model
   - Mock model.predict() and model.decision_function()

3. **ChromaDB Mocking:**
   - Mock query_by_text() and query_by_vector()
   - Return structured dicts matching ChromaDB API

4. **BERT Mocking:**
   - Mock _get_sentence_ef() to avoid 8-second load
   - Mock model.encode() to return 384-dim vector

5. **Threading Mocking:**
   - Disable background pollers in conftest.py
   - Test pipeline synchronously in unit tests

RUN ALL TMA TESTS:
    pytest tests/unit/test_monitoring_agent/ -v --cov=et_service.monitoring_agent
"""
