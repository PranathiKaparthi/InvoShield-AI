from app.database.session import SessionLocal, init_db
from app.models.entities import Invoice
from app.services.fraud_detection_service import fraud_detection_service

def test_fraud_anomaly_detection_high_risk():
    init_db()
    db = SessionLocal()
    try:
        # Seed prior invoices for vendor with modest average (~$500)
        for i in range(3):
            inv = Invoice(
                invoice_number=f"INV-VEND-{i}",
                vendor_name="Small Parts Corp",
                total_amount=500.00,
                cloud_file_path="test.pdf",
                status="approved"
            )
            db.add(inv)
        db.commit()

        # New invoice from same vendor for $28,000 with calculation error and future date
        high_risk_invoice = {
            "invoice_number": "INV-VEND-FRAUD",
            "vendor_name": "Small Parts Corp",
            "total_amount": 28000.00,  # > 50x vendor average
            "subtotal": 20000.00,
            "tax_amount": 1000.00,
            "discount": 0.0,  # 20000 + 1000 != 28000 (math mismatch)
            "invoice_date": "2030-01-01",  # Far in future
            "gst_number": "29ABCDE1234F1Z5"
        }

        score, level, reasons = fraud_detection_service.analyze(high_risk_invoice, duplicate_score=0.0, db=db)
        assert score >= 61
        assert level == "High"
        assert len(reasons) >= 2
        # Verify plain-language explanation includes key indicators
        joined_reasons = " ".join(reasons)
        assert "Abnormal Spend Spike" in joined_reasons or "Substantial Value" in joined_reasons
        assert "Financial Inconsistency" in joined_reasons or "Anomalous Future Date" in joined_reasons
    finally:
        db.close()
