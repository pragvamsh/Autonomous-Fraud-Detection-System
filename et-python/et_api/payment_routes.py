import threading
import time
from flask import Blueprint, request, jsonify, session
from et_service.auth_service import login_required
from et_service.payment_service import (
    validate_payment,
    process_payment,
    commit_payment,
    hold_payment,
    reject_payment,
    get_payment_transactions,
    get_held_payment,
)
from et_dao.auth_dao import find_customer_by_id

payment_bp = Blueprint('payment', __name__)


@payment_bp.route('/payment', methods=['POST'])
@login_required
def make_payment(customer_id):
    """
    POST /api/payment
    Body: { "recipient_account": "...", "amount": ..., "description": "..." }

    Flow:
      1. Validate input
      2. process_payment  — creates PENDING payment
      3. evaluate_transaction (TMA) — synchronous fraud scoring
      4. Act on score and verdict:
           ALLOW (0-25) / FLAG (26-44)  → commit immediately, fire PRA in background
           FLAG+MFA (45-50) / ALERT (51-75)  → hold payment, send OTP, return 202
                                               Frontend shows OTP screen. Customer submits to /payment/verify-otp.
           BLOCK (76-100)   → reject payment, return 403
      5. Return response to frontend

    [FIX] OTP gate now based on TMA SCORE (≥45), not just ALERT verdict.
    This ensures both FLAG+MFA (45-50) and ALERT (51-75) bands require OTP BEFORE payment commit.
    ABA no longer sends OTP — payment_routes is the single source of truth for OTP gates.
    """
    data = request.get_json(silent=True) or {}

    amount            = data.get('amount')
    recipient_account = str(data.get('recipient_account', '')).strip()
    description       = str(data.get('description', 'Payment')).strip() or 'Payment'

    # ── Get sender profile ────────────────────────────────────────────
    customer = find_customer_by_id(customer_id)
    if not customer:
        return jsonify({"message": "Customer not found."}), 404

    sender_account = customer['account_number']

    # ── Validate ──────────────────────────────────────────────────────
    errors = validate_payment(amount, recipient_account, sender_account)
    if errors:
        return jsonify({"errors": errors}), 400

    # ── Critical path — TMA + commit/hold/reject ──────────────────────
    from et_service.monitoring_agent.agent import evaluate_transaction

    try:
        # Step 1: Create PENDING payment record
        payment_result = process_payment(
            sender_customer_id=customer_id,
            sender_account=sender_account,
            recipient_account=recipient_account,
            amount=float(amount),
            description=description,
        )

        # Step 2: Run TMA synchronously
        tma_result = evaluate_transaction(payment_result)
        if tma_result is None:
            tma_result = {'decision': 'ALLOW', 'risk_score': None}

        tma_verdict = tma_result.get('decision', 'ALLOW')
        tma_score = float(tma_result.get('risk_score') or 0)

        # Step 3: Act on verdict and score
        # [FIX] OTP gate now based on SCORE (≥45), not just ALERT verdict
        # This covers both ALERT (51-75) and FLAG+MFA (45-50) bands
        if tma_verdict == 'BLOCK':
            reject_payment(payment_result)
            return jsonify({
                'message': 'Payment blocked by security policy.',
                'tma':     tma_result,
            }), 403

        elif tma_score >= 45:
            # ── OTP Gate: hold payment, send OTP, ask customer to verify ──
            # Triggered for scores 45+ (FLAG+MFA band 45-50 OR ALERT band 51-75)
            # Payment is NOT committed yet. Balance does not change.
            # Customer must verify via POST /api/payment/verify-otp.
            hold_payment(payment_result)

            # [FIX BUG-001] Propagate alert_id from TMA result to payment_result
            # before sending OTP — ABA account_controller needs it for logging.
            payment_result['fraud_alert_id'] = tma_result.get('alert_id')

            # Send OTP to customer
            _send_alert_otp(customer_id, payment_result)

            refreshed = find_customer_by_id(customer_id)
            payment_result['new_sender_balance'] = (
                refreshed['balance'] if refreshed else customer['balance']
            )

            # Return 202 — frontend must show OTP screen
            return jsonify({
                'status':              'verification_required',
                'payment_id':          payment_result['payment_id'],
                'amount':              payment_result['amount'],
                'recipient':           _mask_account(payment_result['recipient_account']),
                'current_balance':     payment_result.get('new_sender_balance', 0.0),
                'message':             'This transaction requires verification. '
                                       'Please enter the OTP sent to your registered mobile number.',
                'otp_timeout_seconds': 300,
                'tma':                 tma_result,
            }), 202

        elif tma_verdict in ('ALLOW', 'FLAG'):
            # ALLOW (score 0-25) or FLAG (score 26-44) — commit immediately
            status       = 'COMPLETED' if tma_verdict == 'ALLOW' else 'PENDING_REVIEW'
            final_result = commit_payment(payment_result, status_override=status)
            payment_result['new_sender_balance'] = final_result['new_sender_balance']

        else:
            # Unknown verdict — safe fallback: treat as ALLOW
            print(f"[PaymentRoute] WARN — unknown TMA verdict '{tma_verdict}', treating as ALLOW")
            final_result = commit_payment(payment_result, status_override='COMPLETED')
            payment_result['new_sender_balance'] = final_result['new_sender_balance']

    except ValueError as e:
        return jsonify({"message": str(e)}), 400
    except RuntimeError as e:
        import traceback
        print(f"[PaymentRoute] RuntimeError: {e}")
        traceback.print_exc()
        return jsonify({"message": "Payment failed due to a system error. Please try again."}), 500
    except Exception as e:
        import traceback
        print(f"[PaymentRoute] Unhandled exception: {e}")
        traceback.print_exc()
        return jsonify({"message": "Payment failed due to an internal error. Please try again."}), 500

    # ── Fire PRA in background (ALLOW/FLAG only — ALERT fires after OTP pass) ──
    _fire_pattern_agent(payment_result)

    return jsonify({
        "message":     "Payment processed.",
        "payment_id":  payment_result["payment_id"],
        "amount":      payment_result["amount"],
        "new_balance": payment_result.get("new_sender_balance", 0.0),
        "recipient":   _mask_account(payment_result["recipient_account"]),
        "tma":         tma_result,
    }), 200


