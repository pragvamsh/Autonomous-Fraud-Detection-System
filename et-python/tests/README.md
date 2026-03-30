# Jatayu Test Suite

Comprehensive unit and integration tests for the Jatayu fraud detection system.

## 📁 Test Structure

```
tests/
├── conftest.py                      # Shared fixtures and configuration
├── unit/                            # Isolated component tests
│   ├── test_payment_service.py      # Payment validation, TC-PAY-*
│   ├── test_otp_service.py          # OTP generation/verification, TC-OTP-*
│   ├── test_monitoring_agent/       # TMA pipeline tests, TC-TMA-*
│   │   ├── test_agent.py            # Orchestrator
│   │   ├── test_profile_builder.py
│   │   ├── test_anomaly_extractor.py
│   │   ├── test_ml_layer.py
│   │   └── test_rag_layer.py
│   ├── test_pattern_agent/          # PRA tests, TC-PRA-*
│   │   ├── test_pra_agent.py
│   │   ├── test_sequence_builder.py
│   │   └── test_bilstm_model.py
│   ├── test_raa/                    # RAA tests, TC-RAA-*
│   │   ├── test_raa_agent.py
│   │   ├── test_tier_engine.py
│   │   └── test_score_engine.py
│   └── test_aba/                    # ABA tests, TC-ABA-*
│       ├── test_aba_agent.py
│       └── test_account_controller.py
├── integration/                     # Multi-component tests
│   ├── test_payment_flow.py         # End-to-end payment workflow
│   ├── test_tma_pra_pipeline.py     # TMA → PRA handoff
│   └── test_full_pipeline.py        # TMA → PRA → RAA → ABA
└── fixtures/                        # Reusable test data
    ├── sample_payments.py
    ├── sample_profiles.py
    └── sample_alerts.py
```

## 🚀 Setup

### 1. Install Test Dependencies

```bash
cd et-python
pip install -r requirements-test.txt
```

### 2. Verify Installation

```bash
pytest --version
# Should show: pytest 7.4.3
```

## ▶️ Running Tests

### All Tests
```bash
pytest tests/
```

### Unit Tests Only
```bash
pytest tests/unit/
```

### Specific Test File
```bash
pytest tests/unit/test_payment_service.py -v
```

### Specific Test Function
```bash
pytest tests/unit/test_payment_service.py::TestProcessPayment::test_insufficient_balance_edge_case -v
```

### Tests Matching Keyword
```bash
pytest -k "balance" -v          # Run all tests with "balance" in name
pytest -k "otp" -v              # Run all OTP tests
pytest -k "tma" -v              # Run all TMA tests
```

### With Coverage Report
```bash
# Terminal output
pytest --cov=et_service --cov=et_dao --cov=et_api

# HTML report (opens in browser)
pytest --cov=et_service --cov-report=html
open htmlcov/index.html
```

### Verbose Mode (Show Test Names)
```bash
pytest -v
```

### Stop on First Failure
```bash
pytest -x
```

### Run Last Failed Tests
```bash
pytest --lf
```

## 🎯 Critical Test Cases

### TC-PAY-06: Balance Validation Bug (WILL FAIL)
```bash
pytest tests/unit/test_payment_service.py::TestProcessPayment::test_insufficient_balance_edge_case -v
```
**Expected:** FAIL (bug in current code)
**After Fix:** PASS

This test validates the critical balance validation bug found in the manual test execution report.

### TC-TMA-05: ML Model Failure Graceful Degradation
```bash
pytest tests/unit/test_monitoring_agent/test_agent.py::TestMLLayerFallback::test_ml_model_missing_graceful_degradation -v
```
Tests that TMA continues in RAG-only mode when ML model is missing.

### TC-OTP-03: OTP Verification
```bash
pytest tests/unit/test_otp_service.py::TestOTPHashing::test_verify_correct_otp -v
```
Tests bcrypt OTP verification logic.

