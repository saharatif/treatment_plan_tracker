from fastapi import HTTPException
import pytest

from app import auth
from app.auth import LoginRequest, User, authenticate_demo_user, issue_token


@pytest.mark.asyncio
async def test_issue_and_validate_token(monkeypatch):
    monkeypatch.setattr(auth.settings, "jwt_secret", "test-secret")
    token = issue_token(User(username="clinician", role="clinician"))

    user = await auth.get_current_user(token)

    assert user.username == "clinician"
    assert user.role == "clinician"


def test_authenticate_demo_user_requires_configured_password(monkeypatch):
    monkeypatch.setattr(auth.settings, "demo_billing_password", "billing-pass")

    user = authenticate_demo_user(LoginRequest(username="billing", password="billing-pass"))

    assert user is not None
    assert user.role == "billing"


@pytest.mark.asyncio
async def test_require_roles_rejects_wrong_role():
    dependency = auth.require_roles("billing")

    with pytest.raises(HTTPException) as exc:
        await dependency(User(username="clinician", role="clinician"))

    assert exc.value.status_code == 403