# ── OTP Verification Route ─────────────────────────────────────────────────────

@payment_bp.route('/payment/verify-otp', methods=['POST'])
@login_required
def verify_payment_otp(customer_id):
    """
    POST /api/payment/verify-otp
    Body: { "payment_id": "...", "otp": "123456" }

    Called by frontend after customer enters OTP from the ALERT verification screen.

    Flow:
      OTP correct         → commit held payment, fire PRA, return 200
      OTP wrong (< 3)     → return 401 with attempts_remaining
      OTP wrong (= 3)     → reject payment, soft-lock account 30min, return 403
      OTP expired/missing → return 410 (timeout — customer must restart payment)
    """
    data       = request.get_json(silent=True) or {}
    payment_id = str(data.get('payment_id', '')).strip()
    otp_input  = str(data.get('otp', '')).strip()

    if not payment_id or not otp_input:
        return jsonify({"message": "payment_id and otp are required."}), 400

    try:
        from et_service.aba.account_controller import verify_fraud_mfa_otp
        from et_dao.aba_dao import (
            get_otp_attempt_count,
            increment_otp_attempts,
            reset_otp_attempts,
            set_soft_lock,
        )

        # Check if account is soft-locked from previous OTP failures
        if _is_soft_locked(customer_id):
            return jsonify({
                "message": "Account temporarily locked due to multiple failed verifications. "
                           "Please try again in 30 minutes or contact support.",
                "status":  "soft_locked",
            }), 403

        # Verify the OTP
        verify_result = verify_fraud_mfa_otp(customer_id, otp_input, payment_id)

        if verify_result.get('verified'):
            # ── OTP PASSED — commit the held payment ──────────────────
            reset_otp_attempts(customer_id)

            held_payment = get_held_payment(payment_id, customer_id)
            if not held_payment:
                return jsonify({
                    "message": "Payment session expired. Please initiate a new payment.",
                    "status":  "expired",
                }), 410

            final_result = commit_payment(held_payment, status_override='COMPLETED')
            _fire_pattern_agent(held_payment)

            print(f"[PaymentRoute] OTP verified — payment committed | "
                  f"payment_id={payment_id} | customer={customer_id}")

            return jsonify({
                "message":     "Payment verified and processed successfully.",
                "status":      "approved",
                "payment_id":  payment_id,
                "new_balance": final_result.get('new_sender_balance', 0.0),
            }), 200

        else:
            # ── OTP FAILED ────────────────────────────────────────────
            attempts      = increment_otp_attempts(customer_id)
            max_attempts  = 3
            remaining     = max_attempts - attempts

            if attempts >= max_attempts:
                # 3 failures — reject payment, soft-lock account 30 min
                try:
                    held_payment = get_held_payment(payment_id, customer_id)
                    if held_payment:
                        reject_payment(held_payment)
                except Exception:
                    pass

                set_soft_lock(customer_id, duration_seconds=1800)  # 30 minutes

                print(f"[PaymentRoute] OTP max attempts reached — payment rejected, "
                      f"account soft-locked | customer={customer_id}")

                return jsonify({
                    "message": "Payment rejected after 3 failed verification attempts. "
                               "Your account has been temporarily locked for 30 minutes. "
                               "Contact support if this was not you.",
                    "status":  "blocked",
                }), 403

            print(f"[PaymentRoute] OTP failed | customer={customer_id} | "
                  f"attempts={attempts}/{max_attempts}")

            return jsonify({
                "message":           f"Incorrect OTP. {remaining} attempt(s) remaining.",
                "status":            "otp_failed",
                "attempts_remaining": remaining,
            }), 401

    except ValueError as e:
        return jsonify({"message": str(e)}), 400
    except Exception as e:
        import traceback
        print(f"[PaymentRoute] OTP verification error: {e}")
        traceback.print_exc()
        return jsonify({"message": "Verification failed due to a system error."}), 500


