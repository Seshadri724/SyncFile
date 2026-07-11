import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.config import settings

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c

def test_enterprise_multi_tenancy_rbac_fleet_decommission(client):
    # 1. Create Organization
    res_org = client.post("/auth/organizations", json={"name": "Test Corp"})
    assert res_org.status_code == 201
    org_id = res_org.json()["id"]

    # 2. Create Users (viewer, admin)
    res_viewer = client.post("/auth/users", json={
        "email": "viewer@testcorp.com",
        "password": "password123",
        "role": "viewer",
        "org_id": org_id
    })
    assert res_viewer.status_code == 201

    res_admin = client.post("/auth/users", json={
        "email": "admin@testcorp.com",
        "password": "password123",
        "role": "admin",
        "org_id": org_id
    })
    assert res_admin.status_code == 201

    # 3. Login users to get tokens
    login_viewer = client.post("/auth/login", json={
        "email": "viewer@testcorp.com",
        "password": "password123"
    })
    assert login_viewer.status_code == 200
    viewer_token = login_viewer.json()["access_token"]
    viewer_headers = {"Authorization": f"Bearer {viewer_token}"}

    login_admin = client.post("/auth/login", json={
        "email": "admin@testcorp.com",
        "password": "password123"
    })
    assert login_admin.status_code == 200
    admin_token = login_admin.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # 4. Verify RBAC constraints
    # Viewer cannot register sources
    res_fail = client.post("/sources/register", json={
        "name": "Source A", "kind": "device", "roots": ["/a"]
    }, headers=viewer_headers)
    assert res_fail.status_code == 403

    # Admin registers Source A and Source B
    res_a = client.post("/sources/register", json={
        "name": "Source A", "kind": "device", "roots": ["/a"]
    }, headers=admin_headers)
    assert res_a.status_code == 201
    source_a = res_a.json()["source"]
    agent_a_key = res_a.json()["agent_key"]

    res_b = client.post("/sources/register", json={
        "name": "Source B", "kind": "device", "roots": ["/b"]
    }, headers=admin_headers)
    assert res_b.status_code == 201
    source_b = res_b.json()["source"]
    agent_b_key = res_b.json()["agent_key"]

    # 5. Upload file inventories (satisfies unique / PII checks)
    # Source A files: 1 unique.txt, 1 tax_form.pdf (PII), 1 shared.png
    payload_a = {
        "source_id": source_a["id"],
        "files": [
            {"path": "/a/unique.txt", "relative_path": "unique.txt", "size_bytes": 100, "mtime": "2026-07-10T12:00:00", "hash_sha256": "hash1"},
            {"path": "/a/tax_form.pdf", "relative_path": "tax_form.pdf", "size_bytes": 200, "mtime": "2026-07-10T12:00:00", "hash_sha256": "hash2"},
            {"path": "/a/shared.png", "relative_path": "shared.png", "size_bytes": 300, "mtime": "2026-07-10T12:00:00", "hash_sha256": "hash3"}
        ]
    }
    headers_agent_a = {
        "X-SetSync-Source-Id": source_a["id"],
        "X-SetSync-Agent-Key": agent_a_key
    }
    client.post("/inventory/upload", json=payload_a, headers=headers_agent_a)

    # Source B files: only shared.png
    payload_b = {
        "source_id": source_b["id"],
        "files": [
            {"path": "/b/shared.png", "relative_path": "shared.png", "size_bytes": 300, "mtime": "2026-07-10T12:00:00", "hash_sha256": "hash3"}
        ]
    }
    headers_agent_b = {
        "X-SetSync-Source-Id": source_b["id"],
        "X-SetSync-Agent-Key": agent_b_key
    }
    client.post("/inventory/upload", json=payload_b, headers=headers_agent_b)

    # 6. Verify Fleet Dashboard
    res_fleet = client.get("/analysis/fleet", headers=viewer_headers)
    assert res_fleet.status_code == 200
    fleet_data = res_fleet.json()
    assert fleet_data["total_sources"] == 2
    assert fleet_data["total_files"] == 4
    assert fleet_data["total_bytes"] == 900
    assert fleet_data["unique_files_count"] == 2  # unique.txt and tax_form.pdf
    assert fleet_data["unique_files_bytes"] == 300

    # 7. Verify PII Governance Scanning
    res_gov = client.get("/analysis/governance", headers=viewer_headers)
    assert res_gov.status_code == 200
    gov_data = res_gov.json()
    assert gov_data["total_flagged_files"] == 1
    assert gov_data["flagged_files"][0]["relative_path"] == "tax_form.pdf"
    assert "Tax" in gov_data["flagged_files"][0]["flag_reason"]

    # 8. Verify Safe Decommissioning Blocker
    # Viewer tries to decommission -> should fail (403)
    res_dec_fail1 = client.post(f"/sources/{source_a['id']}/decommission", headers=viewer_headers)
    assert res_dec_fail1.status_code == 403

    # Admin tries to decommission Source A -> should fail (400) because files are not safe
    res_dec_fail2 = client.post(f"/sources/{source_a['id']}/decommission", headers=admin_headers)
    assert res_dec_fail2.status_code == 400
    detail = res_dec_fail2.json()["detail"]
    assert "Decommission Blocked" in detail["error"]
    assert len(detail["unique_files"]) == 2

    # Simulate replicating / sync'ing unique.txt and tax_form.pdf to Source B
    payload_b_new = {
        "source_id": source_b["id"],
        "files": [
            {"path": "/b/shared.png", "relative_path": "shared.png", "size_bytes": 300, "mtime": "2026-07-10T12:00:00", "hash_sha256": "hash3"},
            {"path": "/b/unique.txt", "relative_path": "unique.txt", "size_bytes": 100, "mtime": "2026-07-10T12:00:00", "hash_sha256": "hash1"},
            {"path": "/b/tax_form.pdf", "relative_path": "tax_form.pdf", "size_bytes": 200, "mtime": "2026-07-10T12:00:00", "hash_sha256": "hash2"}
        ]
    }
    client.post("/inventory/upload", json=payload_b_new, headers=headers_agent_b)

    # Now decommissioning Source A should succeed
    res_dec_ok = client.post(f"/sources/{source_a['id']}/decommission", headers=admin_headers)
    assert res_dec_ok.status_code == 200
    res_data = res_dec_ok.json()
    assert res_data["status"] == "decommissioned"
    assert "Certificate" in res_data["certificate"]
