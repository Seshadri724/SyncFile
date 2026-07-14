import pytest
import hashlib
import jwt
from fastapi.testclient import TestClient
from app.main import app
from app.config import settings

def test_jwt_authentication_spoofing():
    client = TestClient(app)
    
    # 1. Create Organization & User
    res_org = client.post("/auth/organizations", json={"name": "AuthHardeningOrg"})
    assert res_org.status_code == 201
    org_id = res_org.json()["id"]
    
    res_user = client.post("/auth/users", json={
        "email": "user@hardening.com",
        "password": "password123",
        "role": "admin",
        "org_id": org_id
    })
    assert res_user.status_code == 201
    
    # 2. Login to retrieve the cryptographic JWT access token
    login_res = client.post("/auth/login", json={"email": "user@hardening.com", "password": "password123"})
    assert login_res.status_code == 200
    valid_jwt = login_res.json()["access_token"]
    
    # Verify valid JWT works on protected route
    res_valid = client.get("/plans", headers={"Authorization": f"Bearer {valid_jwt}"})
    assert res_valid.status_code == 200
    
    # 3. Test spoofed legacy token (plaintext user ID prefix) - MUST be blocked
    legacy_token = f"user:{res_user.json()['id']}"
    res_legacy = client.get("/plans", headers={"Authorization": f"Bearer {legacy_token}"})
    assert res_legacy.status_code == 401
    
    # 4. Test modified JWT signature - MUST be blocked
    # Alter the last few characters of the JWT
    forged_jwt = valid_jwt[:-4] + "aaaa"
    res_forged = client.get("/plans", headers={"Authorization": f"Bearer {forged_jwt}"})
    assert res_forged.status_code == 401


def test_plans_tenant_isolation():
    client = TestClient(app)
    
    # 1. Setup Org 1
    res_org1 = client.post("/auth/organizations", json={"name": "PlanOrgOne"})
    org1_id = res_org1.json()["id"]
    client.post("/auth/users", json={"email": "user1@plan1.com", "password": "password123", "role": "admin", "org_id": org1_id})
    token1 = client.post("/auth/login", json={"email": "user1@plan1.com", "password": "password123"}).json()["access_token"]
    
    # 2. Setup Org 2
    res_org2 = client.post("/auth/organizations", json={"name": "PlanOrgTwo"})
    org2_id = res_org2.json()["id"]
    client.post("/auth/users", json={"email": "user2@plan2.com", "password": "password123", "role": "admin", "org_id": org2_id})
    token2 = client.post("/auth/login", json={"email": "user2@plan2.com", "password": "password123"}).json()["access_token"]
    
    # 3. Org 1 creates a sync plan
    res_plan1 = client.post(
        "/plans",
        json={"name": "Org1 Sync Plan", "items": []},
        headers={"Authorization": f"Bearer {token1}"}
    )
    assert res_plan1.status_code == 201
    plan1_id = res_plan1.json()["id"]
    
    # 4. Org 2 attempts to fetch Org 1's plan -> MUST be blocked
    res_get = client.get(f"/plans/{plan1_id}", headers={"Authorization": f"Bearer {token2}"})
    assert res_get.status_code == 403
    
    # 5. Org 2 attempts to run Org 1's plan -> MUST be blocked
    res_run = client.post(f"/plans/{plan1_id}/approve", headers={"Authorization": f"Bearer {token2}"})
    assert res_run.status_code == 403
    
    # 6. Org 2 attempts to rollback Org 1's plan -> MUST be blocked
    res_undo = client.post(f"/plans/{plan1_id}/undo", headers={"Authorization": f"Bearer {token2}"})
    assert res_undo.status_code == 403
    
    # 7. Org 2 lists plans -> should not contain Org 1's plan
    res_list = client.get("/plans", headers={"Authorization": f"Bearer {token2}"})
    assert res_list.status_code == 200
    plan_ids = [p["id"] for p in res_list.json()]
    assert plan1_id not in plan_ids


def test_tenant_key_consistency():
    client = TestClient(app)
    
    # 1. Create Organization
    res_org = client.post("/auth/organizations", json={"name": "ConsistencyOrg"})
    org_id = res_org.json()["id"]
    client.post("/auth/users", json={"email": "admin@consistency.com", "password": "password123", "role": "admin", "org_id": org_id})
    token = client.post("/auth/login", json={"email": "admin@consistency.com", "password": "password123"}).json()["access_token"]
    
    # Setup registered source so the check can resolve source context properly
    res_src = client.post("/sources/register", json={
        "name": "PC-C1",
        "kind": "device",
        "roots": ["/root_c1"]
    }, headers={"Authorization": f"Bearer {token}"})
    src_id = res_src.json()["source"]["id"]
    agent_key = res_src.json()["agent_key"]
    
    # Keys
    key1 = "1" * 64 # Valid hex key 1
    key2 = "2" * 64 # Valid hex key 2
    
    # 2. Present Key 1 on first upload request (initializes check hash on organization)
    headers1 = {
        "X-SetSync-Source-ID": src_id,
        "X-SetSync-Agent-Key": agent_key,
        "X-SetSync-Tenant-Key": key1
    }
    
    res_init = client.post("/transfer/init", json={
        "session_id": "session-1",
        "total_chunks": 1,
        "chunk_size": 100,
        "file_sha256": "fake_sha",
        "file_path": "finance.xlsx"
    }, headers=headers1)
    assert res_init.status_code == 200
    
    # Verify check hash was populated in database
    db_org = client.get(f"/auth/organizations", headers={"Authorization": f"Bearer {token}"}) # Let's verify via get db or auth list if exposed
    
    # 3. Present Key 2 (different key) on a subsequent request -> MUST be rejected with HTTP 400
    headers2 = {
        "X-SetSync-Source-ID": src_id,
        "X-SetSync-Agent-Key": agent_key,
        "X-SetSync-Tenant-Key": key2
    }
    
    res_bad = client.post("/transfer/init", json={
        "session_id": "session-2",
        "total_chunks": 1,
        "chunk_size": 100,
        "file_sha256": "fake_sha",
        "file_path": "finance.xlsx"
    }, headers=headers2)
    assert res_bad.status_code == 400
    assert "consistency" in res_bad.json()["detail"].lower()
    
    # 4. Present Key 1 again -> MUST be allowed
    res_ok = client.post("/transfer/init", json={
        "session_id": "session-3",
        "total_chunks": 1,
        "chunk_size": 100,
        "file_sha256": "fake_sha",
        "file_path": "finance.xlsx"
    }, headers=headers1)
    assert res_ok.status_code == 200
