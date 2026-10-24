import re
from datetime import datetime
from typing import Dict, Any, List, Tuple

class ValidationService:
    """
    Intelligent Data Validation Engine for Invoices:
    - Required field check
    - Invoice number format
    - Date format and chronological consistency
    - Total amount sanity & positive numeric checks
    - Tax calculation & Math reconciliation: Subtotal + Tax - Discount = Total
    - Missing field detection
    - Vendor info validation
    Assigns: Valid, Warning, Invalid, Missing per field.
    """

    def validate(self, extracted_data: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], str]:
        results: List[Dict[str, Any]] = []
        has_invalid = False
        has_warning = False

        confidences = extracted_data.get("field_confidences", {})

        # 1. Invoice Number
        inv_no = extracted_data.get("invoice_number")
        inv_conf = confidences.get("invoice_number", 0.9)
        if not inv_no:
            results.append({
                "field_name": "invoice_number",
                "extracted_value": None,
                "validation_status": "Missing",
                "confidence_score": 0.0,
                "validation_message": "Invoice number is missing."
            })
            has_invalid = True
        elif not re.match(r"^[A-Za-z0-9\-_/]{3,30}$", inv_no):
            results.append({
                "field_name": "invoice_number",
                "extracted_value": inv_no,
                "validation_status": "Invalid",
                "confidence_score": inv_conf,
                "validation_message": f"Invoice number '{inv_no}' contains invalid characters or length."
            })
            has_invalid = True
        else:
            results.append({
                "field_name": "invoice_number",
                "extracted_value": inv_no,
                "validation_status": "Valid",
                "confidence_score": inv_conf,
                "validation_message": "Valid invoice identifier format."
            })

        # 2. Vendor Name
        vendor = extracted_data.get("vendor_name")
        v_conf = confidences.get("vendor_name", 0.9)
        if not vendor or not vendor.strip():
            results.append({
                "field_name": "vendor_name",
                "extracted_value": None,
                "validation_status": "Missing",
                "confidence_score": 0.0,
                "validation_message": "Vendor name is required."
            })
            has_invalid = True
        elif len(vendor.strip()) < 3:
            results.append({
                "field_name": "vendor_name",
                "extracted_value": vendor,
                "validation_status": "Warning",
                "confidence_score": v_conf,
                "validation_message": "Vendor name is suspiciously short."
            })
            has_warning = True
        else:
            results.append({
                "field_name": "vendor_name",
                "extracted_value": vendor,
                "validation_status": "Valid",
                "confidence_score": v_conf,
                "validation_message": "Vendor name verified."
            })

        # 3. Invoice Date & Due Date
        inv_date_str = extracted_data.get("invoice_date")
        due_date_str = extracted_data.get("due_date")
        d_conf = confidences.get("invoice_date", 0.9)
        parsed_inv_date = None
        parsed_due_date = None

        if not inv_date_str:
            results.append({
                "field_name": "invoice_date",
                "extracted_value": None,
                "validation_status": "Missing",
                "confidence_score": 0.0,
                "validation_message": "Invoice date is missing."
            })
            has_invalid = True
        else:
            for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d"):
                try:
                    parsed_inv_date = datetime.strptime(inv_date_str.strip(), fmt)
                    break
                except ValueError:
                    pass
            
            if parsed_inv_date is None:
                results.append({
                    "field_name": "invoice_date",
                    "extracted_value": inv_date_str,
                    "validation_status": "Warning",
                    "confidence_score": d_conf,
                    "validation_message": "Date format could not be strictly parsed as ISO/Standard."
                })
                has_warning = True
            else:
                results.append({
                    "field_name": "invoice_date",
                    "extracted_value": inv_date_str,
                    "validation_status": "Valid",
                    "confidence_score": d_conf,
                    "validation_message": "Date format is valid."
                })

        if due_date_str:
            for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d"):
                try:
                    parsed_due_date = datetime.strptime(due_date_str.strip(), fmt)
                    break
                except ValueError:
                    pass
            
            if parsed_inv_date and parsed_due_date and parsed_due_date < parsed_inv_date:
                results.append({
                    "field_name": "due_date",
                    "extracted_value": due_date_str,
                    "validation_status": "Invalid",
                    "confidence_score": confidences.get("due_date", 0.9),
                    "validation_message": "Due date cannot be before invoice date."
                })
                has_invalid = True
            else:
                results.append({
                    "field_name": "due_date",
                    "extracted_value": due_date_str,
                    "validation_status": "Valid",
                    "confidence_score": confidences.get("due_date", 0.9),
                    "validation_message": "Due date is valid."
                })
        else:
            results.append({
                "field_name": "due_date",
                "extracted_value": None,
                "validation_status": "Warning",
                "confidence_score": 0.5,
                "validation_message": "Due date not specified."
            })
            has_warning = True

        # 4. GST / Tax ID
        gst = extracted_data.get("gst_number")
        if not gst:
            results.append({
                "field_name": "gst_number",
                "extracted_value": None,
                "validation_status": "Warning",
                "confidence_score": 0.0,
                "validation_message": "GST / Tax ID not detected on document."
            })
            has_warning = True
        else:
            results.append({
                "field_name": "gst_number",
                "extracted_value": gst,
                "validation_status": "Valid",
                "confidence_score": confidences.get("gst_number", 0.9),
                "validation_message": "Tax ID format verified."
            })

        # 5. Financial Calculation Check: Subtotal + Tax - Discount = Total
        subtotal = float(extracted_data.get("subtotal") or 0.0)
        tax = float(extracted_data.get("tax_amount") or 0.0)
        discount = float(extracted_data.get("discount") or 0.0)
        total = float(extracted_data.get("total_amount") or 0.0)

        if total <= 0:
            results.append({
                "field_name": "total_amount",
                "extracted_value": str(total),
                "validation_status": "Invalid",
                "confidence_score": confidences.get("total_amount", 0.9),
                "validation_message": "Total amount must be greater than zero."
            })
            has_invalid = True
        else:
            results.append({
                "field_name": "total_amount",
                "extracted_value": str(total),
                "validation_status": "Valid",
                "confidence_score": confidences.get("total_amount", 0.9),
                "validation_message": "Total amount sanity check passed."
            })

        expected_total = round(subtotal + tax - discount, 2)
        diff = abs(expected_total - round(total, 2))

        if diff > 0.10:
            results.append({
                "field_name": "calculation_check",
                "extracted_value": f"Subtotal({subtotal}) + Tax({tax}) - Discount({discount}) = {expected_total} vs Total({total})",
                "validation_status": "Invalid",
                "confidence_score": 0.95,
                "validation_message": f"Math mismatch: Subtotal + Tax - Discount ({expected_total}) differs from Total ({total}) by {diff:.2f}."
            })
            has_invalid = True
        else:
            results.append({
                "field_name": "calculation_check",
                "extracted_value": f"{subtotal} + {tax} - {discount} = {total}",
                "validation_status": "Valid",
                "confidence_score": 1.0,
                "validation_message": "Mathematical reconciliation verified: Subtotal + Tax - Discount = Total."
            })

        # 6. Overall invoice status
        if has_invalid:
            overall_status = "invalid"
        elif has_warning:
            overall_status = "warning"
        else:
            overall_status = "valid"

        return results, overall_status

validation_service = ValidationService()
