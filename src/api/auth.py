"""Authentication API routes using JSON-based account storage."""

from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, constr

from ..storage.auth_storage import create_account, find_account, load_accounts
from ..storage.user_storage import UserStorage

router = APIRouter(prefix="/api", tags=["auth"])

# In-memory token storage: token -> {"username": str, "user_id": str}
SESSION_TOKENS: dict[str, dict] = {}

# User storage instance
user_storage = UserStorage()


class AuthResponse(BaseModel):
    success: bool
    token: str
    user: dict  # {"username": str, "user_id": str}


class MessageResponse(BaseModel):
    success: bool
    message: str


class RegisterRequest(BaseModel):
    username: constr(min_length=1, strip_whitespace=True)
    password: constr(min_length=1)


class LoginRequest(BaseModel):
    username: constr(min_length=1, strip_whitespace=True)
    password: constr(min_length=1)


def _generate_token(account: dict) -> str:
    """Generate token and store account info"""
    token = uuid4().hex
    SESSION_TOKENS[token] = {
        "username": account["username"],
        "user_id": account["user_id"],
    }
    return token


def _get_user_by_token(authorization: str | None) -> dict:
    """Get user info from token"""
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token")

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token format")

    user_info = SESSION_TOKENS.get(token)
    if not user_info:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    return user_info


def get_current_user(authorization: str = Header(None)) -> dict:
    """Dependency to get current user from token"""
    return _get_user_by_token(authorization)


@router.post("/register", response_model=AuthResponse)
def register(payload: RegisterRequest) -> AuthResponse:
    """Register a new account and return an auth token."""
    username = payload.username
    password = payload.password

    if find_account(username):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already exists")

    account = create_account(username, password)
    
    # Create user data in user.json
    user_storage.create_user_if_not_exists(account["user_id"])
    
    token = _generate_token(account)
    return AuthResponse(
        success=True,
        token=token,
        user={"username": account["username"], "user_id": account["user_id"]},
    )


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest) -> AuthResponse:
    """Login with username and password."""
    username = payload.username
    password = payload.password

    account = find_account(username)
    if not account or account.get("password") != password:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    # Ensure user data exists
    user_storage.create_user_if_not_exists(account["user_id"])
    
    token = _generate_token(account)
    return AuthResponse(
        success=True,
        token=token,
        user={"username": account["username"], "user_id": account["user_id"]},
    )


@router.get("/me")
def get_me(authorization: str = Header(None)) -> dict:
    """Get current user info from token."""
    user_info = _get_user_by_token(authorization)
    account = find_account(user_info["username"])

    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

    return {
        "username": account["username"],
        "user_id": account["user_id"],
        "success": True,
    }


@router.post("/logout", response_model=MessageResponse)
def logout(authorization: str = Header(None)) -> MessageResponse:
    """Logout by removing token."""
    user_info = _get_user_by_token(authorization)

    # Remove all tokens associated with user
    tokens_to_remove = [
        token for token, info in SESSION_TOKENS.items()
        if info["username"] == user_info["username"]
    ]
    for token in tokens_to_remove:
        SESSION_TOKENS.pop(token, None)

    return MessageResponse(success=True, message="Logged out")


@router.get("/accounts", response_model=list[dict])
def list_accounts() -> list[dict]:
    """List all accounts (for debugging/demo purposes)."""
    return load_accounts()


