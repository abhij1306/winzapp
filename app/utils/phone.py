import re

INDIA_COUNTRY_CODE = "91"
PHONE_DIGITS_RE = re.compile(r"\D+")


def normalize_phone(raw_phone: str) -> str:
    digits = PHONE_DIGITS_RE.sub("", raw_phone)

    if digits.startswith("0"):
        digits = digits[1:]

    if len(digits) == 10:
        digits = f"{INDIA_COUNTRY_CODE}{digits}"

    if len(digits) != 12 or not digits.startswith(INDIA_COUNTRY_CODE):
        raise ValueError("Invalid phone number")

    national_number = digits[-10:]
    if national_number[0] not in {"6", "7", "8", "9"}:
        raise ValueError("Invalid phone number")

    return f"+{digits}"


def mask_phone(phone: str) -> str:
    digits = PHONE_DIGITS_RE.sub("", phone)
    if len(digits) < 4:
        return "****"
    return f"****{digits[-4:]}"
