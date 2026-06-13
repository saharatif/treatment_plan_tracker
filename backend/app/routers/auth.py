from fastapi import APIRouter, HTTPException

from app.auth import LoginRequest, TokenResponse, authenticate_demo_user, issue_token

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest) -> TokenResponse:
    user = authenticate_demo_user(payload)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return TokenResponse(access_token=issue_token(user), user=user)
