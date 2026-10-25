from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.models.entities import User, AuditLog
from app.schemas.schemas import UserCreate, UserLogin, UserResponse, TokenResponse, ChangePasswordRequest
from app.core.security import get_password_hash, verify_password, create_access_token
from app.api.deps import get_current_user_allow_password_change

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

from sqlalchemy import func

@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(user_in: UserCreate, db: Session = Depends(get_db)):
    """Register a new user, hash password with bcrypt, and issue JWT."""
    email_clean = user_in.email.strip().lower()
    existing_user = db.query(User).filter(func.lower(User.email) == email_clean).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email address already exists."
        )
    
    # Restrict direct registration of admin role unless first user
    role = user_in.role if user_in.role in ["reviewer", "user"] else "user"
    
    new_user = User(
        name=user_in.name.strip() if user_in.name else "User",
        email=email_clean,
        password_hash=get_password_hash(user_in.password),
        role=role,
        organization=user_in.organization or "General"
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Audit log
    audit = AuditLog(
        user_id=new_user.id,
        action="USER_REGISTERED",
        details=f"User registered with email {new_user.email} and role {new_user.role}"
    )
    db.add(audit)
    db.commit()

    token = create_access_token(subject=new_user.email, role=new_user.role)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": new_user
    }

@router.post("/login", response_model=TokenResponse)
def login(login_data: UserLogin, db: Session = Depends(get_db)):
    """Authenticate user with email and password, returning JWT access token."""
    email_clean = login_data.email.strip().lower()
    user = db.query(User).filter(func.lower(User.email) == email_clean).first()
    if not user or not verify_password(login_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = create_access_token(subject=user.email, role=user.role)

    audit = AuditLog(
        user_id=user.id,
        action="USER_LOGIN",
        details=f"User {user.email} logged in successfully."
    )
    db.add(audit)
    db.commit()

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user
    }

@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user_allow_password_change)):
    """Get profile of current authenticated user."""
    return current_user

@router.post("/change-password", response_model=UserResponse)
def change_password(
    req: ChangePasswordRequest,
    current_user: User = Depends(get_current_user_allow_password_change),
    db: Session = Depends(get_db),
):
    """Change own password. Clears the forced first-login password change flag."""
    if not verify_password(req.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect.")
    if req.current_password == req.new_password:
        raise HTTPException(status_code=400, detail="New password must be different from the current one.")
    current_user.password_hash = get_password_hash(req.new_password)
    current_user.must_change_password = False
    db.add(AuditLog(user_id=current_user.id, action="USER_PASSWORD_CHANGED",
                    details=f"User {current_user.email} changed their password."))
    db.commit()
    db.refresh(current_user)
    return current_user
