from typing import Dict, Any, Tuple, Optional
from rapidfuzz import fuzz
from sqlalchemy.orm import Session
from app.models.entities import Invoice
from app.services.encryption_service import encryption_service

class DuplicateDetectionService:
    """
    RapidFuzz Duplicate Detection Service:
    Compares candidate invoice against existing invoices across:
    - Invoice Number, Vendor Name, Invoice Date, Total Amount, GST Number, PO Number.
    Verdicts:
      90-100% -> Highly Likely Duplicate
      75-89%  -> Possible Duplicate
      <75%    -> No Significant Duplicate
    """

    def check_duplicate(self, current_invoice_data: Dict[str, Any], db: Session, exclude_id: Optional[int] = None, organization: Optional[str] = None) -> Tuple[float, str, Optional[int], Dict[str, Any]]:
        query = db.query(Invoice)
        if organization:
            query = query.filter(Invoice.organization == organization)
        if exclude_id:
            query = query.filter(Invoice.id != exclude_id)
        existing_invoices = query.all()

        if not existing_invoices:
            return 0.0, "No Significant Duplicate", None, {}

        highest_score = 0.0
        best_match_id = None
        best_breakdown: Dict[str, Any] = {}

        curr_inv_num = str(current_invoice_data.get("invoice_number") or "").strip().lower()
        curr_vendor = str(current_invoice_data.get("vendor_name") or "").strip().lower()
        curr_date = str(current_invoice_data.get("invoice_date") or "").strip()
        curr_amount = float(current_invoice_data.get("total_amount") or 0.0)
        curr_gst = str(current_invoice_data.get("gst_number") or "").strip().lower()
        curr_po = str(current_invoice_data.get("po_number") or "").strip().lower()

        for prev in existing_invoices:
            prev_inv_num = str(prev.invoice_number or "").strip().lower()
            prev_vendor = str(prev.vendor_name or "").strip().lower()
            prev_date = str(prev.invoice_date or "").strip()
            prev_amount = float(prev.total_amount or 0.0)
            prev_gst = str(encryption_service.decrypt(prev.gst_number) or "").strip().lower()
            prev_po = str(prev.po_number or "").strip().lower()

            # Field similarity scores (0 - 100)
            score_inv_num = fuzz.ratio(curr_inv_num, prev_inv_num) if curr_inv_num and prev_inv_num else 0.0
            score_vendor = fuzz.token_sort_ratio(curr_vendor, prev_vendor) if curr_vendor and prev_vendor else 0.0
            score_date = 100.0 if (curr_date and prev_date and curr_date == prev_date) else 0.0

            # Amount similarity
            if curr_amount > 0 and prev_amount > 0:
                diff_ratio = abs(curr_amount - prev_amount) / max(curr_amount, prev_amount)
                if diff_ratio == 0:
                    score_amount = 100.0
                elif diff_ratio < 0.02:
                    score_amount = 90.0
                elif diff_ratio < 0.05:
                    score_amount = 75.0
                elif diff_ratio < 0.15:
                    score_amount = 50.0
                else:
                    score_amount = 0.0
            else:
                score_amount = 0.0

            score_gst = fuzz.ratio(curr_gst, prev_gst) if curr_gst and prev_gst else 0.0
            score_po = fuzz.ratio(curr_po, prev_po) if curr_po and prev_po else 0.0

            # Weighted composite score
            # Invoice Num: 30%, Vendor: 25%, Amount: 25%, GST: 10%, PO: 5%, Date: 5%
            composite = (
                (score_inv_num * 0.30) +
                (score_vendor * 0.25) +
                (score_amount * 0.25) +
                (score_gst * 0.10) +
                (score_po * 0.05) +
                (score_date * 0.05)
            )

            # Strong indicator: Exact same invoice number & vendor name
            if score_inv_num == 100.0 and score_vendor >= 90.0:
                composite = max(composite, 95.0)

            composite = round(composite, 1)

            if composite > highest_score:
                highest_score = composite
                best_match_id = prev.id
                best_breakdown = {
                    "matched_invoice_id": prev.id,
                    "matched_invoice_number": prev.invoice_number,
                    "matched_vendor": prev.vendor_name,
                    "matched_total_amount": prev.total_amount,
                    "matched_date": prev.invoice_date,
                    "matched_gst": prev_gst,
                    "field_scores": {
                        "invoice_number": round(score_inv_num, 1),
                        "vendor_name": round(score_vendor, 1),
                        "total_amount": round(score_amount, 1),
                        "gst_number": round(score_gst, 1),
                        "po_number": round(score_po, 1),
                        "invoice_date": round(score_date, 1),
                    }
                }

        # Determine verdict
        if highest_score >= 90.0:
            status = "Highly Likely Duplicate"
        elif highest_score >= 75.0:
            status = "Possible Duplicate"
        else:
            status = "No Significant Duplicate"

        return highest_score, status, best_match_id, best_breakdown

duplicate_detection_service = DuplicateDetectionService()
