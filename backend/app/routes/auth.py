from fastapi import APIRouter, Depends, HTTPException

from backend.app.deps_auth import get_current_user
from backend.app.models.schemas import AuthResponse, LoginRequest, RegisterRequest, UserResponse
from backend.app.services import auth as auth_service

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=AuthResponse)
def register(body: RegisterRequest):
    try:
        result = auth_service.register_user(body.email, body.password)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return AuthResponse(**result)


@router.post("/login", response_model=AuthResponse)
def login(body: LoginRequest):
    try:
        result = auth_service.login_user(body.email, body.password)
    except ValueError as e:
        raise HTTPException(401, str(e)) from e
    return AuthResponse(**result)


@router.get("/me", response_model=UserResponse)
def me(user: dict = Depends(get_current_user)):
    return UserResponse(user_id=user["id"], email=user["email"])
