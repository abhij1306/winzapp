from __future__ import annotations

import asyncio
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import SessionLocal
from app.models import Clinic, Test

PILOT_FEATURE_FLAGS: dict[str, bool] = {
    "test_booking": True,
    "home_collection": True,
    "report_delivery": True,
    "recalls": True,
    "review_requests": True,
    "daily_digest": True,
    "llm_intent_fallback": True,
    "appointment_booking": False,
    "broadcasts": False,
    "gbp_autopilot": False,
    "razorpay": False,
}

PILOT_TEST_CATALOG: list[dict[str, object]] = [
    {
        "name": "CBC",
        "category": "Blood",
        "price": Decimal("300.00"),
        "duration_hours": 6,
        "requires_fasting": False,
    },
    {
        "name": "Thyroid Profile",
        "category": "Hormone",
        "price": Decimal("500.00"),
        "duration_hours": 12,
        "requires_fasting": False,
    },
    {
        "name": "HbA1c",
        "category": "Diabetes",
        "price": Decimal("450.00"),
        "duration_hours": 12,
        "requires_fasting": False,
    },
    {
        "name": "Lipid Profile",
        "category": "Cardiac",
        "price": Decimal("700.00"),
        "duration_hours": 12,
        "requires_fasting": True,
    },
    {
        "name": "Liver Function Test",
        "category": "Organ Function",
        "price": Decimal("650.00"),
        "duration_hours": 12,
        "requires_fasting": False,
    },
    {
        "name": "Kidney Function Test",
        "category": "Organ Function",
        "price": Decimal("650.00"),
        "duration_hours": 12,
        "requires_fasting": False,
    },
    {
        "name": "Blood Sugar Fasting",
        "category": "Diabetes",
        "price": Decimal("120.00"),
        "duration_hours": 4,
        "requires_fasting": True,
    },
    {
        "name": "Vitamin D",
        "category": "Vitamin",
        "price": Decimal("900.00"),
        "duration_hours": 24,
        "requires_fasting": False,
    },
    {
        "name": "Vitamin B12",
        "category": "Vitamin",
        "price": Decimal("800.00"),
        "duration_hours": 24,
        "requires_fasting": False,
    },
    {
        "name": "Full Body Checkup",
        "category": "Package",
        "price": Decimal("1999.00"),
        "duration_hours": 24,
        "requires_fasting": True,
    },
    {
        "name": "Urine Routine",
        "category": "Urine",
        "price": Decimal("150.00"),
        "duration_hours": 6,
        "requires_fasting": False,
    },
    {
        "name": "Dengue NS1",
        "category": "Fever",
        "price": Decimal("900.00"),
        "duration_hours": 12,
        "requires_fasting": False,
    },
]


async def seed_pilot_data(db: AsyncSession) -> dict[str, object]:
    clinic, clinic_status = await upsert_pilot_clinic(db)
    created, updated = await upsert_test_catalog(db, clinic)
    await db.commit()
    return {"clinic": clinic_status, "tests_created": created, "tests_updated": updated}


async def upsert_pilot_clinic(db: AsyncSession) -> tuple[Clinic, str]:
    statement = select(Clinic).where(Clinic.whatsapp_number == "+919000000001")
    clinic = (await db.execute(statement)).scalar_one_or_none()
    status = "updated"
    if clinic is None:
        clinic = Clinic(
            name="Pilot Diagnostics Clinic",
            whatsapp_number="+919000000001",
            owner_whatsapp="+919000000002",
            settings={},
        )
        db.add(clinic)
        status = "created"

    clinic.name = "Pilot Diagnostics Clinic"
    clinic.owner_name = "Pilot Owner"
    clinic.clinic_type = "diagnostic"
    clinic.plan = "diagnostic"
    clinic.plan_active = True
    clinic.city = "Mumbai"
    clinic.timezone = "Asia/Kolkata"
    clinic.settings = {
        "wa_phone_number_id": "pilot-wa-phone-number-id",
        "features": PILOT_FEATURE_FLAGS,
    }
    await db.flush()
    return clinic, status


async def upsert_test_catalog(db: AsyncSession, clinic: Clinic) -> tuple[int, int]:
    created = 0
    updated = 0
    for sort_order, item in enumerate(PILOT_TEST_CATALOG, start=1):
        test = await find_test(db, str(clinic.id), str(item["name"]))
        if test is None:
            test = Test(clinic_id=str(clinic.id), name=str(item["name"]))
            db.add(test)
            created += 1
        else:
            updated += 1
        apply_test_item(test, item, sort_order)
    return created, updated


async def find_test(db: AsyncSession, clinic_id: str, name: str) -> Test | None:
    statement = select(Test).where(
        Test.clinic_id == clinic_id,
        Test.name == name,
        Test.deleted_at.is_(None),
    )
    return (await db.execute(statement)).scalar_one_or_none()


def apply_test_item(test: Test, item: dict[str, object], sort_order: int) -> None:
    category = item["category"]
    price = item["price"]
    duration_hours = item["duration_hours"]
    requires_fasting = item["requires_fasting"]
    if not isinstance(duration_hours, int):
        raise TypeError("duration_hours must be an int")

    test.category = str(category)
    test.price = price if isinstance(price, Decimal) else None
    test.duration_hours = duration_hours
    test.requires_fasting = bool(requires_fasting)
    test.home_collection_available = True
    test.is_active = True
    test.sort_order = sort_order


async def main() -> None:
    async with SessionLocal() as db:
        result = await seed_pilot_data(db)
        print(result)


if __name__ == "__main__":
    asyncio.run(main())
