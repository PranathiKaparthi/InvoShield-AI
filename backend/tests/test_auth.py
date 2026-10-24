import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database.session import init_db

client = TestClient(app)

@pytest.fixture(scope="module", autouse=True)
def setup_db():
    init_db()

def test_register_login_me_roundtrip():
    # 1. Register new user
    email = "test.officer@invoshield.ai"
    reg_payload = {
        "name": "Audit Officer",
        "email": email,
        "password": "Password@123",
        "confirm_password": "Password@123",
        "organization": "FinOps Corp",
        "role": "reviewer"
    }
    reg_res = client.post("/api/auth/register", json=reg_payload)
    assert reg_res.status_code in [201, 400]  # 400 if already created in prior run

    # 2. Login
    login_res = client.post("/api/auth/login", json={
        "email": email,
        "password": "Password@123"
    })
    assert login_res.status_code == 200
    login_data = login_res.json()
    assert "access_token" in login_data
    token = login_data["access_token"]
    assert login_data["user"]["role"] == "reviewer"

    # 3. GET /api/auth/me with Bearer token
    headers = {"Authorization": f"Bearer {token}"}
    me_res = client.get("/api/auth/me", headers=headers)
    assert me_res.status_code == 200
    me_data = me_res.json()
    assert me_data["email"] == email
    assert me_data["name"] == "Audit Officer"

def test_role_based_access_control():
    # Standard user login
    user_res = client.post("/api/auth/login", json={
        "email": "user@invoshield.ai",
        "password": "User@12345"
    })
    assert user_res.status_code == 200
    user_token = user_res.json()["access_token"]

    # Try accessing admin endpoint /api/admin/users
    blocked_res = client.get("/api/admin/users", headers={"Authorization": f"Bearer {user_token}"})
    assert blocked_res.status_code == 403
    assert "Access forbidden" in blocked_res.json()["detail"]

    # Admin login
    admin_res = client.post("/api/auth/login", json={
        "email": "admin@invoshield.ai",
        "password": "Admin@12345"
    })
    assert admin_res.status_code == 200
    admin_token = admin_res.json()["access_token"]

    # Admin access succeeds
    admin_access_res = client.get("/api/admin/users", headers={"Authorization": f"Bearer {admin_token}"})
    assert admin_access_res.status_code == 200
    users_list = admin_access_res.json()
    assert len(users_list) >= 1
