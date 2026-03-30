from mysql.connector import Error
from db import get_db_connection


def find_customer_by_id(customer_id: str) -> dict | None:
    conn = get_db_connection()
    if not conn:
        raise RuntimeError("Database connection error.")
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT customer_id, full_name, email, phone_number, date_of_birth,
                   gender, account_number, account_type, city, state, country,
                   balance, password_hash, password_set, is_first_login,
                   is_email_verified, is_minor, created_at, is_frozen, frozen_reason, 
                   frozen_at, frozen_by_alert_id
            FROM customers WHERE customer_id = %s
        """, (customer_id,))
        return cursor.fetchone()
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


def find_customer_by_email_or_id(identifier: str) -> dict | None:
    """Used for login — accepts either customer_id or email."""
    conn = get_db_connection()
    if not conn:
        raise RuntimeError("Database connection error.")
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT customer_id, full_name, email, password_hash,
                   password_set, is_first_login, is_email_verified
            FROM customers
            WHERE customer_id = %s OR email = %s
        """, (identifier, identifier.lower()))
        return cursor.fetchone()
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


def set_password(customer_id: str, hashed_password: str) -> bool:
    """Set password_hash, mark password_set = true."""
    conn = get_db_connection()
    if not conn:
        raise RuntimeError("Database connection error.")
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE customers
            SET password_hash = %s, password_set = 1, must_change_pw = 0
            WHERE customer_id = %s
        """, (hashed_password, customer_id))
        conn.commit()
        return cursor.rowcount > 0
    except Error as e:
        conn.rollback()
        raise RuntimeError(f"Database error: {e}")
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


def mark_email_verified(customer_id: str) -> bool:
    """Mark is_email_verified = 1. Also clears is_first_login if password is set."""
    conn = get_db_connection()
    if not conn:
        raise RuntimeError("Database connection error.")
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE customers
            SET is_email_verified = 1,
                is_first_login = CASE WHEN password_set = 1 THEN 0 ELSE is_first_login END
            WHERE customer_id = %s
        """, (customer_id,))
        conn.commit()
        return cursor.rowcount > 0
    except Error as e:
        conn.rollback()
        raise RuntimeError(f"Database error: {e}")
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


def update_email(customer_id: str, new_email: str) -> bool:
    conn = get_db_connection()
    if not conn:
        raise RuntimeError("Database connection error.")
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE customers
            SET email = %s, is_email_verified = 0
            WHERE customer_id = %s
        """, (new_email.strip().lower(), customer_id))
        conn.commit()
        return cursor.rowcount > 0
    except Error as e:
        conn.rollback()
        raise RuntimeError(f"Database error: {e}")
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


def update_phone(customer_id: str, new_phone: str) -> bool:
    conn = get_db_connection()
    if not conn:
        raise RuntimeError("Database connection error.")
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE customers SET phone_number = %s WHERE customer_id = %s
        """, (new_phone.strip(), customer_id))
        conn.commit()
        return cursor.rowcount > 0
    except Error as e:
        conn.rollback()
        raise RuntimeError(f"Database error: {e}")
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()