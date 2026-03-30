import random
import bcrypt
from datetime import datetime
from mysql.connector import Error

from db import get_db_connection
from et_model.customer import CustomerRegistration


# ── ID generation ─────────────────────────────────────────────────────────────

def _generate_constrained_id(length: int, prev_ids: set) -> str:
    """
    Generates a numeric ID of `length` digits where no digit repeats more than twice.
    Guaranteed unique against `prev_ids`.
    """
    while True:
        digits = []
        counts = {str(i): 0 for i in range(10)}
        while len(digits) < length:
            d = str(random.randint(0, 9))
            if counts[d] < 2:
                digits.append(d)
                counts[d] += 1
        candidate = "".join(digits)
        if candidate not in prev_ids:
            return candidate


def generate_unique_ids(cursor) -> tuple[str, str]:
    """Fetch existing IDs from DB and return a fresh (customer_id, account_number)."""
    cursor.execute("SELECT customer_id FROM customers")
    existing_cust_ids = {row[0] for row in cursor.fetchall()}

    cursor.execute("SELECT account_number FROM customers")
    existing_acc_nums = {row[0] for row in cursor.fetchall()}

    customer_id    = _generate_constrained_id(6,  existing_cust_ids)
    account_number = _generate_constrained_id(12, existing_acc_nums)

    return customer_id, account_number


# ── Duplicate checks ──────────────────────────────────────────────────────────

def find_by_phone(cursor, phone: str):
    cursor.execute("SELECT customer_id FROM customers WHERE phone_number = %s", (phone,))
    return cursor.fetchone()


def find_by_email(cursor, email: str):
    cursor.execute("SELECT customer_id FROM customers WHERE email = %s", (email,))
    return cursor.fetchone()


def find_by_pan(cursor, pan: str):
    cursor.execute("SELECT customer_id FROM customers WHERE pan_number = %s", (pan,))
    return cursor.fetchone()


# ── Insert ────────────────────────────────────────────────────────────────────

def insert_customer(customer: CustomerRegistration) -> dict:
    """
    Persists a validated CustomerRegistration to the DB.
    Returns {"customer_id": ..., "account_number": ...} on success.
    Raises RuntimeError on duplicate or DB error.
    """
    conn = get_db_connection()
    if not conn:
        raise RuntimeError("Database connection error.")

    try:
        cursor = conn.cursor()

        # Duplicate guards
        if find_by_phone(cursor, customer.phone):
            raise ValueError("An account with this phone number already exists.")
        if find_by_email(cursor, customer.email):
            raise ValueError("An account with this email address already exists.")
        if find_by_pan(cursor, customer.pan):
            raise ValueError("An account linked to this PAN number already exists.")

        # Hash sensitive data
        aadhaar_hash  = bcrypt.hashpw(customer.aadhaar.encode(), bcrypt.gensalt()).decode()
        temp_password = f"Temp@{random.randint(1000, 9999)}"
        password_hash = bcrypt.hashpw(temp_password.encode(), bcrypt.gensalt()).decode()

        # Unique IDs
        customer_id, account_number = generate_unique_ids(cursor)

        cursor.execute("""
            INSERT INTO customers (
                customer_id, account_number, full_name, date_of_birth, gender,
                is_minor, email, phone_number, address, city, state, country,
                aadhaar_hash, pan_number, account_type, password_hash,
                must_change_pw, created_at
            ) VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s
            )
        """, (
            customer_id, account_number, customer.full_name, customer.dob, customer.gender,
            int(customer.is_minor), customer.email, customer.phone, customer.address,
            customer.city, customer.state, customer.country,
            aadhaar_hash, customer.pan, customer.mapped_account_type, password_hash,
            True, datetime.now()
        ))

        conn.commit()
        return {"customer_id": customer_id, "account_number": account_number}

    except ValueError:
        raise  # re-raise duplicate errors cleanly
    except Error as e:
        conn.rollback()
        raise RuntimeError(f"Database error: {str(e)}")
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()

# ── Retrieve customer ─────────────────────────────────────────────────────────

def get_customer_by_id(customer_id: str) -> dict | None:
    """
    Retrieves a customer by their customer_id.
    Returns customer data dict or None if not found.
    Used by CLA agent and other services.
    """
    conn = get_db_connection()
    if not conn:
        return None
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT
                customer_id, account_number, full_name, date_of_birth, gender,
                is_minor, email, phone_number, address, city, state, country,
                pan_number, account_type, balance, is_email_verified,
                is_frozen, frozen_at, frozen_reason, created_at
            FROM customers
            WHERE customer_id = %s
        """, (customer_id,))
        row = cursor.fetchone()
        if row:
            # Convert numeric fields
            if row.get('balance') is not None:
                row['balance'] = float(row['balance'])
            # Convert boolean fields
            for bool_field in ('is_minor', 'is_email_verified', 'is_frozen'):
                if row.get(bool_field) is not None:
                    row[bool_field] = bool(row[bool_field])
        return row
    except Exception as e:
        print(f"[customer_dao] get_customer_by_id error: {e}")
        return None
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()
