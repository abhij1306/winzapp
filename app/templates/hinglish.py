from collections.abc import Sequence
from typing import Protocol

MAIN_MENU_HINT = "0. Main menu"
CONSENT_PROMPT = (
    "Namaste. WhatsApp par booking, reports aur reminders bhejne ke liye aapki consent chahiye.\n"
    "1. Haan, consent deta hoon\n"
    "2. Nahi"
)
CONSENT_ACCEPTED = "Dhanyavaad. Aapki consent save ho gayi hai."
CONSENT_DECLINED = "Theek hai. Hum WhatsApp automation yahin rok rahe hain."
TEST_BOOKING_UNKNOWN_CATEGORY = "Is category ko samajh nahi paaya. Kripya list se category bhejein."
TEST_BOOKING_UNKNOWN_TEST = "Is test ko samajh nahi paaya. Kripya list se test ka naam bhejein."
TEST_BOOKING_CANCELLED = "Theek hai, booking cancel kar di gayi hai."
TEST_BOOKING_CONFIRMED = "{test_name} ke liye walk-in booking confirm ho gayi hai."
HOME_COLLECTION_UNKNOWN_TEST = "Is test ke liye home collection samajh nahi paaya."
HOME_COLLECTION_UNKNOWN_SLOT = "Kripya morning slot ke liye 1 ya 2 bhejein."
HOME_COLLECTION_CONFIRMED = "{test_name} ke liye home collection booking confirm ho gayi hai."
REPORT_STATUS_NOT_FOUND = "Aapki koi active test booking nahi mili."
CANCEL_BOOKING_NOT_FOUND = "Cancel karne ke liye koi active booking nahi mili."
CANCEL_BOOKING_CONFIRMED = "{test_name} booking cancel kar di gayi hai."
OTP_LOGIN_MESSAGE = "Aapka Winzapp login OTP {otp} hai. Ye 5 minutes ke liye valid hai."
ADMIN_UNAUTHORIZED = "Ye command sirf clinic owner ke liye available hai."
ADMIN_UNKNOWN_COMMAND = "Admin command samajh nahi paaya."
ADMIN_REPORT_NOT_FOUND = "Ready report nahi mili. Pehle report upload/ready karein."
ADMIN_PATIENT_OPTED_OUT = (
    "Patient ne WhatsApp automation opt out kiya hai. Report manually share karein."
)
ADMIN_REPORT_SENT = "{test_name} report patient ko bhej di gayi hai."
REPORT_DELIVERY_CAPTION = "{test_name} report attached hai."


class BookingSummary(Protocol):
    id: object
    test_name: str
    booking_type: str
    status: str


def with_main_menu_hint(text: str) -> str:
    return f"{text}\n\n{MAIN_MENU_HINT}"


def render_main_menu() -> str:
    return (
        "Main menu:\n"
        "1. Test booking\n"
        "2. Home collection\n"
        "3. Report status\n"
        "4. Cancel booking"
    )


PATIENT_UNKNOWN_INTENT = (
    "Kripya option number bhejein.\n\n"
    f"{render_main_menu()}"
)


def render_category_prompt(categories: list[str]) -> str:
    options = "\n".join(f"{index}. {category}" for index, category in enumerate(categories, 1))
    return with_main_menu_hint(f"Kaunsa test category chahiye?\n{options}")


def render_test_selection_prompt(category: str, tests: list[str]) -> str:
    options = "\n".join(f"{index}. {test_name}" for index, test_name in enumerate(tests, 1))
    return with_main_menu_hint(f"{category} category mein ye tests available hain:\n{options}")


def render_test_confirmation_prompt(test_name: str, price: str) -> str:
    return with_main_menu_hint(
        f"{test_name} test ka amount Rs {price} hai.\n"
        "1. Confirm booking\n"
        "2. Cancel booking",
    )


def render_home_test_selection_prompt(tests: list[str]) -> str:
    options = "\n".join(f"{index}. {test_name}" for index, test_name in enumerate(tests, 1))
    return with_main_menu_hint(f"Home collection ke liye ye tests available hain:\n{options}")


def render_address_prompt(requires_fasting: bool) -> str:
    fasting_note = " Is test ke liye fasting zaroori hai." if requires_fasting else ""
    return with_main_menu_hint(f"Collection address bhejein.{fasting_note}")


def render_morning_slot_prompt() -> str:
    return with_main_menu_hint("Morning slot choose karein:\n1. Kal 8-10 AM\n2. Kal 10-12 AM")


def render_report_status_pending(test_name: str, status: str) -> str:
    return with_main_menu_hint(
        f"{test_name} report abhi {status} stage mein hai. "
        "Ready hote hi WhatsApp par bhej denge."
    )


def render_report_status_ready(test_name: str) -> str:
    return with_main_menu_hint(
        f"{test_name} report ready hai. Clinic team WhatsApp par report bhej degi.",
    )


def render_admin_today_bookings(bookings: Sequence[BookingSummary]) -> str:
    if not bookings:
        return "Aaj ke liye koi test booking nahi hai."
    rows = [render_admin_booking(index, booking) for index, booking in enumerate(bookings, 1)]
    return "Aaj ke tests:\n" + "\n".join(rows)


def render_admin_pending_reports(bookings: Sequence[BookingSummary]) -> str:
    if not bookings:
        return "Koi pending report nahi hai."
    rows = [render_admin_booking(index, booking) for index, booking in enumerate(bookings, 1)]
    return "Pending reports:\n" + "\n".join(rows)


def render_admin_booking(index: int, booking: BookingSummary) -> str:
    return (
        f"{index}. {booking.test_name} - {booking.booking_type} - "
        f"{booking.status} - {short_id(booking.id)}"
    )


def render_admin_daily_stats(stats: dict[str, int]) -> str:
    return (
        "Daily stats:\n"
        f"Tests booked today: {stats['bookings_today']} "
        f"({stats['home_collection_today']} home collection, {stats['walkin_today']} walk-in)\n"
        f"Pending reports: {stats['pending_reports']}\n"
        f"Reports delivered today: {stats['reports_delivered_today']}"
    )


def short_id(value: object) -> str:
    return str(value)[:8]
