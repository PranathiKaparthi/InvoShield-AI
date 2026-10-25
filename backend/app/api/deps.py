from typing import Generator, Optional, List
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.core.security import decode_access_token
from app.models.entities import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

def get_current_user_allow_password_change(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    """Authenticated user, even if they still have to change their initial password."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials or token expired",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception
    
    email_or_sub: str = payload.get("sub")
    if email_or_sub is None:
        raise credentials_exception
    
    user = db.query(User).filter((User.email == email_or_sub) | (User.id == (int(email_or_sub) if email_or_sub.isdigit() else -1))).first()
    if user is None:
        raise credentials_exception
    return user

def get_current_user(user: User = Depends(get_current_user_allow_password_change)) -> User:
    """Extract and validate the current authenticated user from Bearer JWT.
    Accounts flagged with must_change_password may only call /api/auth/me and /api/auth/change-password."""
    if getattr(user, "must_change_password", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="PASSWORD_CHANGE_REQUIRED: Please change your initial password before continuing.",
        )
    return user

def require_role(allowed_roles: List[str]):
    """Enforce role-based access control (RBAC)."""
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access forbidden: Role '{current_user.role}' lacks permissions for this operation. Required: {allowed_roles}"
            )
        return current_user
    return role_checker
