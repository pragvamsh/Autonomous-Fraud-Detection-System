from mysql.connector import Error
from db import get_db_connection
from datetime import datetime


def get_customer_by_account(account_number: str) -> dict | None:
    """
    Looks up a customer by their account number.
    Returns customer_id, full_name, account_number or None if not found.
    """
    conn = get_db_connection()
    if not conn:
        raise RuntimeError("Database connection error.")
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT customer_id, full_name, account_number
            FROM customers
            WHERE account_number = %s
        """, (account_number,))
        return cursor.fetchone()
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


def create_pending_payment(sender_customer_id: str,
                           sender_account: str,
                           recipient_account: str,
                           amount: float,
                           description: str,
                           payment_id: str,
                           debit_txn_id: str,
                           credit_txn_id: str,
                           recipient_customer_id: str,
                           credit_txn_description: str) -> dict:
    """
    Creates the payment records in PENDING state. Does NOT deduct balance yet.
    """
    conn = get_db_connection()
    if not conn:
        raise RuntimeError("Database connection error.")
    try:
        cursor = conn.cursor()
        now = datetime.now()

        # ── Insert DEBIT transaction record for sender (PENDING) ─────────────
        cursor.execute("""
            INSERT INTO transactions
                (transaction_id, customer_id, type, amount,
                 description, balance_after, recipient_account,
                 agent_status, created_at)
            VALUES (%s, %s, 'DEBIT', %s, %s, 0.0, %s, 'PENDING', %s)
        """, (
            debit_txn_id, sender_customer_id, amount,
            description, recipient_account, now
        ))

        # ── Insert payment_transactions record (PENDING) ─────────────────────
        cursor.execute("""
            INSERT INTO payment_transactions
                (payment_id, sender_customer_id, sender_account,
                 recipient_account, recipient_customer_id,
                 amount, description,
                 debit_transaction_id, credit_transaction_id,
                 status, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'PENDING_REVIEW', %s)
        """, (
            payment_id, sender_customer_id, sender_account,
            recipient_account, recipient_customer_id,
            amount, description,
            debit_txn_id, credit_txn_id, now
        ))

        conn.commit()
        return {}
    except Error as e:
        conn.rollback()
        raise RuntimeError(f"Database error during create pending payment: {e}")
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


def commit_payment(payment_id: str,
                   sender_customer_id: str,
                   recipient_customer_id: str,
                   amount: float,
                   debit_txn_id: str,
                   credit_txn_id: str,
                   sender_account: str,
                   credit_txn_description: str,
                   status_override: str = 'COMPLETED') -> dict:
    """
    Atomically:
      1. Debits sender balance (SELECT FOR UPDATE lock)
      2. Credits recipient balance
      3. Updates DEBIT transaction balance_after and agent_status
      4. Inserts CREDIT transaction record for recipient
      5. Updates payment_transactions status to COMPLETED (or FLAGGED)
    """
    print(f"[commit_payment] START | payment_id={payment_id} | "
          f"sender={sender_customer_id} | recipient={recipient_customer_id} | "
          f"amount={amount} | status={status_override}")

    conn = get_db_connection()
    if not conn:
        raise RuntimeError("Database connection error.")
    try:
        cursor = conn.cursor()
        now = datetime.now()

        # ── 1. Lock and debit sender ──────────────────────────────────
        cursor.execute("""
            SELECT balance FROM customers
            WHERE customer_id = %s FOR UPDATE
        """, (sender_customer_id,))
        row = cursor.fetchone()
        if not row:
            raise ValueError("Sender account not found.")

        sender_balance = float(row[0])
        if sender_balance < amount:
            raise ValueError("Insufficient balance.")

        new_sender_balance = round(sender_balance - amount, 2)
        print(f"[commit_payment] Sender balance: {sender_balance} -> {new_sender_balance}")

        cursor.execute("""
            UPDATE customers SET balance = %s
            WHERE customer_id = %s
        """, (new_sender_balance, sender_customer_id))
        print(f"[commit_payment] Sender UPDATE affected {cursor.rowcount} row(s)")

        # ── 2. Lock and credit recipient ──────────────────────────────
        cursor.execute("""
            SELECT balance FROM customers
            WHERE customer_id = %s FOR UPDATE
        """, (recipient_customer_id,))
        row = cursor.fetchone()
        if not row:
            raise ValueError("Recipient account not found.")

        recipient_balance   = float(row[0])
        new_recipient_balance = round(recipient_balance + amount, 2)
        print(f"[commit_payment] Recipient balance: {recipient_balance} -> {new_recipient_balance}")

        cursor.execute("""
            UPDATE customers SET balance = %s
            WHERE customer_id = %s
        """, (new_recipient_balance, recipient_customer_id))
        print(f"[commit_payment] Recipient UPDATE affected {cursor.rowcount} row(s)")

        # ── 3. Update DEBIT transaction record for sender ─────────────
        cursor.execute("""
            UPDATE transactions
            SET balance_after = %s, agent_status = 'EVALUATED'
            WHERE transaction_id = %s
        """, (new_sender_balance, debit_txn_id))

        # ── 4. Insert CREDIT transaction record for recipient ─────────
        cursor.execute("""
            INSERT INTO transactions
                (transaction_id, customer_id, type, amount,
                 description, balance_after, recipient_account,
                 agent_status, created_at)
            VALUES (%s, %s, 'CREDIT', %s, %s, %s, %s, 'SKIPPED', %s)
        """, (
            credit_txn_id, recipient_customer_id, amount,
            credit_txn_description, new_recipient_balance,
            sender_account, datetime.now()
        ))

        # ── 5. Update payment_transactions record ─────────────────────
        cursor.execute("""
            UPDATE payment_transactions
            SET status = %s, completed_at = %s
            WHERE payment_id = %s
        """, (status_override, datetime.now(), payment_id))

        conn.commit()
        print(f"[commit_payment] COMMITTED | sender_new={new_sender_balance} | recipient_new={new_recipient_balance}")

        return {
            "new_sender_balance":    new_sender_balance,
            "new_recipient_balance": new_recipient_balance,
            "debit_txn_id":          debit_txn_id,
            "credit_txn_id":         credit_txn_id,
        }

    except ValueError as e:
        conn.rollback()
        print(f"[commit_payment] ROLLBACK (ValueError): {e}")
        raise
    except Error as e:
        conn.rollback()
        print(f"[commit_payment] ROLLBACK (DB Error): {e}")
        raise RuntimeError(f"Database error during payment commit: {e}")
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


def reject_payment(payment_id: str, debit_txn_id: str):
    """
    Called when TMA says BLOCK. Marks records as FAILED/REVERSED.
    """
    conn = get_db_connection()
    if not conn:
        raise RuntimeError("Database connection error.")
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE transactions SET agent_status = 'FAILED' WHERE transaction_id = %s", (debit_txn_id,))
        cursor.execute("UPDATE payment_transactions SET status = 'FAILED' WHERE payment_id = %s", (payment_id,))
        conn.commit()
    except Error as e:
        conn.rollback()
        raise RuntimeError(f"Database error rejecting payment: {e}")
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


def hold_payment(payment_id: str, debit_txn_id: str):
    """
    Called when TMA says ALERT. Keeps records in PENDING_REVIEW state.
    """
    conn = get_db_connection()
    if not conn:
        raise RuntimeError("Database connection error.")
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE payment_transactions SET status = 'PENDING_REVIEW' WHERE payment_id = %s", (payment_id,))
        conn.commit()
    except Error as e:
        conn.rollback()
        raise RuntimeError(f"Database error holding payment: {e}")
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


def update_payment_status(payment_id: str,
                           status: str,
                           fraud_alert_id: int = None,
                           risk_score: int = None):
    """
    Called by the monitoring agent after evaluation to update
    the payment record with the fraud alert result.
    """
    conn = get_db_connection()
    if not conn:
        raise RuntimeError("Database connection error.")
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE payment_transactions
            SET status         = %s,
                fraud_alert_id = COALESCE(%s, fraud_alert_id),
                risk_score     = COALESCE(%s, risk_score)
            WHERE payment_id = %s
        """, (status, fraud_alert_id, risk_score, payment_id))
        conn.commit()
    except Error as e:
        conn.rollback()
        raise RuntimeError(f"Database error updating payment status: {e}")
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


