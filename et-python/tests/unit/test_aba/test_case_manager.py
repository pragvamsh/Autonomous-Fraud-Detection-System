"""
test_case_manager.py
─────────────────────
Unit tests for ABA case_manager module.

Tests:
  - Fraud case creation for BLOCK verdict
  - No case creation for other verdicts
  - Case ID format
  - Case priority determination
"""

import unittest
from unittest.mock import patch, MagicMock


class TestCreateFraudCase(unittest.TestCase):
    """Tests for create_fraud_case function."""

    @patch('et_service.aba.case_manager.save_fraud_case')
    def test_block_verdict_creates_fraud_case(self, mock_save):
        """BLOCK verdict creates fraud case."""
        from et_service.aba.case_manager import create_fraud_case

        mock_save.return_value = 'CASE-20260321-A1B2C3D4'

        payload = {
            'raa_verdict': 'BLOCK',
            'final_raa_score': 85,
            'alert_id': 1001,
            'customer_id': 'C12345',
            'typology_code': 'TY-03',
        }

        with patch('builtins.print'):
            result = create_fraud_case(payload, 'PKG123')

        self.assertTrue(result['case_created'])
        self.assertIsNotNone(result['case_id'])
        mock_save.assert_called_once()

    @patch('et_service.aba.case_manager.save_fraud_case')
    def test_alert_verdict_no_case_created(self, mock_save):
        """ALERT verdict does not create fraud case."""
        from et_service.aba.case_manager import create_fraud_case

        payload = {
            'raa_verdict': 'ALERT',
            'final_raa_score': 65,
            'alert_id': 1001,
            'customer_id': 'C12345',
        }

        result = create_fraud_case(payload, 'PKG123')

        self.assertFalse(result['case_created'])
        self.assertEqual(result['reason'], 'Not BLOCK verdict')
        mock_save.assert_not_called()

    @patch('et_service.aba.case_manager.save_fraud_case')
    def test_flag_verdict_no_case_created(self, mock_save):
        """FLAG verdict does not create fraud case."""
        from et_service.aba.case_manager import create_fraud_case

        payload = {
            'raa_verdict': 'FLAG',
            'final_raa_score': 40,
            'alert_id': 1001,
            'customer_id': 'C12345',
        }

        result = create_fraud_case(payload, 'PKG123')

        self.assertFalse(result['case_created'])
        mock_save.assert_not_called()


class TestDeterminePriority(unittest.TestCase):
    """Tests for _determine_priority function."""

    def test_p1_high_score_high_risk_typology(self):
        """Score >= 90 + high-risk typology = P1."""
        from et_service.aba.case_manager import _determine_priority

        # TY-19 (Account Takeover) is in HIGH_RISK_TYPOLOGIES
        priority = _determine_priority(95, 'TY-19')

        self.assertEqual(priority, 'P1')

    def test_p2_block_score_no_high_risk_typology(self):
        """Score 76-89 = P2."""
        from et_service.aba.case_manager import _determine_priority

        priority = _determine_priority(82, None)

        self.assertEqual(priority, 'P2')

    def test_p3_below_block_threshold(self):
        """Score < 76 = P3."""
        from et_service.aba.case_manager import _determine_priority

        priority = _determine_priority(70, 'TY-03')

        self.assertEqual(priority, 'P3')


class TestQueueRegulatoryFilings(unittest.TestCase):
    """Tests for queue_regulatory_filings function."""

    @patch('et_service.aba.case_manager.save_regulatory_filing')
    def test_ctr_auto_filed_when_flag_true(self, mock_save):
        """CTR is auto-filed when ctr_flag=True."""
        from et_service.aba.case_manager import queue_regulatory_filings

        mock_save.return_value = 'CTR_001'

        payload = {
            'ctr_flag': True,
            'str_required': False,
            'customer_id': 'C12345',
            'alert_id': 1001,
            'amount': 1_500_000,
        }

        with patch('builtins.print'):
            result = queue_regulatory_filings(payload)

        self.assertTrue(result['ctr_filed'])
        self.assertIsNotNone(result['ctr_filing_id'])

    @patch('et_service.aba.case_manager.save_regulatory_filing')
    def test_str_queued_pending_approval(self, mock_save):
        """STR is queued with PENDING_APPROVAL status."""
        from et_service.aba.case_manager import queue_regulatory_filings

        mock_save.return_value = 'STR_001'

        payload = {
            'ctr_flag': False,
            'str_required': True,
            'str_draft': {'form': 'FIU-IND STR'},
            'customer_id': 'C12345',
            'alert_id': 1001,
            'amount': 50_000,
            'investigation_note': 'Suspicious activity',
        }

        with patch('builtins.print'):
            result = queue_regulatory_filings(payload)

        self.assertTrue(result['str_queued'])
        self.assertIsNotNone(result['str_filing_id'])

        # Verify STR has PENDING_APPROVAL status
        call_args = mock_save.call_args[0][0]
        self.assertEqual(call_args['status'], 'PENDING_APPROVAL')


class TestBuildEvidencePack(unittest.TestCase):
    """Tests for _build_evidence_pack function."""

    def test_evidence_pack_contains_all_fields(self):
        """Evidence pack contains all required fields."""
        from et_service.aba.case_manager import _build_evidence_pack

        payload = {
            'tma_score': 65,
            'pra_verdict': 'ESCALATE',
            'pattern_score': 70,
            'raa_verdict': 'BLOCK',
            'final_raa_score': 85,
            'typology_code': 'TY-03',
            'urgency_multiplier': 1.5,
            'customer_tier': 'T2',
            'dim_scores': {'D1': 50},
            'rag_multipliers': {'pattern_mult': 1.5},
            'all_citations': [{'source': 'L1'}],
            'investigation_note': 'Test',
            'str_required': True,
            'ctr_flag': False,
            'str_draft': None,
            'timestamp': '2026-03-21T12:00:00',
        }

        evidence = _build_evidence_pack(payload)

        # All key fields should be present
        self.assertIn('tma_score', evidence)
        self.assertIn('pra_verdict', evidence)
        self.assertIn('raa_verdict', evidence)
        self.assertIn('typology_code', evidence)
        self.assertIn('all_citations', evidence)


if __name__ == '__main__':
    unittest.main()
