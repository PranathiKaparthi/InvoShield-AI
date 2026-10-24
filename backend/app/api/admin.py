from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database.session import get_db
from app.api.deps import require_role
from app.models.entities import User, AuditLog, Invoice
from app.schemas.schemas import UserResponse, AuditLogResponse, InvoiceResponse
from pydantic import BaseModel

router = APIRouter(prefix="/api/admin", tags=["Admin Operations"], dependencies=[Depends(require_role(["admin"]))])

class UpdateRoleRequest(BaseModel):
    role: str

@router.get("/users", response_model=List[UserResponse])
def get_all_users(db: Session = Depends(get_db)):
    """Admin endpoint: list all registered users."""
    return db.query(User).order_by(User.id).all()

@router.put("/users/{user_id}/role", response_model=UserResponse)
def update_user_role(user_id: int, req: UpdateRoleRequest, db: Session = Depends(get_db)):
    """Admin endpoint: change a user's role (admin, reviewer, user)."""
    if req.role not in ["admin", "reviewer", "user"]:
        raise HTTPException(status_code=400, detail="Invalid role specified.")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    
    user.role = req.role
    db.commit()
    db.refresh(user)
    return user

@router.get("/audit-logs", response_model=List[dict])
def get_all_audit_logs(db: Session = Depends(get_db)):
    """Admin endpoint: complete system audit trail."""
    logs = db.query(AuditLog).order_by(desc(AuditLog.timestamp)).limit(100).all()
    out = []
    for l in logs:
        out.append({
            "id": l.id,
            "user_id": l.user_id,
            "invoice_id": l.invoice_id,
            "action": l.action,
            "timestamp": l.timestamp,
            "details": l.details,
            "user_name": l.user.name if l.user else "System",
            "user_role": l.user.role if l.user else "system"
        })
    return out

@router.get("/flagged", response_model=List[dict])
def get_flagged_invoices(db: Session = Depends(get_db)):
    """Admin endpoint: list flagged and high risk invoices requiring administrative attention."""
    invoices = db.query(Invoice).filter(
        (Invoice.status == "flagged") | (Invoice.risk_level.ilike("high")) | (Invoice.duplicate_status == "Highly Likely Duplicate")
    ).order_by(desc(Invoice.created_at)).all()
    
    from app.api.invoices import format_invoice_response
    return [format_invoice_response(inv) for inv in invoices]