@payment_bp.route('/payment/resend-otp', methods=['POST'])
@login_required
def resend_payment_otp(customer_id):
    """
    POST /api/payment/resend-otp
    Body: { "payment_id": "..." }

    Resends OTP for a held ALERT payment.
    Rate-limited — only allowed once per payment to prevent OTP farming.
    """
    data       = request.get_json(silent=True) or {}
    payment_id = str(data.get('payment_id', '')).strip()

    if not payment_id:
        return jsonify({"message": "payment_id is required."}), 400

    try:
        held_payment = get_held_payment(payment_id, customer_id)
        if not held_payment:
            return jsonify({
                "message": "Payment session expired or not found.",
                "status":  "expired",
            }), 410

        _send_alert_otp(customer_id, held_payment, is_resend=True)
        return jsonify({
            "message":             "OTP resent to your registered mobile number.",
            "otp_timeout_seconds": 300,
        }), 200

    except Exception as e:
        import traceback
        print(f"[PaymentRoute] Resend OTP error: {e}")
        traceback.print_exc()
        return jsonify({"message": "Could not resend OTP. Please try again."}), 500


# ── Standard routes ────────────────────────────────────────────────────────────

@payment_bp.route('/payment/history', methods=['GET'])
@login_required
def payment_history(customer_id):
    """GET /api/payment/history — last 20 payments for this customer."""
    try:
        payments = get_payment_transactions(customer_id, limit=20)
        return jsonify({"payments": payments}), 200
    except RuntimeError:
        return jsonify({"message": "Could not retrieve payment history."}), 500


@payment_bp.route('/fraud-alert/<payment_id>', methods=['GET'])
@login_required
def get_fraud_alert(customer_id, payment_id):
    """
    GET /api/fraud-alert/{payment_id}
    Retrieves the TMA fraud alert for a specific payment.
    """
    try:
        from et_dao.monitoring_dao import get_fraud_alert_by_payment
        alert = get_fraud_alert_by_payment(payment_id, customer_id)
        if not alert:
            return jsonify({"status": "processing",
                            "message": "Fraud alert not found or still processing."}), 202
        return jsonify(alert), 200
    except RuntimeError:
        return jsonify({"message": "Could not retrieve fraud alert."}), 500