## 🔧 Coverage Goals

| Component               | Target Coverage | Priority |
|------------------------|-----------------|----------|
| Payment Service        | 100%            | Critical |
| OTP Service            | 100%            | Critical |
| TMA Orchestrator       | 90%             | High     |
| PRA Orchestrator       | 90%             | High     |
| RAA Orchestrator       | 90%             | High     |
| ABA Orchestrator       | 90%             | High     |
| ML/RAG Layers          | 80%             | Medium   |
| Database DAOs          | 90%             | High     |

## 🧪 Key Testing Strategies

### 1. Database Mocking
All tests use `mock_get_db_connection` fixture from `conftest.py`:

```python
@pytest.fixture
def mock_get_db_connection(mock_db_connection):
    """Automatically patch get_db_connection for all tests."""
    with patch('db.get_db_connection') as mock:
        mock.return_value = mock_db_connection[0]
        yield mock
```

**Why:** Prevents real database access, ensures test isolation.

### 2. ML Model Mocking
Mock Isolation Forest and BiLSTM models:

```python
@pytest.fixture
def mock_isolation_forest():
    mock_model = MagicMock()
    mock_model.predict.return_value = [1]  # 1 = normal
    mock_model.decision_function.return_value = [-0.05]
    return mock_model
```

**Why:** Avoids loading large model files (8+ second overhead).

### 3. ChromaDB Mocking
Mock vector store queries:

```python
@pytest.fixture
def mock_chromadb_query_result():
    return {
        'ids': [['doc1', 'doc2', 'doc3']],
        'distances': [[0.15, 0.23, 0.31]],
        'metadatas': [[...]],
        'documents': [[...]],
    }
```

**Why:** ChromaDB operations are expensive; mocking ensures fast tests.

### 4. SMTP Mocking
Mock email sending:

```python
@patch('et_service.otp_service.smtplib.SMTP')
def test_send_otp_email(mock_smtp_class):
    mock_smtp = MagicMock()
    mock_smtp_class.return_value.__enter__.return_value = mock_smtp
    # Test continues...
```

**Why:** Can't send real emails during testing.

### 5. Time Mocking
Mock datetime for OTP expiry tests:

```python
@pytest.fixture
def frozen_time():
    fixed_time = datetime(2026, 3, 21, 14, 30, 0)
    with patch('et_service.otp_service.datetime') as mock_dt:
        mock_dt.now.return_value = fixed_time
        yield fixed_time
```

**Why:** OTP expiry tests need controlled time progression.

### 6. Threading Disabling
Disable background pollers during tests:

```python
@pytest.fixture
def disable_agent_pollers():
    patches = [
        patch('et_service.pattern_agent.pra_agent.start_pra_poller'),
        patch('et_service.raa.raa_agent.RAAAgent.create'),
        # ...
    ]
    mocks = [p.start() for p in patches]
    yield mocks
    for p in patches:
        p.stop()
```

**Why:** Background threads interfere with unit test determinism.

## 📋 Test Case Mapping

Tests map directly to edge cases from `Jatayu_Edge_Case_Tests.pdf`:

| Test File                  | Test Cases Covered |
|---------------------------|-------------------|
| `test_payment_service.py` | TC-PAY-01 to TC-PAY-07 |
| `test_otp_service.py`     | TC-OTP-01 to TC-OTP-06 |
| `test_monitoring_agent/`  | TC-TMA-01 to TC-TMA-05 |
| `test_pattern_agent/`     | TC-PRA-01 to TC-PRA-05 |
| `test_raa/`               | TC-RAA-01 to TC-RAA-05 |
| `test_aba/`               | TC-ABA-01 to TC-ABA-05 |

## 🐛 Known Issues (from Manual Testing)

### Issue 1: Balance Validation Bug (TC-PAY-06)
**Status:** ❌ TEST FAILS
**File:** `et_service/payment_service.py:77`
**Test:** `test_insufficient_balance_edge_case`

