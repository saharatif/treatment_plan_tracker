from datetime import datetime, timedelta, timezone
from typing import Annotated, Any

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import BaseModel

from app.config import settings

ALGORITHM = "HS256"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


class User(BaseModel):
    username: str
    role: str
    patient_id: str | None = None


class LoginRequest(BaseModel):
    username: str
    password: str
    patient_id: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: User


def issue_token(user: User) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": user.username,
        "role": user.role,
        "iat": int(now.timestamp()),
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }
    if user.patient_id:
        payload["patient_id"] = user.patient_id
    return jwt.encode(payload, _jwt_secret(), algorithm=ALGORITHM)


async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]) -> User:
    try:
        payload = jwt.decode(token, _jwt_secret(), algorithms=[ALGORITHM])
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    username = payload.get("sub")
    role = payload.get("role")
    if not username or not role:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
    return User(username=username, role=role, patient_id=payload.get("patient_id"))


def require_roles(*roles: str):
    async def dependency(user: Annotated[User, Depends(get_current_user)]) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
        return user

    return dependency


def authenticate_demo_user(payload: LoginRequest) -> User | None:
    users = {
        "clinician": ("clinician", settings.demo_clinician_password),
        "coordinator": ("coordinator", settings.demo_clinician_password),
        "billing": ("billing", settings.demo_billing_password),
        "patient": ("patient", settings.demo_patient_password),
    }
    record = users.get(payload.username)
    if record is None:
        return None
    role, expected_password = record
    if not expected_password or payload.password != expected_password:
        return None
    return User(username=payload.username, role=role, patient_id=payload.patient_id)


def _jwt_secret() -> str:
    if not settings.jwt_secret:
        raise HTTPException(status_code=500, detail="JWT_SECRET is not configured")
    return settings.jwt_secret
