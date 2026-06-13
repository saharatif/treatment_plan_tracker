import asyncio

from sqlalchemy.dialects.postgresql import insert

from app.database import AsyncSessionLocal
from app.models import BillingCode, Orb
from app.seed_data import CPT_CODES, HCPCS_CODES, ICD10_CODES, ORB_CATALOG


async def seed_orbs(session) -> None:
    rows = [
        {
            "catalog_code": code,
            "title": title,
            "category": category,
            "description": f"{category} catalog orb for {title}.",
            "billing_codes": billing_codes,
        }
        for code, title, category, billing_codes in ORB_CATALOG
    ]
    stmt = insert(Orb).values(rows)
    update_columns = {
        "title": stmt.excluded.title,
        "category": stmt.excluded.category,
        "description": stmt.excluded.description,
        "billing_codes": stmt.excluded.billing_codes,
    }
    await session.execute(stmt.on_conflict_do_update(index_elements=["catalog_code"], set_=update_columns))


async def seed_billing_codes(session) -> None:
    rows = [
        {
            "code": code,
            "code_system": "ICD-10",
            "description": description,
            "is_billable": False,
            "requires_auth": False,
        }
        for code, description in ICD10_CODES
    ]
    rows.extend(
        {
            "code": code,
            "code_system": "CPT",
            "description": description,
            "unit_price": unit_price,
            "medicare_rate": medicare_rate,
            "is_billable": True,
            "requires_auth": requires_auth,
        }
        for code, description, unit_price, medicare_rate, requires_auth in CPT_CODES
    )
    rows.extend(
        {
            "code": code,
            "code_system": "HCPCS",
            "description": description,
            "unit_price": unit_price,
            "medicare_rate": medicare_rate,
            "is_billable": True,
            "requires_auth": requires_auth,
        }
        for code, description, unit_price, medicare_rate, requires_auth in HCPCS_CODES
    )
    stmt = insert(BillingCode).values(rows)
    update_columns = {
        "code_system": stmt.excluded.code_system,
        "description": stmt.excluded.description,
        "unit_price": stmt.excluded.unit_price,
        "medicare_rate": stmt.excluded.medicare_rate,
        "is_billable": stmt.excluded.is_billable,
        "requires_auth": stmt.excluded.requires_auth,
    }
    await session.execute(stmt.on_conflict_do_update(index_elements=["code"], set_=update_columns))


async def seed_all() -> None:
    async with AsyncSessionLocal() as session:
        await seed_orbs(session)
        await seed_billing_codes(session)
        await session.commit()


if __name__ == "__main__":
    asyncio.run(seed_all())
