"""Supabase-backed authentication and role-based access control.

Verifies the bearer token from the frontend against Supabase's JWKS (or, for
older HS256 projects, the shared SUPABASE_JWT_SECRET), then looks up the
caller's app role and patient scope in `app.user_roles`. `require_roles`
builds a FastAPI dependency that 403s if the caller's role isn't allowed.
"""

from typing import Annotated, Any

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_session

SUPABASE_AUDIENCE = "authenticated"

# Not a real OAuth login endpoint - just gives FastAPI's Swagger UI a "Authorize"
# button. Tokens are actually obtained from Supabase on the frontend.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/me", auto_error=True)

# Process-wide cache of Supabase's signing keys, refreshed on a cache miss
# (e.g. after Supabase rotates keys).
_jwks_cache: dict[str, Any] | None = None


class User(BaseModel):
    username: str
    role: str
    patient_id: str | None = None


async def _fetch_jwks() -> dict[str, Any]:
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{settings.supabase_url}/auth/v1/.well-known/jwks.json")
        response.raise_for_status()
        return response.json()


async def _signing_key_for(kid: str | None, *, refresh: bool = False) -> dict[str, Any] | None:
    global _jwks_cache
    if _jwks_cache is None or refresh:
        _jwks_cache = await _fetch_jwks()
    for key in _jwks_cache.get("keys", []):
        if key.get("kid") == kid:
            return key
    return None


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    session: AsyncSession = Depends(get_session),
) -> User:
    try:
        header = jwt.get_unverified_header(token)
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token header",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    algorithm = header.get("alg")

    # Legacy Supabase projects sign with a shared HS256 secret; newer projects use
    # asymmetric keys (ES256/RS256) published via JWKS, identified by `kid`.
    if algorithm == "HS256":
        if not settings.supabase_jwt_secret:
            raise HTTPException(status_code=500, detail="SUPABASE_JWT_SECRET is not configured")
        signing_key: Any = settings.supabase_jwt_secret
    else:
        if not settings.supabase_url:
            raise HTTPException(status_code=500, detail="SUPABASE_URL is not configured")
        kid = header.get("kid")
        signing_key = await _signing_key_for(kid)
        if signing_key is None:
            # Key not in cache - Supabase may have rotated keys, so refetch once before
            # giving up.
            signing_key = await _signing_key_for(kid, refresh=True)
        if signing_key is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unknown signing key")

    try:
        payload = jwt.decode(
            token,
            signing_key,
            algorithms=[algorithm],
            audience=SUPABASE_AUDIENCE,
        )
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    supabase_user_id = payload.get("sub")
    if not supabase_user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    # Supabase auth only proves *who* the caller is; app role and patient scope are
    # looked up separately in app.user_roles (admin-provisioned, not self-service).
    result = await session.execute(
        text("SELECT role, patient_id FROM app.user_roles WHERE supabase_user_id = :id"),
        {"id": supabase_user_id},
    )
    record = result.mappings().one_or_none()
    if record is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No role assigned for this account")

    return User(
        username=payload.get("email", supabase_user_id),
        role=record["role"],
        patient_id=record["patient_id"],
    )


def require_roles(*roles: str):
    """Build a FastAPI dependency that 403s unless the caller's role is in `roles`.

    Usage: `Depends(require_roles("clinician", "coordinator"))` on a route.
    """

    async def dependency(user: Annotated[User, Depends(get_current_user)]) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
        return user

    return dependency
