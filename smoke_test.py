import sys
import os

# Add backend directory to sys.path
backend_dir = os.path.join(os.path.dirname(__file__), 'backend')
sys.path.insert(0, backend_dir)

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def run_smoke_test():
    print("--- 1. Testing GET /api/health ---")
    health_res = client.get("/api/health")
    print(f"Status Code: {health_res.status_code}")
    print(f"Response: {health_res.json()}")
    assert health_res.status_code == 200
    assert health_res.json()["status"] in ["healthy", "degraded"]

    print("\n--- 2. Testing POST /api/auth/login (Admin) ---")
    login_res = client.post("/api/auth/login", json={
        "email": "admin@invoshield.ai",
        "password": "Admin@12345"
    })
    print(f"Status Code: {login_res.status_code}")
    login_data = login_res.json()
    print(f"User: {login_data['user']['email']}, Role: {login_data['user']['role']}")
    assert login_res.status_code == 200
    token = login_data["access_token"]

    print("\n--- 3. Testing GET /api/auth/me (with JWT Bearer) ---")
    me_res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    print(f"Status Code: {me_res.status_code}")
    print(f"Profile: {me_res.json()}")
    assert me_res.status_code == 200

    print("\n--- 4. Testing GET /api/dashboard/statistics ---")
    stats_res = client.get("/api/dashboard/statistics", headers={"Authorization": f"Bearer {token}"})
    print(f"Status Code: {stats_res.status_code}")
    print(f"Stats: {stats_res.json()}")
    assert stats_res.status_code == 200

    print("\n--- 5. Testing GET /api/invoices ---")
    inv_res = client.get("/api/invoices", headers={"Authorization": f"Bearer {token}"})
    print(f"Status Code: {inv_res.status_code}")
    print(f"Invoices count: {inv_res.json()['total']}")
    assert inv_res.status_code == 200

    print("\nALL SMOKE TEST CHECKS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    run_smoke_test()
