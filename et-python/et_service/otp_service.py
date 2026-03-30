import random
import smtplib
import bcrypt
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ── SMTP config — swap with your real credentials ────────────────────────────
SMTP_HOST     = "smtp.gmail.com"
SMTP_PORT     = 587
SMTP_USER     = "nirmaldummy@gmail.com"       # <-- update
SMTP_PASSWORD = "Enter Your 16 char Password"          # <-- update (Gmail App Password)
FROM_NAME     = "EagleTrust Bank"

OTP_EXPIRY_MINUTES = 10
OTP_LENGTH         = 6


# ── Pure helpers (unit-testable, no I/O) ─────────────────────────────────────

def generate_otp() -> str:
    """Return a zero-padded 6-digit OTP string."""
    return str(random.randint(0, 10**OTP_LENGTH - 1)).zfill(OTP_LENGTH)


def hash_otp(otp: str) -> str:
    """bcrypt-hash the OTP for safe storage."""
    return bcrypt.hashpw(otp.encode(), bcrypt.gensalt()).decode()


def verify_otp(otp: str, hashed: str) -> bool:
    """Compare a plaintext OTP against its bcrypt hash."""
    return bcrypt.checkpw(otp.encode(), hashed.encode())


def otp_expiry() -> datetime:
    """Return the expiry datetime from now."""
    return datetime.now() + timedelta(minutes=OTP_EXPIRY_MINUTES)


def is_expired(expires_at: datetime) -> bool:
    return datetime.now() > expires_at


# ── Email delivery ────────────────────────────────────────────────────────────

def _build_email(to_email: str, to_name: str, otp: str, purpose: str) -> MIMEMultipart:
    subject_map = {
        "EMAIL_VERIFY":      "EagleTrust Bank — Verify Your Email",
        "PASSWORD_CHANGE":   "EagleTrust Bank — Password Change OTP",
        "FRAUD_MFA":         "EagleTrust Bank — Transaction Verification Required",
        "Fraud Verification": "EagleTrust Bank — Transaction Verification Required",
    }
    body_map = {
        "EMAIL_VERIFY": f"""
            <p>Dear {to_name},</p>
            <p>Use the OTP below to verify your email address.</p>
            <h2 style="letter-spacing:6px; color:#7f5539;">{otp}</h2>
            <p>This OTP is valid for <strong>{OTP_EXPIRY_MINUTES} minutes</strong> and can be used only once.</p>
            <p>If you did not request this, please contact support immediately.</p>
        """,
        "PASSWORD_CHANGE": f"""
            <p>Dear {to_name},</p>
            <p>Use the OTP below to authorise your password change.</p>
            <h2 style="letter-spacing:6px; color:#7f5539;">{otp}</h2>
            <p>This OTP is valid for <strong>{OTP_EXPIRY_MINUTES} minutes</strong> and can be used only once.</p>
            <p>If you did not request this, please ignore this email.</p>
        """,
        "FRAUD_MFA": f"""
            <p>Dear {to_name},</p>
            <p>A transaction on your account requires additional verification.</p>
            <p>Use the OTP below to confirm this transaction:</p>
            <h2 style="letter-spacing:6px; color:#c9190b;">{otp}</h2>
            <p>This OTP is valid for <strong>{OTP_EXPIRY_MINUTES} minutes</strong> and can be used only once.</p>
            <p style="color:#c9190b;"><strong>⚠️ If you did not initiate this transaction, DO NOT share this OTP.</strong></p>
            <p>Contact our fraud helpline immediately: <strong>1800-XXX-XXXX</strong></p>
        """,
        "Fraud Verification": f"""
            <p>Dear {to_name},</p>
            <p>A transaction on your account requires additional verification.</p>
            <p>Use the OTP below to confirm this transaction:</p>
            <h2 style="letter-spacing:6px; color:#c9190b;">{otp}</h2>
            <p>This OTP is valid for <strong>{OTP_EXPIRY_MINUTES} minutes</strong> and can be used only once.</p>
            <p style="color:#c9190b;"><strong>⚠️ If you did not initiate this transaction, DO NOT share this OTP.</strong></p>
            <p>Contact our fraud helpline immediately: <strong>1800-XXX-XXXX</strong></p>
        """,
    }

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject_map.get(purpose, "EagleTrust Bank — OTP")
    msg["From"]    = f"{FROM_NAME} <{SMTP_USER}>"
    msg["To"]      = to_email

    html = f"""
    <html><body style="font-family:Arial,sans-serif; color:#333; max-width:480px; margin:auto;">
        <div style="background:#7f5539; padding:16px; border-radius:8px 8px 0 0;">
            <h3 style="color:#e6ccb2; margin:0;">🏦 EagleTrust Bank</h3>
        </div>
        <div style="border:1px solid #e0c8b0; border-top:none; padding:24px; border-radius:0 0 8px 8px;">
            {body_map.get(purpose, '')}
            <hr style="border-color:#e0c8b0;">
            <p style="font-size:12px; color:#999;">
                This is an automated message. Do not reply to this email.
            </p>
        </div>
    </html></body>
    """
    msg.attach(MIMEText(html, "html"))
    return msg


def send_otp_email(to_email: str, to_name: str, otp: str, purpose: str) -> bool:
    """
    Send OTP email via SMTP.
    Returns True on success, False on failure.
    Logs errors but never raises — caller decides how to handle.
    """
    try:
        msg = _build_email(to_email, to_name, otp, purpose)
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, to_email, msg.as_string())
        return True
    except Exception as e:
        print(f"[OTP EMAIL ERROR] {e}")
        return False