@payment_bp.route('/pattern-alert/<payment_id>', methods=['GET'])
@login_required
def get_pattern_alert(customer_id, payment_id):
    """
    GET /api/pattern-alert/{payment_id}
    Retrieves the PRA result for a specific payment.
    Returns 202 while PRA is still processing (pra_processed = 0 or 2).
    """
    try:
        from et_dao.monitoring_dao import get_fraud_alert_by_payment
        alert = get_fraud_alert_by_payment(payment_id, customer_id)

        if not alert:
            return jsonify({"status": "processing",
                            "message": "Alert not found or still processing."}), 202

        pra_processed = alert.get('pra_processed', 0)
        if pra_processed != 1:
            return jsonify({"status": "processing",
                            "message": "PRA still running."}), 202

        return jsonify({
            "decision":           alert.get('pra_verdict'),
            "pattern_score":      alert.get('pattern_score'),
            "bilstm_score":       alert.get('bilstm_score'),
            "typology_code":      alert.get('typology_code'),
            "urgency_multiplier": alert.get('urgency_multiplier'),
            "pra_reg_citations":  alert.get('pra_reg_citations'),
            "agent_reasoning":    alert.get('agent_reasoning'),
            "sequence_length":    alert.get('sequence_length'),
        }), 200

    except RuntimeError:
        return jsonify({"message": "Could not retrieve pattern alert."}), 500


# ── Internal helpers ───────────────────────────────────────────────────────────

def _send_alert_otp(customer_id: str, payment_result: dict, is_resend: bool = False):
    """
    Generates and sends OTP for an ALERT-verdict payment.
    Uses the existing OTP infrastructure with FRAUD_MFA purpose.
    """
    try:
        from et_service.aba.account_controller import request_otp_verification
        result = request_otp_verification(
            customer_id=customer_id,
            alert_id=payment_result.get('fraud_alert_id') or payment_result.get('alert_id') or 0,
        )
        action = "Resent" if is_resend else "Sent"
        print(f"[PaymentRoute] {action} ALERT OTP | customer={customer_id} | "
              f"payment={payment_result.get('payment_id')} | otp_sent={result.get('otp_sent')}")
    except Exception as e:
        # OTP failure should not block the hold — just log it
        print(f"[PaymentRoute] WARN: Could not send OTP: {e}")


def _is_soft_locked(customer_id: str) -> bool:
    """Returns True if the customer's account is currently soft-locked."""
    try:
        from et_dao.aba_dao import is_soft_locked
        return is_soft_locked(customer_id)
    except Exception:
        return False  # Don't block payment if lock-check fails


def _fire_pattern_agent(payment_result: dict):
    """
    Launches PRA in a daemon background thread after payment is committed.

    Resolves alert_id via:
      1. fraud_alert_id  — set by TMA response executor (most reliable)
      2. payment_id lookup
      3. transaction_id lookup (fallback, retries up to 2.5s)
    """
    alert_id    = payment_result.get('fraud_alert_id') or payment_result.get('alert_id')
    payment_id  = payment_result['payment_id']
    txn_id      = payment_result.get('debit_transaction_id')
    customer_id = payment_result.get('sender_customer_id') or payment_result.get('customer_id')

    def _run():
        try:
            from et_service.pattern_agent.pra_agent import process_alert

            resolved_alert_id = alert_id

            if not resolved_alert_id:
                time.sleep(0.5)

                try:
                    from et_dao.monitoring_dao import get_fraud_alert_by_payment
                    row = get_fraud_alert_by_payment(payment_id, customer_id)
                    if row and row.get('alert_id'):
                        resolved_alert_id = int(row['alert_id'])
                except Exception:
                    pass

                if not resolved_alert_id and txn_id:
                    for _ in range(5):
                        time.sleep(0.5)
                        try:
                            from et_dao.monitoring_dao import get_fraud_alert_by_transaction
                            row = get_fraud_alert_by_transaction(txn_id)
                            if row and row.get('alert_id'):
                                resolved_alert_id = int(row['alert_id'])
                                break
                        except Exception:
                            pass

            if not resolved_alert_id:
                print(f"[PaymentRoute→PRA] Could not resolve alert_id for "
                      f"payment={payment_id} — PRA skipped")
                return

            process_alert(int(resolved_alert_id))

        except Exception as e:
            import traceback
            print(f"[PaymentRoute→PRA] Unhandled error in PRA thread: {e}")
            traceback.print_exc()

    t = threading.Thread(target=_run, daemon=True, name="pra-worker")
    t.start()
    print(f"[PaymentRoute] PRA thread started for payment={payment_id}")


def _mask_account(account_number: str) -> str:
    """Returns XXXX-XXXX-1234 format for display."""
    if len(account_number) < 4:
        return "****"
    return "XXXX-XXXX-" + account_number[-4:]