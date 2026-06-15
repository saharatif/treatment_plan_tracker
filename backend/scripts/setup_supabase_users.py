"""Provision demo Supabase users and seed app.user_roles.

Requires SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in the environment (see .env.example).

Usage:
    uv run python backend/scripts/setup_supabase_users.py
"""

import asyncio
import sys

import httpx
from sqlalchemy import text

sys.path.insert(0, "backend")

from app.config import settings  # noqa: E402
from app.database import AsyncSessionLocal  # noqa: E402

# (email, password, role, patient_id)
DEMO_USERS = [
    ("clinician@cohera.health", "change-me-clinician", "clinician", None),
    ("coordinator@cohera.health", "change-me-coordinator", "coordinator", None),
    ("billing@cohera.health", "change-me-billing", "billing", None),
    ("patient@cohera.health", "change-me-patient", "patient", "PAT-2026-00847"),
]


async def create_or_get_user(client: httpx.AsyncClient, email: str, password: str) -> str:
    response = await client.post(
        "/auth/v1/admin/users",
        json={"email": email, "password": password, "email_confirm": True},
    )
    if response.status_code == 200:
        return response.json()["id"]

    # Already exists - look it up.
    response = await client.get("/auth/v1/admin/users", params={"page": 1, "per_page": 1000})
    response.raise_for_status()
    for user in response.json().get("users", []):
        if user["email"] == email:
            return user["id"]
    raise RuntimeError(f"Could not create or find user {email}")


async def main() -> None:
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise SystemExit("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")

    headers = {
        "apikey": settings.supabase_service_role_key,
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
    }
    async with httpx.AsyncClient(base_url=settings.supabase_url, headers=headers, timeout=30) as client:
        async with AsyncSessionLocal() as session:
            for email, password, role, patient_id in DEMO_USERS:
                user_id = await create_or_get_user(client, email, password)
                await session.execute(
                    text(
                        """
                        INSERT INTO app.user_roles (supabase_user_id, email, role, patient_id)
                        VALUES (:id, :email, :role, :patient_id)
                        ON CONFLICT (supabase_user_id)
                        DO UPDATE SET email = :email, role = :role, patient_id = :patient_id
                        """
                    ),
                    {"id": user_id, "email": email, "role": role, "patient_id": patient_id},
                )
                print(f"{email} -> role={role} patient_id={patient_id} (supabase_user_id={user_id})")
            await session.commit()


if __name__ == "__main__":
    asyncio.run(main())
