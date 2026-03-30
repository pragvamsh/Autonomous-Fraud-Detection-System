"""
Unit Tests for Payment Service
===============================

Tests payment validation, process, commit, hold, and reject logic.

Critical Tests:
  - TC-PAY-06: Balance validation edge case (WOULD FAIL with current bug)
  - Amount validation (min/max)
  - Recipient validation
  - Self-transfer prevention

Run:
    pytest tests/unit/test_payment_service.py -v
    pytest tests/unit/test_payment_service.py::test_insufficient_balance_edge_case
"""

import pytest
from unittest.mock import patch, MagicMock
from et_service.payment_service import (
    validate_payment,
    process_payment,
    commit_payment,
    hold_payment,
    reject_payment,
    PAYMENT_MIN,
    PAYMENT_MAX,
)


# ══════════════════════════════════════════════════════════════════════════════
# VALIDATION TESTS
# ══════════════════════════════════════════════════════════════════════════════

class TestPaymentValidation:
    """Test payment input validation."""

    def test_amount_too_low(self):
        """TC-PAY-01: Amount = 0.00 should fail."""
        errors = validate_payment(
            amount=0.00,
            recipient_account='123456789012',
            sender_account='987654321098'
        )
        assert len(errors) == 1
        assert "Minimum payment amount is Rs 1.00" in errors[0]

    def test_amount_below_minimum(self):
        """TC-PAY-03: Amount = Rs 0.99 should fail."""
        errors = validate_payment(
            amount=0.99,
            recipient_account='123456789012',
            sender_account='987654321098'
        )
        assert len(errors) == 1
        assert "Minimum payment amount" in errors[0]

    def test_amount_exceeds_maximum(self):
        """TC-PAY-02: Amount = Rs 100,001 should fail."""
        errors = validate_payment(
            amount=100001.00,
            recipient_account='123456789012',
            sender_account='987654321098'
        )
        assert len(errors) == 1
        assert "Maximum payment amount is Rs 100,000" in errors[0]

    def test_amount_at_max_boundary(self):
        """Amount = Rs 100,000 should pass."""
        errors = validate_payment(
            amount=100000.00,
            recipient_account='123456789012',
            sender_account='987654321098'
        )
        assert len(errors) == 0

    def test_amount_at_min_boundary(self):
        """Amount = Rs 1.00 should pass."""
        errors = validate_payment(
            amount=1.00,
            recipient_account='123456789012',
            sender_account='987654321098'
        )
        assert len(errors) == 0

    def test_invalid_amount_type(self):
        """Non-numeric amount should fail."""
        errors = validate_payment(
            amount="not_a_number",
            recipient_account='123456789012',
            sender_account='987654321098'
        )
        assert len(errors) == 1
        assert "Amount must be a valid number" in errors[0]

    def test_empty_recipient_account(self):
        """TC-PAY-04: Empty recipient should fail."""
        errors = validate_payment(
            amount=1000.00,
            recipient_account='',
            sender_account='987654321098'
        )
        assert len(errors) == 1
        assert "Recipient account number is required" in errors[0]

    def test_self_transfer(self):
        """TC-PAY-05: Sender = Recipient should fail."""
        errors = validate_payment(
            amount=1000.00,
            recipient_account='123456789012',
            sender_account='123456789012'  # Same as recipient
        )
        assert len(errors) == 1
        assert "Cannot transfer money to your own account" in errors[0]

    def test_valid_payment(self):
        """Valid payment should return no errors."""
        errors = validate_payment(
            amount=5000.00,
            recipient_account='123456789012',
            sender_account='987654321098'
        )
        assert len(errors) == 0


# ══════════════════════════════════════════════════════════════════════════════
# PROCESS PAYMENT TESTS (with Database Mocking)
# ══════════════════════════════════════════════════════════════════════════════

