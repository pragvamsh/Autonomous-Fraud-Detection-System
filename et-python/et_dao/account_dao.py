from mysql.connector import Error
from db import get_db_connection
from et_service.account_service import generate_transaction_id
from datetime import datetime


def get_balance(customer_id: str) -> float | None:
    conn = get_db_connection()
    if not conn:
        raise RuntimeError("Database connection error.")
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT balance FROM customers WHERE customer_id = %s", (customer_id,))
        row = cursor.fetchone()
        return float(row[0]) if row else None
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


def credit_account(customer_id: str, amount: float, description: str = "Add Money") -> dict:
    """
    Atomically credits the account and inserts a CREDIT transaction record.
    Returns the new balance and transaction ID.
    """
    conn = get_db_connection()
    if not conn:
        raise RuntimeError("Database connection error.")
    try:
        cursor = conn.cursor()

        # Lock the row for atomic update
        cursor.execute("""
            SELECT balance FROM customers
            WHERE customer_id = %s FOR UPDATE
        """, (customer_id,))
        row = cursor.fetchone()
        if not row:
            raise ValueError("Account not found.")

        new_balance = float(row[0]) + amount
        txn_id = generate_transaction_id()

        cursor.execute("""
            UPDATE customers SET balance = %s WHERE customer_id = %s
        """, (new_balance, customer_id))

        cursor.execute("""
            INSERT INTO transactions
                (transaction_id, customer_id, type, amount, description, balance_after, created_at)
            VALUES (%s, %s, 'CREDIT', %s, %s, %s, %s)
        """, (txn_id, customer_id, amount, description, new_balance, datetime.now()))

        conn.commit()
        return {"transaction_id": txn_id, "new_balance": new_balance}

    except ValueError:
        raise
    except Error as e:
        conn.rollback()
        raise RuntimeError(f"Database error: {e}")
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


def get_transactions(customer_id: str, limit: int = 20) -> list[dict]:
    conn = get_db_connection()
    if not conn:
        raise RuntimeError("Database connection error.")
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT transaction_id, type, amount, description, balance_after, created_at
            FROM transactions
            WHERE customer_id = %s
            ORDER BY created_at DESC
            LIMIT %s
        """, (customer_id, limit))
        rows = cursor.fetchall()
        # Serialize datetimes
        for row in rows:
            row['created_at'] = row['created_at'].isoformat()
            row['amount'] = float(row['amount'])
            row['balance_after'] = float(row['balance_after'])
        return rows
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()