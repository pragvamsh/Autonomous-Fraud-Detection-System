import re
from datetime import date, datetime


# ── Telangana cities whitelist ────────────────────────────────────────────────
VALID_CITIES = [
    'Hyderabad', 'Warangal', 'Nizamabad', 'Karimnagar', 'Khammam',
    'Mahbubnagar', 'Nalgonda', 'Adilabad', 'Suryapet', 'Miryalaguda',
    'Jagtial', 'Siddipet', 'Mancherial', 'Ramagundam', 'Sangareddy'
]


def compute_age(dob_str: str) -> int:
    """Return age in completed years from a 'YYYY-MM-DD' string."""
    dob   = datetime.strptime(dob_str, "%Y-%m-%d").date()
    today = date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


def validate_registration_data(data: dict) -> list[str]:
    """
    Pure validation function — no DB calls, no side effects.
    Returns a list of human-readable error strings (empty = valid).
    """
    errors = []

    # 1. Full Name
    full_name = data.get('fullName', '').strip()
    if not full_name:
        errors.append("Name is required.")
    elif not re.match(r"^[A-Za-z\s]+$", full_name):
        errors.append("Invalid entry — name cannot contain numbers or special characters.")
    elif len(full_name) < 3:
        errors.append("Name must be at least 3 characters.")
    elif len(full_name) > 150:
        errors.append("Name cannot exceed 150 characters.")

    # 2. Date of Birth
    dob_str = data.get('dob')
    if not dob_str:
        errors.append("Date of birth is required.")
    else:
        try:
            dob   = datetime.strptime(dob_str, "%Y-%m-%d").date()
            today = date.today()
            if dob > today:
                errors.append("Date of birth cannot be in the future.")
            elif dob < today.replace(year=today.year - 120):
                errors.append("Please enter a valid date of birth.")
        except ValueError:
            errors.append("Invalid date format for date of birth.")

    # 3. Gender
    gender = data.get('gender', '').strip().lower()
    if gender not in ('male', 'female', 'other'):
        errors.append("Please select a valid gender.")

    # 4. Email
    email = data.get('email', '').strip()
    if not email:
        errors.append("Email address is required.")
    elif not re.match(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$", email):
        errors.append("Enter a valid email address.")
    elif len(email) > 254:
        errors.append("Email address is too long.")

    # 5. Phone Number
    phone = data.get('phone', '').strip()
    if not phone:
        errors.append("Phone number is required.")
    elif not re.match(r"^\d{10}$", phone):
        errors.append("Phone number must be exactly 10 digits.")
    elif re.match(r"^(\d)\1+$", phone):
        errors.append("Invalid phone number — cannot be a repeating digit sequence.")
    elif phone[0] == '0':
        errors.append("Phone number cannot start with 0.")
    elif not re.match(r"^[6-9]", phone):
        errors.append("Enter a valid Indian mobile number (must start with 6–9).")

    # 6. Address
    address = data.get('address', '').strip()
    if not address:
        errors.append("Address is required.")
    elif len(address) < 10:
        errors.append("Address must be at least 10 characters long.")
    elif len(address) > 500:
        errors.append("Address cannot exceed 500 characters.")

    # 7. City
    if data.get('city') not in VALID_CITIES:
        errors.append("Please select a valid Telangana city from the list.")

    # 8. State
    if data.get('state') != 'Telangana':
        errors.append("State must be Telangana.")

    # 9. Country
    if data.get('country') != 'India':
        errors.append("Country must be India.")

    # 10. Aadhaar
    aadhaar = data.get('aadhaar', '').strip()
    if not aadhaar:
        errors.append("Aadhaar number is required.")
    elif not re.match(r"^\d{12}$", aadhaar):
        errors.append("Aadhaar number must be exactly 12 digits.")
    elif re.match(r"^(\d)\1+$", aadhaar):
        errors.append("Aadhaar cannot consist of all repeating digits.")
    elif aadhaar == '000000000000':
        errors.append("Invalid Aadhaar number.")
    elif not re.match(r"^[2-9]", aadhaar):
        errors.append("Aadhaar must start with a digit between 2–9.")

    # 11. PAN
    pan = data.get('pan', '').strip().upper()
    if not pan:
        errors.append("PAN number is required.")
    elif not re.match(r"^[A-Z]{5}[0-9]{4}[A-Z]{1}$", pan):
        errors.append("Invalid PAN — format must be 5 letters, 4 digits, 1 letter (e.g. ABCDE1234F).")

    # 12. Account Type
    if data.get('accountType') not in ['Savings Account', 'Current Account']:
        errors.append("Please select a valid account type.")

    return errors