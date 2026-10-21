import re
from datetime import date
from decimal import Decimal
from typing import Annotated

from pydantic import AfterValidator, BeforeValidator, Field, PlainSerializer, StringConstraints

POSTAL_CODE_PATTERN = re.compile(r"^\d{8}$")
MOBILE_PHONE_PATTERN = re.compile(r"^55[1-9][1-9]9\d{8}$")
NON_DIGITS = re.compile(r"\D")
MIN_BIRTH_DATE = date(1900, 1, 1)


def _normalize_postal_code(value: object) -> object:
    if isinstance(value, str):
        return value.replace("-", "").replace(".", "").strip()
    return value


def _validate_postal_code(value: str) -> str:
    if not POSTAL_CODE_PATTERN.fullmatch(value):
        raise ValueError("Postal code must have 8 digits (CEP)")
    return value


def _normalize_mobile_phone(value: object) -> object:
    if not isinstance(value, str):
        return value
    digits = NON_DIGITS.sub("", value)
    return f"55{digits}" if len(digits) == 11 else digits


def _validate_mobile_phone(value: str) -> str:
    if not MOBILE_PHONE_PATTERN.fullmatch(value):
        raise ValueError("Mobile phone must be a Brazilian mobile number: area code + 9 digits")
    return f"+{value}"


def _validate_birth_date(value: date) -> date:
    if value > date.today():
        raise ValueError("Birth date cannot be in the future")
    if value < MIN_BIRTH_DATE:
        raise ValueError(f"Birth date cannot be before {MIN_BIRTH_DATE.isoformat()}")
    return value


FirstName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
LastName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=150)]
BirthDate = Annotated[date, AfterValidator(_validate_birth_date)]
PostalCode = Annotated[
    str, BeforeValidator(_normalize_postal_code), AfterValidator(_validate_postal_code)
]
MobilePhone = Annotated[
    str, BeforeValidator(_normalize_mobile_phone), AfterValidator(_validate_mobile_phone)
]
HoursValue = Annotated[Decimal, PlainSerializer(float, return_type=float, when_used="json")]
Hours = Annotated[HoursValue, Field(gt=0, le=168, max_digits=5, decimal_places=2)]
