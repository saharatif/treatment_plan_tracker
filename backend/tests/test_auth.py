from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

from fastapi import HTTPException
from jose import jwt
import pytest

from app import auth
from app.auth import SUPABASE_AUDIENCE, User


def _make_token(secret: str, *, sub: str = "11111111-1111-1111-1111-111111111111", email: str = "clinician@example.com") -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": sub,
        "email": email,
        "aud": SUPABASE_AUDIENCE,
        "iat": int(now.timestamp()),
        "exp": now + timedelta(hours=1),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def _session_with_role(role: str | None, patient_id: str | None = None) -> AsyncMock:
    result = MagicMock()
    record = {"role": role, "patient_id": patient_id} if role else None
    result.mappings.return_value.one_or_none.return_value = record
    session = AsyncMock()
    session.execute = AsyncMock(return_value=result)
    return session


@pytest.mark.asyncio
async def test_get_current_user_returns_role_from_user_roles(monkeypatch):
    monkeypatch.setattr(auth.settings, "supabase_jwt_secret", "test-secret")
    token = _make_token("test-secret")
    session = _session_with_role("clinician")

    user = await auth.get_current_user(token, session)

    assert user.username == "clinician@example.com"
    assert user.role == "clinician"
    assert user.patient_id is None


@pytest.mark.asyncio
async def test_get_current_user_includes_patient_id(monkeypatch):
    monkeypatch.setattr(auth.settings, "supabase_jwt_secret", "test-secret")
    token = _make_token("test-secret", email="patient@example.com")
    session = _session_with_role("patient", "PAT-2026-00847")

    user = await auth.get_current_user(token, session)

    assert user.role == "patient"
    assert user.patient_id == "PAT-2026-00847"


@pytest.mark.asyncio
async def test_get_current_user_rejects_bad_signature(monkeypatch):
    monkeypatch.setattr(auth.settings, "supabase_jwt_secret", "test-secret")
    token = _make_token("wrong-secret")
    session = _session_with_role("clinician")

    with pytest.raises(HTTPException) as exc:
        await auth.get_current_user(token, session)

    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_rejects_unknown_user(monkeypatch):
    monkeypatch.setattr(auth.settings, "supabase_jwt_secret", "test-secret")
    token = _make_token("test-secret")
    session = _session_with_role(None)

    with pytest.raises(HTTPException) as exc:
        await auth.get_current_user(token, session)

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_require_roles_rejects_wrong_role():
    dependency = auth.require_roles("billing")

    with pytest.raises(HTTPException) as exc:
        await dependency(User(username="clinician@example.com", role="clinician"))

    assert exc.value.status_code == 403
