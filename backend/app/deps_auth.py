from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.app.services.auth import decode_token, get_user_by_id

security = HTTPBearer(auto_error=False)


def get_optional_user(
    creds: HTTPAuthorizationCredentials | None = Depends(security),
) -> dict | None:
    if not creds:
        return None
    payload = decode_token(creds.credentials)
    if not payload:
        return None
    user = get_user_by_id(int(payload["sub"]))
    return user


def get_current_user(user: dict | None = Depends(get_optional_user)) -> dict:
    if not user:
        raise HTTPException(401, "Login required")
    return user
