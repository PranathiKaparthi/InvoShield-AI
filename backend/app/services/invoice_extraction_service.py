import re
from typing import Dict, Any, List, Optional
from datetime import datetime

class InvoiceExtractionService:
    """
    Extracts structured fields from raw OCR text using regex and heuristics:
    - Invoice Number, Dates, Vendor/Customer Details, GST/Tax, PO Number, Amounts, Line Items.
    - Computes confidence score per field.
    """

    def extract(self, text: str, base_confidence: float = 0.90, demo_fallbacks: bool = True) -> Dict[str, Any]:
        """
        demo_fallbacks=True keeps the original behaviour of filling unreadable fields with sample
        values (useful for UI demos). demo_fallbacks=False leaves them empty so validation reports
        them as Missing; the InvoShield Assistant always uses this honest mode, because vendors and
        owners must never be told an invented amount, GSTIN or bank account.
        """
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        
        extracted: Dict[str, Any] = {
            "invoice_number": None,
            "invoice_date": None,
            "due_date": None,
            "vendor_name": None,
            "vendor_address": None,
            "customer_name": None,
            "customer_address": None,
            "gst_number": None,
            "tax_id": None,
            "bank_details": None,
            "po_number": None,
            "currency": "USD",
            "subtotal": 0.0,
            "tax_amount": 0.0,
            "discount": 0.0,
            "total_amount": 0.0,
            "items": [],
            "field_confidences": {},
        }

        # 1. Currency
        if "$" in text or "USD" in text:
            extracted["currency"] = "USD"
        elif "€" in text or "EUR" in text:
            extracted["currency"] = "EUR"
        elif "£" in text or "GBP" in text:
            extracted["currency"] = "GBP"
        elif "₹" in text or "INR" in text or re.search(r"\bRs\.?\s?\d", text):
            extracted["currency"] = "INR"
        extracted["field_confidences"]["currency"] = 0.95

        # 2. Invoice Number
        # Look for explicit labels: "Invoice Number:", "Invoice No:", "Invoice #:", "Inv #:"
        inv_match = re.search(r"(?:invoice\s*(?:number|no\.?|id|code)|invoice\s*#|inv\s*#)\s*[:#\-]?\s*([A-Za-z0-9\-_/]{3,30})", text, re.IGNORECASE)
        if not inv_match:
            # Look for standard INV-XXXX formatted tokens
            inv_match = re.search(r"\b(INV[-_][A-Za-z0-9\-_/]{3,25})\b", text, re.IGNORECASE)
        if not inv_match:
            inv_match = re.search(r"^\s*Invoice\s*[:#\-]\s*([A-Za-z0-9\-_/]{3,30})", text, re.IGNORECASE | re.MULTILINE)

        if inv_match:
            extracted["invoice_number"] = inv_match.group(1).strip()
            extracted["field_confidences"]["invoice_number"] = min(1.0, round(base_confidence * 0.98, 2))
        elif demo_fallbacks:
            extracted["invoice_number"] = "INV-" + datetime.now().strftime("%Y%m%d%H%M")
            extracted["field_confidences"]["invoice_number"] = 0.50

        # 3. Dates
        date_patterns = [
            r"(?:invoice\s*date|date\s*of\s*issue|issue\s*date|dated)\s*[:\-]?\s*(\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|[A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4}|\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4})",
            r"(\b\d{4}-\d{2}-\d{2}\b|\b\d{2}/\d{2}/\d{4}\b)"
        ]
        for pat in date_patterns:
            d_match = re.search(pat, text, re.IGNORECASE)
            if d_match:
                extracted["invoice_date"] = d_match.group(1).strip()
                extracted["field_confidences"]["invoice_date"] = min(1.0, round(base_confidence * 0.95, 2))
                break
        if not extracted["invoice_date"] and demo_fallbacks:
            extracted["invoice_date"] = datetime.now().strftime("%Y-%m-%d")
            extracted["field_confidences"]["invoice_date"] = 0.40

        due_match = re.search(r"(?:due\s*date|payment\s*due)\s*[:\-]?\s*(\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|[A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4})", text, re.IGNORECASE)
        if due_match:
            extracted["due_date"] = due_match.group(1).strip()
            extracted["field_confidences"]["due_date"] = min(1.0, round(base_confidence * 0.94, 2))
        elif demo_fallbacks:
            extracted["due_date"] = extracted["invoice_date"]
            extracted["field_confidences"]["due_date"] = 0.40

        # 4. Vendor Name & Address
        vendor_match = re.search(r"(?:from|vendor|seller|biller)\s*[:\-]?\s*([^\n\r]+)", text, re.IGNORECASE)
        if vendor_match:
            extracted["vendor_name"] = vendor_match.group(1).strip()
            extracted["field_confidences"]["vendor_name"] = min(1.0, round(base_confidence * 0.92, 2))
        elif len(lines) > 0:
            extracted["vendor_name"] = lines[0].strip()[:60]
            extracted["field_confidences"]["vendor_name"] = 0.70
        elif demo_fallbacks:
            extracted["vendor_name"] = "Acme Corp International"
            extracted["field_confidences"]["vendor_name"] = 0.40

        v_addr = re.search(r"(?:vendor\s*address|from\s*address)\s*[:\-]?\s*([^\n\r]+(?:\n[^\n\r]+)?)", text, re.IGNORECASE)
        if v_addr:
            extracted["vendor_address"] = v_addr.group(1).strip()
            extracted["field_confidences"]["vendor_address"] = 0.85
        elif demo_fallbacks:
            extracted["vendor_address"] = "100 Tech Enterprise Blvd, Suite 400"
            extracted["field_confidences"]["vendor_address"] = 0.50

        # 5. Customer Name & Address
        cust_match = re.search(r"(?:bill\s*to|customer|client|sold\s*to)\s*[:\-]?\s*([^\n\r]+)", text, re.IGNORECASE)
        if cust_match:
            extracted["customer_name"] = cust_match.group(1).strip()
            extracted["field_confidences"]["customer_name"] = min(1.0, round(base_confidence * 0.90, 2))
        elif demo_fallbacks:
            extracted["customer_name"] = "InvoShield Global Corp"
            extracted["field_confidences"]["customer_name"] = 0.45

        c_addr = re.search(r"(?:customer\s*address|bill\s*to\s*address|ship\s*to)\s*[:\-]?\s*([^\n\r]+)", text, re.IGNORECASE)
        if c_addr:
            extracted["customer_address"] = c_addr.group(1).strip()
            extracted["field_confidences"]["customer_address"] = 0.85
        elif demo_fallbacks:
            extracted["customer_address"] = "742 Evergreen Terrace, Sector 7"
            extracted["field_confidences"]["customer_address"] = 0.50

        # 6. GST / Tax ID / Bank Details
        gst_match = re.search(r"(?:gst(?:in)?|gst\s*number|tax\s*id|vat\s*reg|vat\s*no)\s*[:#\-]?\s*([0-9A-Z]{9,18})", text, re.IGNORECASE)
        if gst_match:
            extracted["gst_number"] = gst_match.group(1).strip()
            extracted["tax_id"] = extracted["gst_number"]
            extracted["field_confidences"]["gst_number"] = 0.95
            extracted["field_confidences"]["tax_id"] = 0.95
        elif demo_fallbacks:
            extracted["gst_number"] = "29ABCDE1234F1Z5"
            extracted["tax_id"] = "TX-99887766"
            extracted["field_confidences"]["gst_number"] = 0.50
            extracted["field_confidences"]["tax_id"] = 0.50

        bank_match = re.search(r"(?:iban|account\s*(?:no|number)|bank\s*details)\s*[:#\-]?\s*([A-Za-z0-9\s]{8,30})", text, re.IGNORECASE)
        if bank_match:
            extracted["bank_details"] = bank_match.group(1).strip()
            extracted["field_confidences"]["bank_details"] = 0.90
        elif demo_fallbacks:
            extracted["bank_details"] = "IBAN: US98CHAS0001234567890"
            extracted["field_confidences"]["bank_details"] = 0.50

        # 7. PO Number
        po_match = re.search(r"(?:po|purchase\s*order)\s*(?:no|#|number)?\s*[:#\-]?\s*([A-Za-z0-9\-_]{3,20})", text, re.IGNORECASE)
        if po_match:
            extracted["po_number"] = po_match.group(1).strip()
            extracted["field_confidences"]["po_number"] = 0.90
        elif demo_fallbacks:
            extracted["po_number"] = "PO-2024-8831"
            extracted["field_confidences"]["po_number"] = 0.50

        # 8. Financial Amounts
        def extract_amount(pattern: str) -> Optional[float]:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                val_str = match.group(1).replace(",", "").replace("$", "").replace("€", "").replace("£", "").replace("₹", "").strip()
                try:
                    return float(val_str)
                except ValueError:
                    return None
            return None

        total = extract_amount(r"\b(?:grand\s*total|total\s*amount|amount\s*due|balance\s*due|net\s*total|\btotal)\s*[:\-]?\s*(?:Rs\.?|INR)?\s*[\$€£₹]?\s*([0-9]+(?:,[0-9]{2,3})*(?:\.[0-9]{1,2})?)")
        subtotal = extract_amount(r"\b(?:sub\s*total|subtotal|net\s*amount)\s*[:\-]?\s*(?:Rs\.?|INR)?\s*[\$€£₹]?\s*([0-9]+(?:,[0-9]{2,3})*(?:\.[0-9]{1,2})?)")
        tax = extract_amount(r"\b(?:tax\s*amount|sales\s*tax|vat\s*amount|gst\s*amount|tax|gst|vat)\s*[:\-]?\s*(?:Rs\.?|INR)?\s*[\$€£₹]?\s*([0-9]+(?:,[0-9]{2,3})*(?:\.[0-9]{1,2})?)")
        discount = extract_amount(r"\b(?:discount|rebate)\s*[:\-]?\s*(?:Rs\.?|INR)?\s*[\$€£₹]?\s*([0-9]+(?:,[0-9]{2,3})*(?:\.[0-9]{1,2})?)") or 0.0

        if total is not None:
            extracted["total_amount"] = total
            extracted["field_confidences"]["total_amount"] = 0.95
        elif demo_fallbacks:
            extracted["total_amount"] = 1250.00
            extracted["field_confidences"]["total_amount"] = 0.50
        else:
            extracted["field_confidences"]["total_amount"] = 0.0

        if subtotal is not None:
            extracted["subtotal"] = subtotal
            extracted["field_confidences"]["subtotal"] = 0.92
        elif demo_fallbacks:
            extracted["subtotal"] = round(extracted["total_amount"] / 1.10, 2)
            extracted["field_confidences"]["subtotal"] = 0.50

        if tax is not None:
            extracted["tax_amount"] = tax
            extracted["field_confidences"]["tax_amount"] = 0.90
        elif demo_fallbacks:
            extracted["tax_amount"] = round(extracted["total_amount"] - extracted["subtotal"], 2)
            extracted["field_confidences"]["tax_amount"] = 0.50

        extracted["discount"] = discount
        extracted["field_confidences"]["discount"] = 0.85

        # Honest mode: derive (never invent) a missing subtotal/tax from the amounts that were read,
        # so a total-only invoice isn't reported as a maths error.
        if not demo_fallbacks and total is not None:
            if subtotal is None and tax is None:
                extracted["subtotal"] = total + discount
                extracted["field_confidences"]["subtotal"] = 0.30
            elif subtotal is None:
                extracted["subtotal"] = round(total - tax + discount, 2)
                extracted["field_confidences"]["subtotal"] = 0.30
            elif tax is None:
                extracted["tax_amount"] = round(total - subtotal + discount, 2)
                extracted["field_confidences"]["tax_amount"] = 0.30

        # 9. Line Items
        item_pattern = re.compile(r"^\s*([A-Za-z0-9\s\-_.]{4,50})\s+(\d+(?:\.\d+)?)\s+[\$€£₹]?(\d+(?:\.\d+)?)\s+[\$€£₹]?(\d+(?:\.\d+)?)\s*$", re.MULTILINE)
        matches = item_pattern.findall(text)
        line_items = []
        for desc, qty, unit_p, tot_p in matches:
            try:
                line_items.append({
                    "description": desc.strip(),
                    "quantity": float(qty),
                    "unit_price": float(unit_p),
                    "total_price": float(tot_p),
                })
            except Exception:
                continue

        if not line_items and demo_fallbacks:
            # Generate representative default line items based on subtotal
            part = round(extracted["subtotal"] / 2, 2)
            line_items = [
                {"description": "Enterprise Cloud Services & Licensing", "quantity": 1.0, "unit_price": part, "total_price": part},
                {"description": "Technical Consulting & Security Audit", "quantity": 1.0, "unit_price": round(extracted["subtotal"] - part, 2), "total_price": round(extracted["subtotal"] - part, 2)}
            ]

        extracted["items"] = line_items
        extracted["field_confidences"]["items"] = 0.88

        return extracted

invoice_extraction_service = InvoiceExtractionService()
