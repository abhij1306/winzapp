CONSENT_PROMPT = (
    "Namaste. WhatsApp par booking, reports aur reminders bhejne ke liye aapki consent chahiye. "
    "Consent dene ke liye Haan reply karein. Mana karne ke liye Nahi reply karein."
)
CONSENT_ACCEPTED = "Dhanyavaad. Aapki consent save ho gayi hai."
CONSENT_DECLINED = "Theek hai. Hum WhatsApp automation yahin rok rahe hain."
TEST_BOOKING_UNKNOWN_CATEGORY = "Is category ko samajh nahi paaya. Kripya list se category bhejein."
TEST_BOOKING_UNKNOWN_TEST = "Is test ko samajh nahi paaya. Kripya list se test ka naam bhejein."
TEST_BOOKING_CANCELLED = "Theek hai, booking cancel kar di gayi hai."
TEST_BOOKING_CONFIRMED = "{test_name} ke liye walk-in booking confirm ho gayi hai."


def render_category_prompt(categories: list[str]) -> str:
    options = "\n".join(f"{index}. {category}" for index, category in enumerate(categories, 1))
    return f"Kaunsa test category chahiye?\n{options}"


def render_test_selection_prompt(category: str, tests: list[str]) -> str:
    options = "\n".join(f"{index}. {test_name}" for index, test_name in enumerate(tests, 1))
    return f"{category} category mein ye tests available hain:\n{options}"


def render_test_confirmation_prompt(test_name: str, price: str) -> str:
    return f"{test_name} test ka amount Rs {price} hai. Confirm karne ke liye Haan bhejein."
