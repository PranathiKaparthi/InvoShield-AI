import pytest
from app.services.encryption_service import encryption_service
from app.database.session import SessionLocal, init_db
from app.models.entities import Invoice

def test_aes256_gcm_encrypt_decrypt_roundtrip():
    sensitive_gst = "27AAAPL1234C1ZV"
    sensitive_tax = "TX-9988776655"
    sensitive_bank = "IBAN: US890001234567890123"

    encrypted_gst = encryption_service.encrypt(sensitive_gst)
    encrypted_tax = encryption_service.encrypt(sensitive_tax)
    encrypted_bank = encryption_service.encrypt(sensitive_bank)

    # Assert that stored value is NOT plaintext
    assert encrypted_gst != sensitive_gst
    assert encrypted_tax != sensitive_tax
    assert encrypted_bank != sensitive_bank
    assert sensitive_gst not in encrypted_gst

    # Assert that decrypting returns exact original
    assert encryption_service.decrypt(encrypted_gst) == sensitive_gst
    assert encryption_service.decrypt(encrypted_tax) == sensitive_tax
    assert encryption_service.decrypt(encrypted_bank) == sensitive_bank

def test_database_row_stores_encrypted_data():
    init_db()
    db = SessionLocal()
    try:
        raw_gst = "33BBBPK9876D1Z1"
        encrypted_gst = encryption_service.encrypt(raw_gst)

        invoice = Invoice(
            invoice_number="INV-ENC-001",
            vendor_name="Encrypted Vendor LLC",
            gst_number=encrypted_gst,
            cloud_file_path="invoices/pending/test.pdf",
            status="pending_review",
            total_amount=1500.00
        )
        db.add(invoice)
        db.commit()
        db.refresh(invoice)

        # Query direct database row (raw column value in DB)
        saved_row = db.query(Invoice).filter(Invoice.id == invoice.id).first()
        assert saved_row.gst_number is not None
        assert saved_row.gst_number != raw_gst
        assert raw_gst not in saved_row.gst_number
        # Decrypt manually to verify integrity
        assert encryption_service.decrypt(saved_row.gst_number) == raw_gst
    finally:
        db.close()
