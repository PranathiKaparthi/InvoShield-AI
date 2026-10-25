from datetime import datetime, timezone
from typing import Dict, Any, List, Tuple, Optional
from sqlalchemy.orm import Session
from app.models.entities import Invoice
from app.services.encryption_service import encryption_service

class FraudDetectionService:
    """
    Rule-based Anomaly and Risk Scoring Engine.
    Modular structure: can be subclassed or replaced by a scikit-learn IsolationForest / Autoencoder model.
    Produces:
      - Risk Score (0 - 100)
      - Risk Level (Low: 0-30, Medium: 31-60, High: 61-100)
      - Plain-language Alert Reason
    """

    def analyze(self, invoice_data: Dict[str, Any], duplicate_score: float, db: Session, current_invoice_id: Optional[int] = None, organization: Optional[str] = None) -> Tuple[int, str, List[str]]:
        risk_score = 0
        reasons: List[str] = []

        total_amount = float(invoice_data.get("total_amount") or 0.0)
        subtotal = float(invoice_data.get("subtotal") or 0.0)
        tax = float(invoice_data.get("tax_amount") or 0.0)
        discount = float(invoice_data.get("discount") or 0.0)
        vendor_name = (invoice_data.get("vendor_name") or "").strip()
        inv_number = (invoice_data.get("invoice_number") or "").strip()
        inv_date_str = (invoice_data.get("invoice_date") or "").strip()
        gst_number = (invoice_data.get("gst_number") or "").strip()
        sym = {"INR": "₹", "USD": "$", "EUR": "€", "GBP": "£"}.get((invoice_data.get("currency") or "USD").upper(), "$")

        # Rule 1: Duplicate Invoice Risk
        if duplicate_score >= 90.0:
            risk_score += 45
            reasons.append(f"Critical Duplicate Alert: High similarity ({duplicate_score}%) detected against existing invoices.")
        elif duplicate_score >= 75.0:
            risk_score += 25
            reasons.append(f"Potential Duplicate Alert: Noticeable similarity ({duplicate_score}%) found.")

        # Rule 2: Same invoice number with different amounts
        if inv_number and db:
            query = db.query(Invoice).filter(Invoice.invoice_number == inv_number)
            if organization:
                query = query.filter(Invoice.organization == organization)
            if current_invoice_id:
                query = query.filter(Invoice.id != current_invoice_id)
            matching_number_invoices = query.all()
            for prior in matching_number_invoices:
                if abs(float(prior.total_amount or 0.0) - total_amount) > 1.0:
                    risk_score += 40
                    reasons.append(f"Invoice Number Conflict: Invoice #{inv_number} already exists with a different total ({sym}{prior.total_amount:.2f} vs current {sym}{total_amount:.2f}).")
                    break

        # Rule 3: Vendor History and Abnormal Amount Analysis
        if vendor_name and db:
            v_query = db.query(Invoice).filter(Invoice.vendor_name.ilike(f"%{vendor_name}%"))
            if organization:
                v_query = v_query.filter(Invoice.organization == organization)
            vendor_invoices = v_query.all()
            if current_invoice_id:
                vendor_invoices = [inv for inv in vendor_invoices if inv.id != current_invoice_id]

            if vendor_invoices:
                amounts = [float(inv.total_amount or 0.0) for inv in vendor_invoices if inv.total_amount]
                if amounts:
                    avg_vendor_amount = sum(amounts) / len(amounts)
                    if total_amount > (avg_vendor_amount * 3.0) and total_amount > 1000.0:
                        risk_score += 35
                        reasons.append(f"Abnormal Spend Spike: Current amount ({sym}{total_amount:,.2f}) is over 3x higher than vendor '{vendor_name}' average ({sym}{avg_vendor_amount:,.2f}).")
                    elif total_amount > (avg_vendor_amount * 2.0):
                        risk_score += 15
                        reasons.append(f"Elevated Spend: Amount ({sym}{total_amount:,.2f}) is significantly above vendor average ({sym}{avg_vendor_amount:,.2f}).")

        # Rule 4: Unusually High Absolute Amount
        if total_amount > 100000.0:
            risk_score += 30
            reasons.append(f"High Value Threshold: Single invoice amount ({sym}{total_amount:,.2f}) exceeds the 100,000 high-value review threshold.")
        elif total_amount > 25000.0:
            risk_score += 15
            reasons.append(f"Substantial Value: Invoice amount ({sym}{total_amount:,.2f}) exceeds the 25,000 standard review threshold.")

        # Rule 5: Math Calculation / Tax Anomaly
        expected_total = round(subtotal + tax - discount, 2)
        if abs(expected_total - round(total_amount, 2)) > 0.10:
            risk_score += 25
            reasons.append(f"Financial Inconsistency: Calculated total ({sym}{expected_total:,.2f}) does not match billed total ({sym}{total_amount:,.2f}).")

        # Rule 6: Future Invoice Date
        if inv_date_str:
            for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
                try:
                    dt = datetime.strptime(inv_date_str, fmt)
                    days_ahead = (dt.date() - datetime.now(timezone.utc).date()).days
                    if days_ahead > 7:
                        risk_score += 30
                        reasons.append(f"Anomalous Future Date: Invoice date is {days_ahead} days in the future.")
                    break
                except ValueError:
                    pass

        # Rule 7: Missing Critical Identification (Vendor or GST)
        if not vendor_name:
            risk_score += 20
            reasons.append("Missing Vendor Identification: No vendor name detected.")
        if not gst_number:
            risk_score += 10
            reasons.append("Missing Tax Identification: No GST/VAT registration number identified.")

        # Cap score between 0 and 100
        risk_score = min(100, max(0, risk_score))

        # Risk level classification
        if risk_score >= 61:
            risk_level = "High"
        elif risk_score >= 31:
            risk_level = "Medium"
        else:
            risk_level = "Low"

        if not reasons:
            reasons.append("Low Risk: Invoice conforms to standard vendor billing rules with verified mathematics and uniqueness.")

        return risk_score, risk_level, reasons

fraud_detection_service = FraudDetectionService()
