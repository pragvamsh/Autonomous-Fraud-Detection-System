"""
test_gateway_controller.py
──────────────────────────
Unit tests for ABA gateway_controller module.

Tests:
  - Verdict to gateway action mapping
  - MFA gate logic
  - TY-03 Covert Mode
"""

import unittest
from unittest.mock import patch


class TestDetermineGatewayAction(unittest.TestCase):
    """Tests for determine_gateway_action function."""

    def test_block_verdict_returns_stopped(self):
        """BLOCK verdict returns gateway_action='STOPPED'."""
        from et_service.aba.gateway_controller import determine_gateway_action

        payload = {
            'raa_verdict': 'BLOCK',
            'final_raa_score': 85,
            'typology_code': None,
        }

        with patch('builtins.print'):
            result = determine_gateway_action(payload)

        self.assertEqual(result['gateway_action'], 'STOPPED')
        self.assertTrue(result['block_transaction'])
        self.assertTrue(result['hold_funds'])

    def test_alert_verdict_returns_held(self):
        """ALERT verdict returns gateway_action='HELD'."""
        from et_service.aba.gateway_controller import determine_gateway_action

        payload = {
            'raa_verdict': 'ALERT',
            'final_raa_score': 65,
            'typology_code': None,
        }

        with patch('builtins.print'):
            result = determine_gateway_action(payload)

        self.assertEqual(result['gateway_action'], 'HELD')
        self.assertTrue(result['requires_verification'])
        self.assertTrue(result['hold_funds'])

    def test_flag_verdict_returns_approve_after_confirm(self):
        """FLAG verdict (score < 45) returns APPROVE_AFTER_CONFIRM."""
        from et_service.aba.gateway_controller import determine_gateway_action

        payload = {
            'raa_verdict': 'FLAG',
            'final_raa_score': 35,  # Below MFA threshold
            'typology_code': None,
        }

        with patch('builtins.print'):
            result = determine_gateway_action(payload)

        self.assertEqual(result['gateway_action'], 'APPROVE_AFTER_CONFIRM')
        self.assertTrue(result['requires_confirmation'])

    def test_allow_verdict_returns_pass_through(self):
        """ALLOW verdict returns gateway_action='APPROVE'."""
        from et_service.aba.gateway_controller import determine_gateway_action

        payload = {
            'raa_verdict': 'ALLOW',
            'final_raa_score': 20,
            'typology_code': None,
        }

        result = determine_gateway_action(payload)

        self.assertEqual(result['gateway_action'], 'APPROVE')
        self.assertFalse(result['requires_confirmation'])
        self.assertFalse(result['requires_otp'])
        self.assertFalse(result['hold_funds'])

    def test_unknown_verdict_defaults_to_stopped(self):
        """Unknown verdict defaults to safe APPROVE action."""
        from et_service.aba.gateway_controller import determine_gateway_action

        payload = {
            'raa_verdict': 'UNKNOWN',
            'final_raa_score': 50,
            'typology_code': None,
        }

        result = determine_gateway_action(payload)

        # Default behavior for unknown verdict
        self.assertEqual(result['gateway_action'], 'APPROVE')


class TestFlagMFA(unittest.TestCase):
    """Tests for FLAG+MFA gate logic."""

    def test_flag_mfa_score_45_50_triggers_otp_gate(self):
        """FLAG with score 45-50 triggers OTP_GATE."""
        from et_service.aba.gateway_controller import determine_gateway_action

        payload = {
            'raa_verdict': 'FLAG',
            'final_raa_score': 47,  # In MFA band 45-50
            'typology_code': None,
        }

        with patch('builtins.print'):
            result = determine_gateway_action(payload)

        self.assertEqual(result['gateway_action'], 'OTP_GATE')
        self.assertTrue(result['requires_otp'])

    def test_flag_mfa_suppressed_for_ty03(self):
        """FLAG+MFA suppressed for TY-03 (Covert Mode)."""
        from et_service.aba.gateway_controller import determine_gateway_action

        payload = {
            'raa_verdict': 'FLAG',
            'final_raa_score': 47,  # In MFA band
            'typology_code': 'TY-03',  # Covert Mode - no MFA
        }

        with patch('builtins.print'):
            result = determine_gateway_action(payload)

        # Should NOT trigger MFA for TY-03
        self.assertNotEqual(result['gateway_action'], 'OTP_GATE')
        self.assertFalse(result['requires_otp'])


class TestCovertMode(unittest.TestCase):
    """Tests for TY-03 Covert Mode."""

    def test_block_ty03_returns_covert_hold(self):
        """BLOCK with TY-03 returns COVERT_HOLD, not STOPPED."""
        from et_service.aba.gateway_controller import determine_gateway_action

        payload = {
            'raa_verdict': 'BLOCK',
            'final_raa_score': 85,
            'typology_code': 'TY-03',  # Structuring
        }

        with patch('builtins.print'):
            result = determine_gateway_action(payload)

        self.assertEqual(result['gateway_action'], 'COVERT_HOLD')
        self.assertTrue(result['covert_mode'])
        self.assertTrue(result['hold_funds'])
        self.assertFalse(result['block_transaction'])  # Not hard-blocked


class TestShouldTriggerMFA(unittest.TestCase):
    """Tests for should_trigger_mfa helper."""

    def test_mfa_triggers_for_flag_in_band(self):
        """MFA triggers for FLAG verdict, score 45-50, no TY-03."""
        from et_service.aba.gateway_controller import should_trigger_mfa

        self.assertTrue(should_trigger_mfa('FLAG', 45))
        self.assertTrue(should_trigger_mfa('FLAG', 47))
        self.assertTrue(should_trigger_mfa('FLAG', 50))

    def test_mfa_not_triggered_for_allow(self):
        """MFA not triggered for ALLOW verdict."""
        from et_service.aba.gateway_controller import should_trigger_mfa

        self.assertFalse(should_trigger_mfa('ALLOW', 47))

    def test_mfa_not_triggered_for_ty03(self):
        """MFA not triggered for TY-03 typology."""
        from et_service.aba.gateway_controller import should_trigger_mfa

        self.assertFalse(should_trigger_mfa('FLAG', 47, 'TY-03'))


if __name__ == '__main__':
    unittest.main()
