"""
pytest configuration and shared fixtures
=========================================

Run tests:
    pytest tests/                     # All tests
    pytest tests/unit/                # Unit tests only
    pytest tests/integration/         # Integration tests only
    pytest -v tests/unit/test_payment_service.py  # Specific file
    pytest -k "balance"               # Tests matching "balance"
    pytest --cov=et_service --cov-report=html  # With coverage

Requirements:
    pip install pytest pytest-cov pytest-mock
"""

import pytest
from unittest.mock import MagicMock, Mock, patch
from datetime import datetime, timedelta


# ══════════════════════════════════════════════════════════════════════════════
# DATABASE MOCKING
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def mock_db_connection():
    """Mock MySQL connection - prevents real DB access."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.fetchone.return_value = None
    mock_cursor.fetchall.return_value = []
    return mock_conn, mock_cursor


@pytest.fixture(autouse=True)
def mock_get_db_connection(mock_db_connection):
    """Automatically patch get_db_connection for all tests."""
    with patch('db.get_db_connection') as mock:
        mock.return_value = mock_db_connection[0]
        yield mock


# ══════════════════════════════════════════════════════════════════════════════
# CUSTOMER FIXTURES
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def sample_customer():
    """Standard customer with Rs 10,000 balance."""
    return {
        'customer_id': 'C12345',
        'account_number': '123456789012',
        'full_name': 'John Doe',
        'email': 'john@test.com',
        'phone_number': '9876543210',
        'balance': 10000.00,
        'account_type': 'savings',
        'is_frozen': False,
    }


@pytest.fixture
def low_balance_customer():
    """Customer with exactly Rs 500 balance (for edge case testing)."""
    return {
        'customer_id': 'C99999',
        'account_number': '999999999999',
        'full_name': 'Jane Smith',
        'email': 'jane@test.com',
        'phone_number': '9999999999',
        'balance': 500.00,
        'account_type': 'savings',
        'is_frozen': False,
    }


# ══════════════════════════════════════════════════════════════════════════════
# PAYMENT FIXTURES
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def valid_payment_data():
    """Valid payment request data."""
    return {
        'sender_customer_id': 'C12345',
        'sender_account': '123456789012',
        'recipient_account': '987654321098',
        'amount': 1000.00,
        'description': 'Test payment',
    }


@pytest.fixture
def payment_result():
    """Mock payment_result dict returned by process_payment()."""
    return {
        'payment_id': 'PAY1234567890123',
        'debit_transaction_id': 'TXN1234567890123',
        'credit_transaction_id': 'TXN9876543210987',
        'amount': 1000.00,
        'sender_customer_id': 'C12345',
        'sender_account': '123456789012',
        'recipient_account': '987654321098',
        'recipient_customer_id': 'C67890',
        'description': 'Test payment',
        'created_at': 'now',
    }


# ══════════════════════════════════════════════════════════════════════════════
# FRAUD ALERT FIXTURES
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def fraud_alert_tma():
    """TMA fraud alert (before PRA processing)."""
    return {
        'id': 1001,
        'alert_id': 1001,
        'transaction_id': 'TXN1234567890123',
        'customer_id': 'C12345',
        'risk_score': 75,
        'ml_score': 70,
        'rag_score': 80,
        'decision': 'FLAG',
        'pra_processed': 0,
        'raa_processed': 0,
        'anomaly_flags': ['high_amount', 'unusual_time'],
        'typology_code': 'AML_STRUCTURING',
    }


@pytest.fixture
def fraud_alert_pra_complete():
    """PRA-processed alert (ready for RAA)."""
    return {
        'id': 1001,
        'alert_id': 1001,
        'customer_id': 'C12345',
        'risk_score': 75,
        'decision': 'FLAG',
        'pra_processed': 1,
        'pra_verdict': 'ESCALATE',
        'pattern_score': 82.50,
        'bilstm_score': 78.30,
        'urgency_multiplier': 1.25,
        'typology_code': 'AML_STRUCTURING',
        'raa_processed': 0,
    }


# ══════════════════════════════════════════════════════════════════════════════
# ML MODEL MOCKING
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def mock_isolation_forest():
    """Mock Isolation Forest model."""
    mock_model = MagicMock()
    mock_model.predict.return_value = [1]  # 1 = normal, -1 = anomaly
    mock_model.decision_function.return_value = [-0.05]  # Anomaly score
    return mock_model


@pytest.fixture
def mock_bilstm_model():
    """Mock BiLSTM model inference."""
    with patch('et_service.pattern_agent.bilstm_model.run_inference') as mock:
        mock.return_value = {
            'bilstm_score': 75.0,
            'hidden_state': [0.1] * 128,  # 128-dim vector
        }
        yield mock


@pytest.fixture
def mock_sentence_transformer():
    """Mock SentenceTransformer (BERT embeddings)."""
    mock_model = MagicMock()
    # Return a 384-dim vector (all-MiniLM-L6-v2 output size)
    mock_model.encode.return_value = [0.01] * 384
    return mock_model


# ══════════════════════════════════════════════════════════════════════════════
# CHROMADB MOCKING
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def mock_chromadb_query_result():
    """Mock ChromaDB query result."""
    return {
        'ids': [['doc1', 'doc2', 'doc3']],
        'distances': [[0.15, 0.23, 0.31]],
        'metadatas': [[
            {'rule_id': 'RBI_2023_001', 'severity': 'HIGH'},
            {'rule_id': 'RBI_2023_002', 'severity': 'MEDIUM'},
            {'rule_id': 'FATF_2024_010', 'severity': 'HIGH'},
        ]],
        'documents': [[
            'Suspicious transaction reporting threshold...',
            'KYC verification requirements...',
            'AML compliance guidelines...',
        ]],
    }


@pytest.fixture
def mock_chromadb_collections():
    """Mock ChromaDB collection objects."""
    mock_l1 = MagicMock()
    mock_l2 = MagicMock()
    mock_l3 = MagicMock()

    with patch('et_service.monitoring_agent.rag.vector_store.COLLECTIONS') as mock_collections:
        mock_collections['L1'] = mock_l1
        mock_collections['L2'] = mock_l2
        mock_collections['L3'] = mock_l3
        yield {
            'L1': mock_l1,
            'L2': mock_l2,
            'L3': mock_l3,
        }


# ══════════════════════════════════════════════════════════════════════════════
# OTP FIXTURES
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def mock_send_otp_email():
    """Mock OTP email sending."""
    with patch('et_service.otp_service.send_otp_email') as mock:
        mock.return_value = True  # Email sent successfully
        yield mock


@pytest.fixture
def sample_otp():
    """Generated OTP for testing."""
    return '123456'


# ══════════════════════════════════════════════════════════════════════════════
# TIME MOCKING (for OTP expiry tests)
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def frozen_time():
    """Mock datetime.now() to return a fixed time."""
    fixed_time = datetime(2026, 3, 21, 14, 30, 0)
    with patch('et_service.otp_service.datetime') as mock_dt:
        mock_dt.now.return_value = fixed_time
        mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
        yield fixed_time


# ══════════════════════════════════════════════════════════════════════════════
# BEHAVIORAL PROFILE FIXTURES
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def complete_profile():
    """Complete behavioural profile (all required fields for anomaly extractor)."""
    return {
        'customer_id': 'C12345',
        'cold_start': False,
        'profile_strength': 0.85,
        'avg_amount': 2500.00,
        'std_amount': 500.00,
        'max_single_amount': 8000.00,
        'avg_daily_volume': 15000.00,
        'transaction_frequency': 2.5,
        'usual_hour_start': 9,
        'usual_hour_end': 18,
        'known_recipients_count': 12,
        'total_data_points': 45,
    }


# ══════════════════════════════════════════════════════════════════════════════
# AGENT THREADING MOCKS
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def disable_agent_pollers():
    """Disable background polling threads for all agents during tests."""
    patches = [
        patch('et_service.pattern_agent.pra_agent.start_pra_poller'),
        patch('et_service.raa.raa_agent.RAAAgent.create'),
        patch('et_service.aba.aba_agent.ABAAgent.create'),
        patch('et_service.cla.start_cla_agent'),
    ]

    mocks = [p.start() for p in patches]
    yield mocks
    for p in patches:
        p.stop()
