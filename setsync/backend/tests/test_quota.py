import pytest
import hashlib
import os
import shutil
from fastapi.testclient import TestClient
from app.main import app
from app.config import settings
from app.services.storage_backend import STAGING_ROOT

def test_tenant_storage_quota_enforcement():
    client = TestClient(app)
    
    # 1. Create Org 1 and User 1
    res_org1 = client.post("/auth/organizations", json={"name": "QuotaOrgOne"})
    assert res_org1.status_code == 201
    org1_id = res_org1.json()["id"]
    
    res_user1 = client.post("/auth/users", json={
        "email": "user1@quotaorg1.com",
        "password": "password123",
        "role": "admin",
        "org_id": org1_id
    })
    assert res_user1.status_code == 201
    
    login_1 = client.post("/auth/login", json={"email": "user1@quotaorg1.com", "password": "password123"})
    assert login_1.status_code == 200
    user1_token = login_1.json()["access_token"]
    
    res_src1 = client.post("/sources/register", json={
        "name": "PC-Q1",
        "kind": "device",
        "roots": ["/root_q1"]
    }, headers={"Authorization": f"Bearer {user1_token}"})
    assert res_src1.status_code == 201
    src1_id = res_src1.json()["source"]["id"]
    
    # Override quota settings limit to a small size (e.g., 220 bytes) for testing
    original_quota = settings.TENANT_STORAGE_QUOTA_BYTES
    settings.TENANT_STORAGE_QUOTA_BYTES = 220
    
    try:
        # Create a Job/Session
        res_seed = client.post("/inventory/upload", json={
            "source_id": src1_id,
            "files": [
                {
                    "path": "/root_q1/test.xlsx",
                    "relative_path": "test.xlsx",
                    "size_bytes": 1024,
                    "mtime": "2026-07-07T12:00:00",
                    "hash_sha256": "fake_sha_q"
                }
            ]
        }, headers={"Authorization": f"Bearer {user1_token}"})
        
        res_job1 = client.post("/actions/copy", json={
            "file_path": "test.xlsx",
            "source": src1_id,
            "destination": src1_id,
            "triggered_by": "ui"
        }, headers={"Authorization": f"Bearer {user1_token}"})
        assert res_job1.status_code == 200
        session_id = res_job1.json()["id"]
        
        # Initialize upload
        res_init = client.post("/transfer/init", json={
            "session_id": session_id,
            "total_chunks": 3,
            "chunk_size": 20,
            "file_sha256": "dummy_sha_q",
            "file_path": "test.xlsx"
        }, headers={"Authorization": f"Bearer {user1_token}"})
        assert res_init.status_code == 200
        
        # Upload chunk 0: 20 bytes (Total Org 1: 20 bytes -> Under 50 bytes)
        chunk0 = b"01234567890123456789"
        sha0 = hashlib.sha256(chunk0).hexdigest()
        res_u0 = client.post(
            f"/transfer/{session_id}/chunk/0",
            content=chunk0,
            headers={"Authorization": f"Bearer {user1_token}", "X-Chunk-SHA256": sha0}
        )
        assert res_u0.status_code == 200
        
        # Upload chunk 1: 20 bytes (Total Org 1: 40 bytes -> Under 50 bytes)
        chunk1 = b"abcdefghijklmnopqrst"
        sha1 = hashlib.sha256(chunk1).hexdigest()
        res_u1 = client.post(
            f"/transfer/{session_id}/chunk/1",
            content=chunk1,
            headers={"Authorization": f"Bearer {user1_token}", "X-Chunk-SHA256": sha1}
        )
        assert res_u1.status_code == 200
        
        # Upload chunk 2: 20 bytes (Total Org 1 projected: 60 bytes -> Over 50 bytes quota!)
        chunk2 = b"xyzxyzxyzxyzxyzxyzxy"
        sha2 = hashlib.sha256(chunk2).hexdigest()
        res_u2 = client.post(
            f"/transfer/{session_id}/chunk/2",
            content=chunk2,
            headers={"Authorization": f"Bearer {user1_token}", "X-Chunk-SHA256": sha2}
        )
        # Should be rejected with HTTP 413
        assert res_u2.status_code == 413
        assert "quota exceeded" in res_u2.json()["detail"].lower()
        
        # 2. Verify another organization is not impacted by Org 1's usage (Org Isolation)
        res_org2 = client.post("/auth/organizations", json={"name": "QuotaOrgTwo"})
        assert res_org2.status_code == 201
        org2_id = res_org2.json()["id"]
        
        res_user2 = client.post("/auth/users", json={
            "email": "user2@quotaorg2.com",
            "password": "password123",
            "role": "admin",
            "org_id": org2_id
        })
        assert res_user2.status_code == 201
        
        login_2 = client.post("/auth/login", json={"email": "user2@quotaorg2.com", "password": "password123"})
        user2_token = login_2.json()["access_token"]
        
        res_src2 = client.post("/sources/register", json={
            "name": "PC-Q2",
            "kind": "device",
            "roots": ["/root_q2"]
        }, headers={"Authorization": f"Bearer {user2_token}"})
        src2_id = res_src2.json()["source"]["id"]
        
        res_seed2 = client.post("/inventory/upload", json={
            "source_id": src2_id,
            "files": [
                {
                    "path": "/root_q2/doc.xlsx",
                    "relative_path": "doc.xlsx",
                    "size_bytes": 500,
                    "mtime": "2026-07-07T12:00:00",
                    "hash_sha256": "fake_sha_q2"
                }
            ]
        }, headers={"Authorization": f"Bearer {user2_token}"})
        
        res_job2 = client.post("/actions/copy", json={
            "file_path": "doc.xlsx",
            "source": src2_id,
            "destination": src2_id,
            "triggered_by": "ui"
        }, headers={"Authorization": f"Bearer {user2_token}"})
        session_id_2 = res_job2.json()["id"]
        
        res_init2 = client.post("/transfer/init", json={
            "session_id": session_id_2,
            "total_chunks": 2,
            "chunk_size": 20,
            "file_sha256": "dummy_sha_q2",
            "file_path": "doc.xlsx"
        }, headers={"Authorization": f"Bearer {user2_token}"})
        assert res_init2.status_code == 200
        
        # Org 2 uploads chunk 0: 20 bytes (Total Org 2: 20 bytes -> Under 50 bytes)
        # Even though Org 1's usage is 40 bytes, Org 2 should succeed!
        res_u2_0 = client.post(
            f"/transfer/{session_id_2}/chunk/0",
            content=chunk0,
            headers={"Authorization": f"Bearer {user2_token}", "X-Chunk-SHA256": sha0}
        )
        assert res_u2_0.status_code == 200
        
    finally:
        # Restore quota config
        settings.TENANT_STORAGE_QUOTA_BYTES = original_quota
        # Cleanup staging directories
        if (STAGING_ROOT / org1_id).exists():
            shutil.rmtree(STAGING_ROOT / org1_id, ignore_errors=True)
        if 'org2_id' in locals() and (STAGING_ROOT / org2_id).exists():
            shutil.rmtree(STAGING_ROOT / org2_id, ignore_errors=True)