**Bug:**
```python
# Current (WRONG):
if current_balance < (amount - 0.01):
    raise ValueError("Insufficient balance")

# Fixed:
if current_balance + 0.01 < amount:
    raise ValueError("Insufficient balance")
```

**After fixing, this test should PASS.**

### Issue 2: OTP Resend Rate Limiting (TC-OTP-04)
**Status:** ⚠️ NOT IMPLEMENTED
**File:** `et_api/payment_routes.py:260-294`

Need to add:
1. `resend_count` column to `otp_tokens` table
2. Rate limit check in `/payment/resend-otp` endpoint
3. Unit test: `test_resend_otp_rate_limiting()`

## 🔄 CI/CD Integration

### GitHub Actions Example

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt -r requirements-test.txt
      - run: pytest --cov --cov-report=xml
      - uses: codecov/codecov-action@v3
```

## 📊 Coverage Report Example

After running with coverage:

```bash
pytest --cov=et_service --cov-report=term-missing
```

Output:
```
Name                                      Stmts   Miss  Cover   Missing
-----------------------------------------------------------------------
et_service/payment_service.py                71      2    97%   77-78
et_service/otp_service.py                    42      0   100%
et_service/monitoring_agent/agent.py        198     15    92%
-----------------------------------------------------------------------
TOTAL                                      1523    112    93%
```

## 🎓 Writing New Tests

### Example: Testing a New DAO Function

```python
# tests/unit/test_payment_dao.py

import pytest
from unittest.mock import patch, MagicMock

class TestPaymentDAO:
    @patch('db.get_db_connection')
    def test_get_payment_by_id(self, mock_conn):
        # Setup
        mock_cursor = MagicMock()
        mock_conn.return_value.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = {
            'payment_id': 'PAY123',
            'amount': 1000.00,
            'status': 'COMPLETED'
        }

        # Execute
        from et_dao.payment_dao import get_payment_by_id
        result = get_payment_by_id('PAY123')

        # Assert
        assert result['payment_id'] == 'PAY123'
        assert result['status'] == 'COMPLETED'
        mock_cursor.execute.assert_called_once()
```

## 🆘 Troubleshooting

### Issue: Tests Can't Find Modules
```bash
# Solution: Install package in editable mode
pip install -e .
```

### Issue: ChromaDB Import Errors
```bash
# Solution: Ensure ChromaDB is installed
pip install chromadb
```

### Issue: Tests Hang
**Cause:** Background polling threads not disabled
**Solution:** Use `disable_agent_pollers` fixture in `conftest.py`

### Issue: MySQL Connection Errors
**Cause:** Tests attempting real DB connection
**Solution:** Ensure `mock_get_db_connection` fixture is active

## 📚 Additional Resources

- [pytest Documentation](https://docs.pytest.org/)
- [unittest.mock Guide](https://docs.python.org/3/library/unittest.mock.html)
- [Coverage.py](https://coverage.readthedocs.io/)

## ✅ Pre-Commit Checklist

Before committing code:

```bash
# 1. Run all tests
pytest

# 2. Check coverage (aim for >90%)
pytest --cov --cov-report=term-missing

# 3. Run only affected tests
pytest -k "payment"

# 4. Verify critical tests pass
pytest tests/unit/test_payment_service.py::TestProcessPayment::test_insufficient_balance_edge_case
```

## 🎯 Next Steps

1. **Implement remaining unit tests** for PRA, RAA, ABA components
2. **Add integration tests** for full pipeline (TMA → PRA → RAA → ABA)
3. **Fix TC-PAY-06 bug** and verify test passes
4. **Implement TC-OTP-04 rate limiting** and add tests
5. **Set up CI/CD** with automated test runs
6. **Achieve 90%+ coverage** across all critical components

---

**Questions?** Refer to inline comments in test files or check `conftest.py` for fixture documentation.
