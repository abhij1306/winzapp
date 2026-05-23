import pytest

from app.utils.phone import mask_phone, normalize_phone


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("+91 98765 43210", "+919876543210"),
        ("09876543210", "+919876543210"),
        ("9876543210", "+919876543210"),
        ("91-98765-43210", "+919876543210"),
    ],
)
def test_normalize_phone_returns_e164_for_indian_numbers(raw: str, expected: str) -> None:
    assert normalize_phone(raw) == expected


def test_mask_phone_returns_only_last_four_digits() -> None:
    assert mask_phone("+919876543210") == "****3210"


def test_normalize_phone_rejects_invalid_phone() -> None:
    with pytest.raises(ValueError, match="Invalid phone number"):
        normalize_phone("12345")
