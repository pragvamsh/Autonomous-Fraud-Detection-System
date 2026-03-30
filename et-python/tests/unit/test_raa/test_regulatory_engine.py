"""
test_regulatory_engine.py
──────────────────────────
Unit tests for RAA regulatory_engine module.

Tests:
  - CTR single transaction threshold
  - CTR 24h aggregate threshold
  - STR structuring typology triggers
  - STR CRITICAL pra_verdict mandatory
  - STR L3 obligation triggers
  - STR draft building
  - Database error handling
"""

import unittest
from unittest.mock import patch, MagicMock


class TestCheckRegulatory(unittest.TestCase):
    """Tests for check_regulatory function."""

    @patch('et_service.raa.regulatory_engine.get_24h_customer_total')
    def test_ctr_single_txn_above_threshold_sets_flag(self, mock_24h):
        """Single transaction >= CTR threshold sets ctr_flag=True."""
        from et_service.raa.regulatory_engine import check_regulatory

        mock_24h.return_value = 0.0

        scores = {'final_raa_score': 50}
        rag = {
            'ctr_single_threshold': 1_000_000,
            'ctr_aggregate_threshold': 500_000,
            'str_obligation': None,
            'l3_typology_doc': None,
            'l2_citations': [],
            'l1_citations': [],
            'l3_citations': [],
        }
        data = {
            'customer_id': 'C12345',
            'pra_verdict': 'MAINTAIN',
            'typology_code': None,
            '_amount': 1_100_000,  # >= 1_000_000 threshold
            'feature_snapshot': {},
        }

        with patch('builtins.print'):
            result = check_regulatory(scores, rag, data)

        self.assertTrue(result['ctr_flag'])
        self.assertIn('single_txn_threshold', result['ctr_reason'])

    @patch('et_service.raa.regulatory_engine.get_24h_customer_total')
    def test_ctr_single_txn_below_threshold_no_flag(self, mock_24h):
        """Single transaction < CTR threshold - no flag."""
        from et_service.raa.regulatory_engine import check_regulatory

        mock_24h.return_value = 0.0

        scores = {'final_raa_score': 50}
        rag = {
            'ctr_single_threshold': 1_000_000,
            'ctr_aggregate_threshold': 500_000,
            'str_obligation': None,
            'l3_typology_doc': None,
            'l2_citations': [],
            'l1_citations': [],
            'l3_citations': [],
        }
        data = {
            'customer_id': 'C12345',
            'pra_verdict': 'MAINTAIN',
            'typology_code': None,
            '_amount': 100_000,  # < both single and aggregate thresholds
            'feature_snapshot': {},
        }

        with patch('builtins.print'):
            result = check_regulatory(scores, rag, data)

        self.assertFalse(result['ctr_flag'])

    @patch('et_service.raa.regulatory_engine.get_24h_customer_total')
    def test_ctr_24h_aggregate_triggers(self, mock_24h):
        """24h aggregate >= threshold triggers CTR."""
        from et_service.raa.regulatory_engine import check_regulatory

        mock_24h.return_value = 450_000  # Prior 24h total

        scores = {'final_raa_score': 50}
        rag = {
            'ctr_single_threshold': 1_000_000,
            'ctr_aggregate_threshold': 500_000,
            'str_obligation': None,
            'l3_typology_doc': None,
            'l2_citations': [],
            'l1_citations': [],
            'l3_citations': [],
        }
        data = {
            'customer_id': 'C12345',
            'pra_verdict': 'MAINTAIN',
            'typology_code': None,
            '_amount': 100_000,  # 450k + 100k = 550k >= 500k threshold
            'feature_snapshot': {},
        }

        with patch('builtins.print'):
            result = check_regulatory(scores, rag, data)

        self.assertTrue(result['ctr_flag'])
        self.assertIn('aggregate_24h_threshold', result['ctr_reason'])

    @patch('et_service.raa.regulatory_engine.get_24h_customer_total')
    def test_str_structuring_typology_triggers(self, mock_24h):
        """Structuring typology (TY-03) + score > 40 triggers STR."""
        from et_service.raa.regulatory_engine import check_regulatory

        mock_24h.return_value = 0.0

        scores = {'final_raa_score': 50}  # > 40
        rag = {
            'ctr_single_threshold': 1_000_000,
            'ctr_aggregate_threshold': 500_000,
            'str_obligation': None,
            'l3_typology_doc': {'description': 'Structuring', 'decisive_signals': 'Multiple small txns'},
            'l2_citations': [],
            'l1_citations': [],
            'l3_citations': [],
        }
        data = {
            'customer_id': 'C12345',
            'pra_verdict': 'ESCALATE',
            'typology_code': 'TY-03',  # Structuring
            '_amount': 50_000,
            'feature_snapshot': {},
        }

        with patch('builtins.print'):
            result = check_regulatory(scores, rag, data)

        self.assertTrue(result['str_required'])

    @patch('et_service.raa.regulatory_engine.get_24h_customer_total')
    def test_str_requires_score_above_40(self, mock_24h):
        """Structuring typology but score <= 40 - no STR."""
        from et_service.raa.regulatory_engine import check_regulatory

        mock_24h.return_value = 0.0

        scores = {'final_raa_score': 35}  # <= 40
        rag = {
            'ctr_single_threshold': 1_000_000,
            'ctr_aggregate_threshold': 500_000,
            'str_obligation': None,
            'l3_typology_doc': None,
            'l2_citations': [],
            'l1_citations': [],
            'l3_citations': [],
        }
        data = {
            'customer_id': 'C12345',
            'pra_verdict': 'DE-ESCALATE',
            'typology_code': 'TY-03',
            '_amount': 50_000,
            'feature_snapshot': {},
        }

        with patch('builtins.print'):
            result = check_regulatory(scores, rag, data)

        self.assertFalse(result['str_required'])

    @patch('et_service.raa.regulatory_engine.get_24h_customer_total')
    def test_str_critical_pra_verdict_mandatory(self, mock_24h):
        """CRITICAL pra_verdict always triggers STR."""
        from et_service.raa.regulatory_engine import check_regulatory

        mock_24h.return_value = 0.0

        scores = {'final_raa_score': 30}  # Even low score
        rag = {
            'ctr_single_threshold': 1_000_000,
            'ctr_aggregate_threshold': 500_000,
            'str_obligation': None,
            'l3_typology_doc': None,
            'l2_citations': [],
            'l1_citations': [],
            'l3_citations': [],
        }
        data = {
            'customer_id': 'C12345',
            'pra_verdict': 'CRITICAL',  # CRITICAL triggers STR
            'typology_code': None,
            '_amount': 10_000,
            'feature_snapshot': {},
        }

        with patch('builtins.print'):
            result = check_regulatory(scores, rag, data)

        self.assertTrue(result['str_required'])

    @patch('et_service.raa.regulatory_engine.get_24h_customer_total')
    def test_str_l3_obligation_triggers(self, mock_24h):
        """L3 str_obligation='STR' + amount > 5% of CTR threshold triggers STR."""
        from et_service.raa.regulatory_engine import check_regulatory

        mock_24h.return_value = 0.0

        scores = {'final_raa_score': 50}
        rag = {
            'ctr_single_threshold': 1_000_000,
            'ctr_aggregate_threshold': 500_000,
            'str_obligation': 'STR',  # L3 says STR required
            'l3_typology_doc': None,
            'l2_citations': [],
            'l1_citations': [],
            'l3_citations': [],
        }
        data = {
            'customer_id': 'C12345',
            'pra_verdict': 'MAINTAIN',
            'typology_code': None,
            '_amount': 60_000,  # > 5% of 1M = 50k
            'feature_snapshot': {},
        }

        with patch('builtins.print'):
            result = check_regulatory(scores, rag, data)

        self.assertTrue(result['str_required'])

    @patch('et_service.raa.regulatory_engine.get_24h_customer_total')
    def test_str_draft_built_when_required(self, mock_24h):
        """STR draft is built when str_required=True."""
        from et_service.raa.regulatory_engine import check_regulatory

        mock_24h.return_value = 0.0

        scores = {'final_raa_score': 70, 'raa_verdict': 'ALERT'}
        rag = {
            'ctr_single_threshold': 1_000_000,
            'ctr_aggregate_threshold': 500_000,
            'str_obligation': None,
            'l3_typology_doc': {'description': 'Test', 'decisive_signals': 'Signal'},
            'l2_citations': [],
            'l1_citations': [],
            'l3_citations': [],
        }
        data = {
            'customer_id': 'C12345',
            'pra_verdict': 'CRITICAL',
            'typology_code': 'TY-03',
            '_amount': 50_000,
            'feature_snapshot': {},
            'transaction_id': 'TXN123',
            'risk_score': 70,
            'pattern_score': 65,
        }

        with patch('builtins.print'):
            result = check_regulatory(scores, rag, data)

        self.assertTrue(result['str_required'])
        self.assertIsNotNone(result['str_draft'])

        # Check draft structure
        draft = result['str_draft']
        self.assertIn('form', draft)
        self.assertIn('section', draft)
        self.assertIn('status', draft)
        self.assertIn('DRAFT', draft['status'])

    @patch('et_service.raa.regulatory_engine.get_24h_customer_total')
    def test_str_never_auto_files(self, mock_24h):
        """STR is never auto-filed - always DRAFT status."""
        from et_service.raa.regulatory_engine import check_regulatory

        mock_24h.return_value = 0.0

        scores = {'final_raa_score': 85, 'raa_verdict': 'BLOCK'}
        rag = {
            'ctr_single_threshold': 1_000_000,
            'ctr_aggregate_threshold': 500_000,
            'str_obligation': 'STR',
            'l3_typology_doc': None,
            'l2_citations': [],
            'l1_citations': [],
            'l3_citations': [],
        }
        data = {
            'customer_id': 'C12345',
            'pra_verdict': 'CRITICAL',
            'typology_code': 'TY-03',
            '_amount': 100_000,
            'feature_snapshot': {},
        }

        with patch('builtins.print'):
            result = check_regulatory(scores, rag, data)

        # STR should be draft only, never auto-filed
        if result['str_draft']:
            self.assertIn('PENDING', result['str_draft']['status'])

    @patch('et_service.raa.regulatory_engine.get_24h_customer_total')
    def test_24h_lookup_error_does_not_crash(self, mock_24h):
        """24h lookup error continues - ctr_flag=False."""
        from et_service.raa.regulatory_engine import check_regulatory

        mock_24h.side_effect = Exception("Database error")

        scores = {'final_raa_score': 50}
        rag = {
            'ctr_single_threshold': 1_000_000,
            'ctr_aggregate_threshold': 500_000,
            'str_obligation': None,
            'l3_typology_doc': None,
            'l2_citations': [],
            'l1_citations': [],
            'l3_citations': [],
        }
        data = {
            'customer_id': 'C12345',
            'pra_verdict': 'MAINTAIN',
            'typology_code': None,
            '_amount': 100_000,  # Below single threshold
            'feature_snapshot': {},
        }

        with patch('builtins.print'):
            result = check_regulatory(scores, rag, data)

        # Should not crash, ctr_flag should be False
        self.assertFalse(result['ctr_flag'])


class TestBuildStrDraft(unittest.TestCase):
    """Tests for build_str_draft function."""

    def test_draft_contains_required_fields(self):
        """STR draft contains all required fields."""
        from et_service.raa.regulatory_engine import build_str_draft

        alert_row = {
            'transaction_id': 'TXN123',
            'customer_id': 'C12345',
            'typology_code': 'TY-03',
            'risk_score': 70,
            'pra_verdict': 'ESCALATE',
            'pattern_score': 65,
        }
        l3_doc = {'description': 'Structuring', 'decisive_signals': 'Multiple txns'}
        citations = [{'source': 'L1_regulatory', 'text': 'PMLA section'}]
        scores = {'final_raa_score': 70, 'raa_verdict': 'ALERT'}

        draft = build_str_draft(alert_row, l3_doc, citations, scores)

        # Required fields
        self.assertIn('form', draft)
        self.assertIn('section', draft)
        self.assertIn('status', draft)
        self.assertIn('transaction_id', draft)
        self.assertIn('customer_id', draft)
        self.assertIn('typology_code', draft)


if __name__ == '__main__':
    unittest.main()
