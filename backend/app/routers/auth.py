"""Auth endpoints. Login itself happens client-side via Supabase; this just
exposes the resolved app role/patient scope for the current session."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.auth import User, get_current_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/me", response_model=User)
async def me(user: Annotated[User, Depends(get_current_user)]) -> User:
    return user
