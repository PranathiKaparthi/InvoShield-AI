from app.database.session import SessionLocal, init_db
from app.models.entities import Invoice
from app.services.duplicate_detection_service import duplicate_detection_service
from app.services.encryption_service import encryption_service

def test_duplicate_detection_near_match():
    init_db()
    db = SessionLocal()
    try:
        # Clear invoices for clean isolation
        db.query(Invoice).filter(Invoice.invoice_number.ilike("INV-DUP-%")).delete()
        db.commit()

        # Seed an original invoice
        orig = Invoice(
            invoice_number="INV-DUP-100",
            vendor_name="Global Logistics International Inc",
            invoice_date="2024-08-01",
            total_amount=4500.00,
            gst_number=encryption_service.encrypt("29ABCDE1234F1Z5"),
            po_number="PO-9910",
            cloud_file_path="invoices/pending/orig.pdf",
            status="approved"
        )
        db.add(orig)
        db.commit()
        db.refresh(orig)

        # Create candidate near-duplicate
        candidate_data = {
            "invoice_number": "INV-DUP-100",  # Exact
            "vendor_name": "Global Logistics Intl Inc",  # Slight variation
            "invoice_date": "2024-08-01",
            "total_amount": 4500.00,  # Exact
            "gst_number": "29ABCDE1234F1Z5",  # Exact
            "po_number": "PO-9910"
        }

        score, verdict, matched_id, breakdown = duplicate_detection_service.check_duplicate(candidate_data, db)
        assert score >= 85.0
        assert verdict in ["Highly Likely Duplicate", "Possible Duplicate"]
        assert matched_id == orig.id
        assert "field_scores" in breakdown
        assert breakdown["field_scores"]["invoice_number"] == 100.0
        assert breakdown["field_scores"]["total_amount"] == 100.0
    finally:
        db.close()
