from datetime import timedelta
from typing import Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, EmailStr

from auth.dependencies import get_current_user, require_role
from auth.security import ACCESS_TOKEN_EXPIRE_MINUTES, create_access_token, hash_password, verify_password
from db import repository

router = APIRouter(prefix="/auth", tags=["auth"])
templates = Jinja2Templates(directory="templates")

# In-memory password store for demo users (since Supabase users table doesn't have password_hash column)
_DEMO_USERS_PASSWORD_STORE: Dict[str, str] = {}


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    role: str = "AP_CLERK"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


@router.post("/register")
def register(payload: RegisterRequest):
    role = payload.role.upper()
    if role not in {"ADMIN", "AP_CLERK", "FINANCE_MANAGER"}:
        raise HTTPException(status_code=400, detail="Invalid role")

    existing = repository.get_user_by_email(payload.email)
    if existing:
        raise HTTPException(status_code=409, detail="User already exists")

    password_hash = hash_password(payload.password)
    created = repository.create_user(payload.email, role)
    if not created:
        raise HTTPException(status_code=500, detail="Unable to create user")

    # Store password in memory (workaround for missing password column in Supabase)
    _DEMO_USERS_PASSWORD_STORE[payload.email] = password_hash

    return {"id": created.get("id"), "email": created.get("email"), "role": created.get("role")}


@router.post("/login")
def login(payload: LoginRequest, response: Response):
    user = repository.get_user_by_email(payload.email)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    # Check password from in-memory store (workaround)
    stored_hash = _DEMO_USERS_PASSWORD_STORE.get(payload.email)
    if not stored_hash or not verify_password(payload.password, stored_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = create_access_token(
        subject=user["email"],
        role=user.get("role", "AP_CLERK"),
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )

    response.set_cookie(
        key="access_token",
        value=f"Bearer {token}",
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {"email": user["email"], "role": user["role"]},
    }


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie("access_token")
    return {"status": "logged_out"}


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@router.get("/me")
def me(current_user=Depends(get_current_user)):
    return {
        "id": current_user.get("id"),
        "email": current_user.get("email"),
        "role": current_user.get("role"),
    }


@router.get("/users")
def list_users(_admin=Depends(require_role(["ADMIN"]))):
    return {"items": repository.list_users()}


def ensure_demo_users() -> None:
    """Seed demo users on startup if they don't exist."""
    try:
        # Note: database supports AP_CLERK, FINANCE_MANAGER, AUDITOR roles
        # We map ADMIN -> AUDITOR for database compatibility
        seed = [
            ("admin@test.com", "demo123", "AUDITOR"),  # Maps to AUDITOR in DB, treated as ADMIN in app
            ("clerk@test.com", "demo123", "AP_CLERK"),
            ("manager@test.com", "demo123", "FINANCE_MANAGER"),
        ]
        for email, password, role in seed:
            existing = repository.get_user_by_email(email)
            if not existing:
                result = repository.create_user(email, role)
                if result:
                    # Store password in memory
                    _DEMO_USERS_PASSWORD_STORE[email] = hash_password(password)
                    print(f"[SEED] Created demo user: {email} ({role})")
            else:
                # Ensure password is in memory store
                if email not in _DEMO_USERS_PASSWORD_STORE:
                    _DEMO_USERS_PASSWORD_STORE[email] = hash_password(password)
                print(f"[SEED] Demo user already exists: {email}")
    except Exception as e:
        print(f"[SEED ERROR] Failed to seed demo users: {e}")
