from typing import Callable, Dict, List

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from db import repository
from auth.security import decode_access_token

bearer_scheme = HTTPBearer(auto_error=False)


def _extract_token(request: Request, credentials: HTTPAuthorizationCredentials | None) -> str | None:
    if credentials and credentials.scheme.lower() == "bearer":
        return credentials.credentials

    cookie_token = request.cookies.get("access_token")
    if cookie_token:
        if cookie_token.lower().startswith("bearer "):
            return cookie_token.split(" ", 1)[1]
        return cookie_token
    return None


def get_current_user(request: Request, credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme)) -> Dict:
    token = _extract_token(request, credentials)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    try:
        payload = decode_access_token(token)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication token")

    email = payload.get("sub")
    if not email:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication token")

    user = repository.get_user_by_email(email)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    # Map AUDITOR to ADMIN for role-based access control
    # (Supabase users table supports AP_CLERK, FINANCE_MANAGER, AUDITOR; we treat AUDITOR as ADMIN)
    role = user.get("role", "").upper()
    if role == "AUDITOR":
        user["role"] = "ADMIN"
    
    return user


def require_role(allowed_roles: List[str]) -> Callable:
    normalized = {role.upper() for role in allowed_roles}

    def _role_check(current_user: Dict = Depends(get_current_user)) -> Dict:
        current_role = str(current_user.get("role", "")).upper()
        if current_role not in normalized:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
        return current_user

    return _role_check
