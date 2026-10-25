from datetime import datetime, timedelta, timezone
from typing import Dict, Any
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_

from app.core.config import settings

from app.database.session import get_db
from app.api.deps import get_current_user
from app.models.entities import User, Invoice, AuditLog
from app.schemas.schemas import DashboardStatistics, DashboardAnalytics

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard Analytics"])


def to_usd(amount, currency) -> float:
    """Dashboard totals mix invoices in different currencies; add them up in one base (USD).
    The web app converts the base to the currency the user picks."""
    rate = settings.FX_RATES_PER_USD.get((currency or "USD").upper(), 1.0) or 1.0
    return float(amount or 0.0) / rate


def scoped_audit_logs(db: Session, user: User):
    """Admins see every event; reviewers only their organization's; users only their own."""
    q = db.query(AuditLog)
    if user.role == "user":
        return q.filter(AuditLog.user_id == user.id)
    if user.role == "reviewer":
        org = user.organization or "General"
        org_users = db.query(User.id).filter(User.organization == org)
        org_invoices = db.query(Invoice.id).filter(Invoice.organization == org)
        return q.filter(or_(AuditLog.user_id.in_(org_users), AuditLog.invoice_id.in_(org_invoices)))
    return q

@router.get("/statistics", response_model=DashboardStatistics)
def get_dashboard_statistics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Aggregate statistics for KPI summary cards."""
    query = db.query(Invoice)
    if current_user.role == "user":
        query = query.filter(Invoice.user_id == current_user.id)
    elif current_user.role == "reviewer":
        query = query.filter(Invoice.organization == (current_user.organization or "General"))

    total_invoices = query.count()
    pending = query.filter(Invoice.status.in_(["pending_review", "uploaded"])).count()
    approved = query.filter(Invoice.status == "approved").count()
    rejected = query.filter(Invoice.status == "rejected").count()
    flagged = query.filter(Invoice.status == "flagged").count()
    
    dup_alerts = query.filter(Invoice.duplicate_status.in_(["Highly Likely Duplicate", "Possible Duplicate"])).count()
    high_risk = query.filter(Invoice.risk_level.ilike("high")).count()

    total_val = sum(to_usd(amount, cur) for amount, cur in
                    query.with_entities(Invoice.total_amount, Invoice.currency).all())

    return {
        "total_invoices": total_invoices,
        "pending_invoices": pending,
        "approved_invoices": approved,
        "rejected_invoices": rejected,
        "flagged_invoices": flagged,
        "duplicate_alerts": dup_alerts,
        "high_risk_count": high_risk,
        "total_amount_processed": round(total_val, 2)
    }

@router.get("/analytics", response_model=DashboardAnalytics)
def get_dashboard_analytics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Comprehensive chart data and recent activity feed."""
    base_query = db.query(Invoice)
    if current_user.role == "user":
        base_query = base_query.filter(Invoice.user_id == current_user.id)
    elif current_user.role == "reviewer":
        base_query = base_query.filter(Invoice.organization == (current_user.organization or "General"))

    invoices = base_query.all()

    # 1. Status Distribution
    status_counts = {"approved": 0, "pending_review": 0, "flagged": 0, "rejected": 0, "uploaded": 0}
    for inv in invoices:
        st = inv.status or "uploaded"
        status_counts[st] = status_counts.get(st, 0) + 1

    status_distribution = [
        {"name": "Approved", "count": status_counts.get("approved", 0), "color": "#10B981"},
        {"name": "Pending Review", "count": status_counts.get("pending_review", 0) + status_counts.get("uploaded", 0), "color": "#3B82F6"},
        {"name": "Flagged Risk", "count": status_counts.get("flagged", 0), "color": "#F59E0B"},
        {"name": "Rejected", "count": status_counts.get("rejected", 0), "color": "#EF4444"},
    ]

    # 2. Risk Distribution
    risk_counts = {"Low": 0, "Medium": 0, "High": 0}
    for inv in invoices:
        lvl = (inv.risk_level or "Low").capitalize()
        risk_counts[lvl] = risk_counts.get(lvl, 0) + 1

    risk_distribution = [
        {"level": "Low (0-30)", "count": risk_counts.get("Low", 0), "color": "#10B981"},
        {"level": "Medium (31-60)", "count": risk_counts.get("Medium", 0), "color": "#F59E0B"},
        {"level": "High (61-100)", "count": risk_counts.get("High", 0), "color": "#EF4444"},
    ]

    # 3. Processing over time (last 7 days or weeks)
    now = datetime.now(timezone.utc)
    days_map = {}
    for i in range(6, -1, -1):
        day_date = (now - timedelta(days=i)).strftime("%b %d")
        days_map[day_date] = {"date": day_date, "count": 0, "amount": 0.0}

    for inv in invoices:
        if inv.created_at:
            day_str = inv.created_at.strftime("%b %d")
            if day_str in days_map:
                days_map[day_str]["count"] += 1
                days_map[day_str]["amount"] = round(days_map[day_str]["amount"] + to_usd(inv.total_amount, inv.currency), 2)

    processing_over_time = list(days_map.values())

    # 4. Vendor Distribution (Top 5)
    vendor_stats: Dict[str, Dict[str, Any]] = {}
    for inv in invoices:
        v = inv.vendor_name or "Unknown Vendor"
        if v not in vendor_stats:
            vendor_stats[v] = {"vendor": v, "count": 0, "total_amount": 0.0}
        vendor_stats[v]["count"] += 1
        vendor_stats[v]["total_amount"] = round(vendor_stats[v]["total_amount"] + to_usd(inv.total_amount, inv.currency), 2)

    vendor_distribution = sorted(vendor_stats.values(), key=lambda x: x["total_amount"], reverse=True)[:5]

    # 5. Monthly Totals
    monthly_map = {}
    for i in range(5, -1, -1):
        m_str = (now - timedelta(days=i*30)).strftime("%b %Y")
        monthly_map[m_str] = {"month": m_str, "count": 0, "amount": 0.0}

    for inv in invoices:
        if inv.created_at:
            m_str = inv.created_at.strftime("%b %Y")
            if m_str in monthly_map:
                monthly_map[m_str]["count"] += 1
                monthly_map[m_str]["amount"] = round(monthly_map[m_str]["amount"] + to_usd(inv.total_amount, inv.currency), 2)

    monthly_totals = list(monthly_map.values())

    # 6. Recent Activities from Audit Logs
    recent_audits = scoped_audit_logs(db, current_user).order_by(desc(AuditLog.timestamp)).limit(10).all()

    formatted_audits = []
    for a in recent_audits:
        formatted_audits.append({
            "id": a.id,
            "user_id": a.user_id,
            "invoice_id": a.invoice_id,
            "action": a.action,
            "timestamp": a.timestamp,
            "details": a.details,
            "user_name": a.user.name if a.user else "System",
        })

    return {
        "processing_over_time": processing_over_time,
        "status_distribution": status_distribution,
        "risk_distribution": risk_distribution,
        "vendor_distribution": vendor_distribution,
        "monthly_totals": monthly_totals,
        "recent_activities": formatted_audits
    }
