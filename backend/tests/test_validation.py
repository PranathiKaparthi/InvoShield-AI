from app.services.validation_service import validation_service

def test_validation_math_reconciliation_pass():
    valid_payload = {
        "invoice_number": "INV-2024-9001",
        "vendor_name": "Apex Cloud Systems",
        "invoice_date": "2024-10-15",
        "due_date": "2024-11-15",
        "subtotal": 1000.0,
        "tax_amount": 100.0,
        "discount": 50.0,
        "total_amount": 1050.0,  # 1000 + 100 - 50 = 1050.0
        "gst_number": "27AAAPL1234C1ZV",
        "field_confidences": {"invoice_number": 0.98, "total_amount": 0.95}
    }

    results, overall = validation_service.validate(valid_payload)
    assert overall == "valid"
    calc_result = next((r for r in results if r["field_name"] == "calculation_check"), None)
    assert calc_result is not None
    assert calc_result["validation_status"] == "Valid"

def test_validation_math_mismatch_fails():
    invalid_math_payload = {
        "invoice_number": "INV-2024-9002",
        "vendor_name": "Apex Cloud Systems",
        "invoice_date": "2024-10-15",
        "due_date": "2024-11-15",
        "subtotal": 1000.0,
        "tax_amount": 100.0,
        "discount": 50.0,
        "total_amount": 2500.0,  # Incorrect!
        "gst_number": "27AAAPL1234C1ZV"
    }

    results, overall = validation_service.validate(invalid_math_payload)
    assert overall == "invalid"
    calc_result = next((r for r in results if r["field_name"] == "calculation_check"), None)
    assert calc_result is not None
    assert calc_result["validation_status"] == "Invalid"
    assert "Math mismatch" in calc_result["validation_message"]