def create_payment_record():
    """Placeholder — payment record creation is handled inside debit_account."""
    pass


def get_held_payment(payment_id: str, customer_id: str = None) -> dict | None:
    """
    Retrieves a held payment (PENDING_REVIEW) by payment_id.
    Used by OTP verify route to look up payment details before releasing.

    If customer_id is provided, also validates that the customer owns this payment
    (security check to prevent accessing other users' held payments).
    """
    conn = get_db_connection()
    if not conn:
        raise RuntimeError("Database connection error.")
    try:
        cursor = conn.cursor(dictionary=True)
        if customer_id:
            cursor.execute("""
                SELECT payment_id, sender_customer_id, sender_account,
                       recipient_account, recipient_customer_id,
                       amount, description,
                       debit_transaction_id, credit_transaction_id,
                       status, created_at
                FROM payment_transactions
                WHERE payment_id = %s AND status = 'PENDING_REVIEW'
                  AND sender_customer_id = %s
            """, (payment_id, customer_id))
        else:
            cursor.execute("""
                SELECT payment_id, sender_customer_id, sender_account,
                       recipient_account, recipient_customer_id,
                       amount, description,
                       debit_transaction_id, credit_transaction_id,
                       status, created_at
                FROM payment_transactions
                WHERE payment_id = %s AND status = 'PENDING_REVIEW'
            """, (payment_id,))
        row = cursor.fetchone()
        if row:
            row['amount'] = float(row['amount'])
        return row
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


def get_payment_history(customer_id: str, limit: int = 20) -> list[dict]:
    """
    Returns recent payment history for a customer —
    both sent and received payments.
    """
    conn = get_db_connection()
    if not conn:
        raise RuntimeError("Database connection error.")
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT
                pt.payment_id,
                pt.sender_account,
                pt.recipient_account,
                pt.amount,
                pt.description,
                pt.status,
                pt.risk_score,
                pt.created_at,
                CASE
                    WHEN pt.sender_customer_id = %s THEN 'SENT'
                    ELSE 'RECEIVED'
                END AS direction
            FROM payment_transactions pt
            WHERE pt.sender_customer_id = %s
               OR pt.recipient_customer_id = %s
            ORDER BY pt.created_at DESC
            LIMIT %s
        """, (customer_id, customer_id, customer_id, limit))
        rows = cursor.fetchall()
        for row in rows:
            row['created_at'] = row['created_at'].isoformat()
            row['amount']     = float(row['amount'])
        return rows
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()