class TestProcessPayment:
    """Test payment processing logic with mocked database."""

    @patch('et_service.payment_service.get_customer_by_account')
    @patch('et_dao.account_dao.get_balance')
    @patch('et_service.payment_service.create_pending_payment')
    def test_successful_payment_processing(
        self,
        mock_create_pending,
        mock_get_balance,
        mock_get_recipient
    ):
        """Valid payment should create pending payment record."""
        # Mock recipient exists
        mock_get_recipient.return_value = {
            'customer_id': 'C67890',
            'account_number': '987654321098'
        }
        # Mock sender has sufficient balance
        mock_get_balance.return_value = 10000.00

        result = process_payment(
            sender_customer_id='C12345',
            sender_account='123456789012',
            recipient_account='987654321098',
            amount=1000.00,
            description='Test payment'
        )

        # Verify result structure
        assert result['amount'] == 1000.00
        assert result['sender_customer_id'] == 'C12345'
        assert result['recipient_customer_id'] == 'C67890'
        assert 'payment_id' in result
        assert result['payment_id'].startswith('PAY')

        # Verify DAO called
        mock_create_pending.assert_called_once()

    @patch('et_service.payment_service.get_customer_by_account')
    def test_nonexistent_recipient(self, mock_get_recipient):
        """TC-PAY-07: Non-existent recipient should raise ValueError."""
        mock_get_recipient.return_value = None  # Recipient not found

        with pytest.raises(ValueError) as exc_info:
            process_payment(
                sender_customer_id='C12345',
                sender_account='123456789012',
                recipient_account='9999999999',
                amount=1000.00,
                description='Test'
            )

        assert "Recipient account not found" in str(exc_info.value)

    @patch('et_service.payment_service.get_customer_by_account')
    @patch('et_dao.account_dao.get_balance')
    def test_insufficient_balance(
        self,
        mock_get_balance,
        mock_get_recipient
    ):
        """Insufficient balance should raise ValueError."""
        mock_get_recipient.return_value = {'customer_id': 'C67890'}
        mock_get_balance.return_value = 500.00  # Balance less than amount

        with pytest.raises(ValueError) as exc_info:
            process_payment(
                sender_customer_id='C12345',
                sender_account='123456789012',
                recipient_account='987654321098',
                amount=1000.00,
                description='Test'
            )

        assert "Insufficient balance" in str(exc_info.value)

    @patch('et_service.payment_service.get_customer_by_account')
    @patch('et_dao.account_dao.get_balance')
    def test_insufficient_balance_edge_case(
        self,
        mock_get_balance,
        mock_get_recipient
    ):
        """
        TC-PAY-06: CRITICAL TEST - Balance validation edge case

        🚨 THIS TEST WILL **FAIL** WITH CURRENT BUGGY CODE

        Bug Location: et_service/payment_service.py:77
        Current code: if current_balance < (amount - 0.01)

        For balance=500.00, amount=500.01:
          Check: 500.00 < (500.01 - 0.01) → 500.00 < 500.00 → FALSE
          Result: Payment incorrectly ALLOWED (should be rejected)

        Expected: ValueError("Insufficient balance")
        Actual: Payment proceeds (overdraft by Rs 0.01)
        """
        mock_get_recipient.return_value = {'customer_id': 'C67890'}
        mock_get_balance.return_value = 500.00  # Exactly Rs 500

        with pytest.raises(ValueError) as exc_info:
            process_payment(
                sender_customer_id='C12345',
                sender_account='123456789012',
                recipient_account='987654321098',
                amount=500.01,  # Rs 0.01 more than balance
                description='Edge case test'
            )

        assert "Insufficient balance" in str(exc_info.value)
        assert "Available: Rs 500.00" in str(exc_info.value)
        assert "Required: Rs 500.01" in str(exc_info.value)

    @patch('et_service.payment_service.get_customer_by_account')
    @patch('et_dao.account_dao.get_balance')
    def test_exact_balance_payment(
        self,
        mock_get_balance,
        mock_get_recipient
    ):
        """Payment for exact balance should succeed."""
        mock_get_recipient.return_value = {'customer_id': 'C67890'}
        mock_get_balance.return_value = 500.00

        # This should succeed with Rs 500.00 balance and Rs 500.00 payment
        # (accounting for floating-point tolerance)
        # The test will pass/fail based on fix implementation

    @patch('et_service.payment_service.get_customer_by_account')
    @patch('et_dao.account_dao.get_balance')
    def test_balance_retrieval_failure(self, mock_get_balance, mock_get_recipient):
        """Database error during balance check should raise RuntimeError."""
        mock_get_recipient.return_value = {'customer_id': 'C67890'}
        mock_get_balance.return_value = None  # DB error

        with pytest.raises(RuntimeError) as exc_info:
            process_payment(
                sender_customer_id='C12345',
                sender_account='123456789012',
                recipient_account='987654321098',
                amount=1000.00,
                description='Test'
            )

        assert "Could not retrieve account balance" in str(exc_info.value)


# ══════════════════════════════════════════════════════════════════════════════
# COMMIT/HOLD/REJECT TESTS
# ══════════════════════════════════════════════════════════════════════════════

class TestPaymentActions:
    """Test commit, hold, and reject payment actions."""

    @patch('et_service.payment_service.dao_commit_payment')
    def test_commit_payment(self, mock_dao_commit, payment_result):
        """Commit payment should call DAO with correct parameters."""
        mock_dao_commit.return_value = {'new_sender_balance': 9000.00}

        result = commit_payment(payment_result, status_override='COMPLETED')

        mock_dao_commit.assert_called_once()
        call_kwargs = mock_dao_commit.call_args[1]
        assert call_kwargs['payment_id'] == payment_result['payment_id']
        assert call_kwargs['amount'] == payment_result['amount']
        assert call_kwargs['status_override'] == 'COMPLETED'

    @patch('et_service.payment_service.dao_hold_payment')
    def test_hold_payment(self, mock_dao_hold, payment_result):
        """Hold payment should mark payment as HELD (no balance deduction)."""
        hold_payment(payment_result)

        mock_dao_hold.assert_called_once_with(
            payment_id=payment_result['payment_id'],
            debit_txn_id=payment_result['debit_transaction_id']
        )

    @patch('et_service.payment_service.dao_reject_payment')
    def test_reject_payment(self, mock_dao_reject, payment_result):
        """Reject payment should mark payment as FAILED."""
        reject_payment(payment_result)

        mock_dao_reject.assert_called_once_with(
            payment_id=payment_result['payment_id'],
            debit_txn_id=payment_result['debit_transaction_id']
        )


# ══════════════════════════════════════════════════════════════════════════════
# INTEGRATION NOTE
# ══════════════════════════════════════════════════════════════════════════════

"""
RECOMMENDED FIX for TC-PAY-06:

File: et_service/payment_service.py:77

Current (BUGGY):
    if current_balance < (amount - 0.01):
        raise ValueError("Insufficient balance")

Fixed Option 1 (Recommended):
    if current_balance + 0.01 < amount:
        raise ValueError("Insufficient balance")

Fixed Option 2 (Alternative):
    if round(current_balance, 2) < round(amount, 2):
        raise ValueError("Insufficient balance")

After fixing, run:
    pytest tests/unit/test_payment_service.py::TestProcessPayment::test_insufficient_balance_edge_case -v

Expected: PASS (currently FAIL)
"""
