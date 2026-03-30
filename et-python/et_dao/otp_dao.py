from datetime import datetime
from mysql.connector import Error
from db import get_db_connection
from et_service.otp_service import otp_expiry, hash_otp

OTP_RATE_LIMIT_MINUTES = 1   # minimum gap between OTP requests per purpose


def get_recent_otp_count(cursor, customer_id: str, purpose: str) -> int:
    """Count unused, non-expired OTPs in the last OTP_RATE_LIMIT_MINUTES window."""
    cursor.execute("""
        SELECT COUNT(*) FROM otp_tokens
        WHERE customer_id = %s AND purpose = %s AND used = 0
          AND created_at >= NOW() - INTERVAL %s MINUTE
    """, (customer_id, purpose, OTP_RATE_LIMIT_MINUTES))
    return cursor.fetchone()[0]


def invalidate_existing_otps(cursor, customer_id: str, purpose: str):
    """Mark all previous OTPs for this customer+purpose as used."""
    cursor.execute("""
        UPDATE otp_tokens SET used = 1
        WHERE customer_id = %s AND purpose = %s AND used = 0
    """, (customer_id, purpose))


def store_otp(customer_id: str, otp: str, purpose: str) -> bool:
    """
    Invalidate old OTPs, hash and store the new one.
    Enforces rate limiting: raises ValueError if too many recent requests.
    Returns True on success.
    """
    conn = get_db_connection()
    if not conn:
        raise RuntimeError("Database connection error.")
    try:
        cursor = conn.cursor()

        # Rate limit check
        if get_recent_otp_count(cursor, customer_id, purpose) > 0:
            raise ValueError(f"Please wait {OTP_RATE_LIMIT_MINUTES} minute(s) before requesting another OTP.")

        # Invalidate old OTPs for this purpose
        invalidate_existing_otps(cursor, customer_id, purpose)

        # Insert new hashed OTP
        cursor.execute("""
            INSERT INTO otp_tokens (customer_id, hashed_otp, purpose, expires_at)
            VALUES (%s, %s, %s, %s)
        """, (customer_id, hash_otp(otp), purpose, otp_expiry()))

        conn.commit()
        return True
    except ValueError:
        raise
    except Error as e:
        conn.rollback()
        raise RuntimeError(f"Database error storing OTP: {e}")
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


def fetch_latest_otp(customer_id: str, purpose: str) -> dict | None:
    """
    Fetch the most recent unused OTP record for this customer+purpose.
    Returns dict with hashed_otp, expires_at, id — or None if not found.
    """
    conn = get_db_connection()
    if not conn:
        raise RuntimeError("Database connection error.")
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT id, hashed_otp, expires_at FROM otp_tokens
            WHERE customer_id = %s AND purpose = %s AND used = 0
            ORDER BY created_at DESC LIMIT 1
        """, (customer_id, purpose))
        return cursor.fetchone()
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


def mark_otp_used(otp_id: int):
    """Mark a specific OTP record as used."""
    conn = get_db_connection()
    if not conn:
        raise RuntimeError("Database connection error.")
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE otp_tokens SET used = 1 WHERE id = %s", (otp_id,))
        conn.commit()
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


def verify_otp(customer_id: str, otp: str, purpose: str) -> bool:
    """
    Verify an OTP for the given customer and purpose.

    Fetches the latest unused OTP, checks expiry, verifies against hash,
    and marks it as used if valid.

    Returns True if OTP is valid, False otherwise.
    """
    from et_service.otp_service import verify_otp as check_otp_hash, is_expired

    record = fetch_latest_otp(customer_id, purpose)
    if not record:
        return False

    # Check expiry
    if is_expired(record['expires_at']):
        return False

    # Verify hash
    if not check_otp_hash(otp, record['hashed_otp']):
        return False

    # Mark as used
    mark_otp_used(record['id'])
    return True