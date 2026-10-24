import io
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database.session import init_db

client = TestClient(app)

@pytest.fixture(scope="module", autouse=True)
def setup_module():
    init_db()

def get_auth_token(email="reviewer@invoshield.ai", password="Reviewer@12345"):
    res = client.post("/api/auth/login", json={"email": email, "password": password})
    return res.json()["access_token"]

def test_invoice_upload_and_full_workflow():
    token = get_auth_token()
    headers = {"Authorization": f"Bearer {token}"}

    sample_content = b"""
    INVOICE
    Invoice Number: INV-2024-8877
    Date: 2024-09-01
    Due Date: 2024-09-30
    Vendor: Quantum Solutions LLC
    Vendor Address: 500 Enterprise Way, Silicon Valley, CA
    Customer: InvoShield Global
    GST Number: 27AABCT1332L1Z1
    PO Number: PO-4500

    Description        Qty   Price   Total
    Software License    1    1000.00 1000.00
    Support Services    1    200.00  200.00

    Subtotal: $1200.00
    Tax Amount: $120.00
    Discount: $20.00
    Total Amount: $1300.00
    """

    file_tuple = ("test_invoice.txt", io.BytesIO(sample_content), "text/plain")
    upload_res = client.post(
        "/api/invoices/upload",
        files={"file": file_tuple},
        headers=headers
    )
    assert upload_res.status_code == 201
    invoice_data = upload_res.json()
    invoice_id = invoice_data["id"]

    assert invoice_data["invoice_number"] == "INV-2024-8877"
    assert invoice_data["vendor_name"] == "Quantum Solutions LLC"
    assert invoice_data["total_amount"] == 1300.00
    assert len(invoice_data["validation_results"]) > 0
    assert "risk_score" in invoice_data

    # Test GET list
    list_res = client.get("/api/invoices?search=Quantum", headers=headers)
    assert list_res.status_code == 200
    assert list_res.json()["total"] >= 1

    # Test inline update
    put_res = client.put(
        f"/api/invoices/{invoice_id}",
        json={"vendor_name": "Quantum Solutions International LLC"},
        headers=headers
    )
    assert put_res.status_code == 200
    assert put_res.json()["vendor_name"] == "Quantum Solutions International LLC"

    # Test Segregation of Duties (SoD): self-approval must be blocked with 403
    self_approve_res = client.post(f"/api/invoices/{invoice_id}/approve", headers=headers)
    assert self_approve_res.status_code == 403

    # Test independent approval by admin succeeds
    admin_token = get_auth_token(email="admin@invoshield.ai", password="Admin@12345")
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    approve_res = client.post(f"/api/invoices/{invoice_id}/approve", headers=admin_headers)
    assert approve_res.status_code == 200
    assert approve_res.json()["status"] == "approved"

    # Test dashboard statistics
    stats_res = client.get("/api/dashboard/statistics", headers=headers)
    assert stats_res.status_code == 200
    stats = stats_res.json()
    assert stats["total_invoices"] >= 1
    assert stats["approved_invoices"] >= 1
