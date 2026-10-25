"""Regression tests for tenant isolation and self-registration rules."""
import io
import uuid

import pytest
from fastapi.testclient import TestClient

from app.database.session import init_db
from app.main import app
from app.services.fraud_detection_service import amount_thresholds

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_module():
    init_db()


def _login(email, password):
    res = client.post("/api/auth/login", json={"email": email, "password": password})
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _register(org, role="reviewer"):
    email = f"u-{uuid.uuid4().hex[:8]}@example.com"
    res = client.post("/api/auth/register", json={"name": "Test", "email": email, "password": "Password@123",
                                                  "organization": org, "role": role})
    assert res.status_code == 201, res.text
    return res.json()["user"], {"Authorization": f"Bearer {res.json()['access_token']}"}


def _upload(headers):
    body = f"Invoice Number: AC-{uuid.uuid4().hex[:6]}\nVendor: Test Vendor\nTotal Amount: $100.00\n".encode()
    res = client.post("/api/invoices/upload", files={"file": ("a.txt", io.BytesIO(body), "text/plain")},
                      headers=headers)
    assert res.status_code == 201, res.text
    return res.json()["id"]


def test_user_cannot_open_another_users_invoice():
    inv_id = _upload(_login("reviewer@invoshield.ai", "Reviewer@12345"))
    outsider = _login("user@invoshield.ai", "User@12345")
    for path in ("", "/file", "/duplicates", "/risk-analysis"):
        assert client.get(f"/api/invoices/{inv_id}{path}", headers=outsider).status_code == 404, path
    assert client.post(f"/api/invoices/{inv_id}/validate", headers=outsider).status_code == 404


def test_reviewer_cannot_touch_other_organizations_invoice():
    inv_id = _upload(_login("reviewer@invoshield.ai", "Reviewer@12345"))  # Apex FinTech Audits
    _, other = _register(f"Other Org {uuid.uuid4().hex[:6]}")             # reviewer of a new org
    assert client.get(f"/api/invoices/{inv_id}", headers=other).status_code == 404
    assert client.put(f"/api/invoices/{inv_id}", json={"vendor_name": "x"}, headers=other).status_code == 404
    assert client.post(f"/api/invoices/{inv_id}/approve", headers=other).status_code == 404
    # the admin still can
    assert client.get(f"/api/invoices/{inv_id}", headers=_login("admin@invoshield.ai", "Admin@12345")).status_code == 200


def test_cannot_self_register_as_reviewer_of_existing_company():
    user, _ = _register("Apex FinTech Audits", role="reviewer")
    assert user["role"] == "user"
    new_org_user, _ = _register(f"Brand New Co {uuid.uuid4().hex[:6]}", role="reviewer")
    assert new_org_user["role"] == "reviewer"
    admin_attempt, _ = _register(f"Another Co {uuid.uuid4().hex[:6]}", role="admin")
    assert admin_attempt["role"] == "user"


def test_rupee_thresholds_are_not_dollar_thresholds():
    review_inr, high_inr, _ = amount_thresholds("INR")
    review_usd, _, _ = amount_thresholds("USD")
    assert review_inr > review_usd * 5 and high_inr > review_inr


def test_dashboard_has_no_fake_vendors_and_scoped_activity():
    _, fresh = _register(f"Empty Co {uuid.uuid4().hex[:6]}")
    analytics = client.get("/api/dashboard/analytics", headers=fresh).json()
    assert analytics["vendor_distribution"] == []          # no invented "Apex Technologies"
    # a new organization's reviewer must not see other companies' audit events
    for event in analytics["recent_activities"]:
        assert "Apex" not in (event["details"] or "") and "admin@invoshield.ai" not in (event["details"] or "")


def test_dashboard_adds_rupees_and_dollars_correctly():
    user, h = _register(f"Mixed Co {uuid.uuid4().hex[:6]}")
    for body in (b"Invoice Number: MX-1\nVendor: A\nTotal Amount: Rs. 83,000.00\n",
                 b"Invoice Number: MX-2\nVendor: B\nTotal Amount: $1000.00\n"):
        client.post("/api/invoices/upload", files={"file": ("a.txt", io.BytesIO(body), "text/plain")}, headers=h)
    stats = client.get("/api/dashboard/statistics", headers=h).json()
    assert stats["total_amount_processed"] == 2000.0      # ₹83,000 ≈ $1,000 + $1,000
