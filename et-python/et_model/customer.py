from dataclasses import dataclass
from datetime import date


@dataclass
class CustomerRegistration:
    """
    Represents a validated, cleaned registration payload.
    Constructed by the service layer after validation passes.
    """
    full_name: str
    dob: str                  # "YYYY-MM-DD" string (stored as DATE in MySQL)
    gender: str               # 'male' | 'female' | 'other'
    is_minor: bool
    email: str                # normalised to lowercase
    phone: str
    address: str
    city: str
    state: str
    country: str
    aadhaar: str              # raw — hashed in DAO before storage
    pan: str                  # uppercase
    account_type: str         # 'Savings Account' | 'Current Account'
    mapped_account_type: str  # 'savings' | 'current'  (for DB ENUM)

    @staticmethod
    def from_dict(data: dict) -> "CustomerRegistration":
        """
        Build a CustomerRegistration from the raw request payload.
        Assumes validate_registration_data() has already passed.
        """
        from et_service.register_service import compute_age

        dob_str = data['dob']
        age = compute_age(dob_str)

        gender = data['gender'].strip().lower()
        pan    = data['pan'].strip().upper()
        email  = data['email'].strip().lower()
        account_type = data['accountType']
        mapped_account_type = 'savings' if account_type == 'Savings Account' else 'current'

        return CustomerRegistration(
            full_name=data['fullName'].strip(),
            dob=dob_str,
            gender=gender,
            is_minor=age < 18,
            email=email,
            phone=data['phone'].strip(),
            address=data['address'].strip(),
            city=data['city'],
            state=data['state'],
            country=data['country'],
            aadhaar=data['aadhaar'].strip(),
            pan=pan,
            account_type=account_type,
            mapped_account_type=mapped_account_type,
        )