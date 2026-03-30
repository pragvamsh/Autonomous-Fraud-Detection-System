from dataclasses import dataclass
from datetime import datetime
from typing import Literal

OtpPurpose = Literal['EMAIL_VERIFY', 'PASSWORD_CHANGE']


@dataclass
class OtpToken:
    customer_id: str
    hashed_otp: str
    purpose: OtpPurpose
    expires_at: datetime
    used: bool = False