import pytest
import os
import shutil
import hashlib
from fastapi.testclient import TestClient
from app.main import app
from app.config import settings
from app.services.chunked_transfer import STAGING_ROOT

def test_tenant_sandbox_isolation():
    client = TestClient(app)
    
    # 1. Create Org 1
    res_org1 = client.post("/auth/organizations", json={"name": "OrgOne"})
    assert res_org1.status_code == 201
    org1_id = res_org1.json()["id"]
    
    # Create User 1
    res_user1 = client.post("/auth/users", json={
        "email": "user1@org1.com",
        "password": "password123",
        "role": "admin",
        "org_id": org1_id
    })
    assert res_user1.status_code == 201
    
    # Login User 1
    login_1 = client.post("/auth/login", json={
        "email": "user1@org1.com",
        "password": "password123"
    })
    assert login_1.status_code == 200
    user1_token = login_1.json()["access_token"]
    
    # Register Source 1 for Org 1
    res_src1 = client.post("/sources/register", json={
        "name": "PC-1",
        "kind": "device",
        "roots": ["/root_1"]
    }, headers={"Authorization": f"Bearer {user1_token}"})
    assert res_src1.status_code == 201
    src1_id = res_src1.json()["source"]["id"]
    
    # Upload dummy inventory file record to make execute_action copy succeed
    # We must seed the file in the database so execute_action doesn't raise FileNotFoundError
    res_seed = client.post("/inventory/upload", json={
        "source_id": src1_id,
        "files": [
            {
                "path": "/root_1/finance.xlsx",
                "relative_path": "finance.xlsx",
                "size_bytes": 2048,
                "mtime": "2026-07-07T12:00:00",
                "hash_sha256": "fake_sha_finance"
            }
        ]
    }, headers={"Authorization": f"Bearer {user1_token}"})
    assert res_seed.status_code in [200, 201]
    
    # 2. Create Org 2
    res_org2 = client.post("/auth/organizations", json={"name": "OrgTwo"})
    assert res_org2.status_code == 201
    org2_id = res_org2.json()["id"]
    
    # Create User 2
    res_user2 = client.post("/auth/users", json={
        "email": "user2@org2.com",
        "password": "password123",
        "role": "admin",
        "org_id": org2_id
    })
    assert res_user2.status_code == 201
    
    # Login User 2
    login_2 = client.post("/auth/login", json={
        "email": "user2@org2.com",
        "password": "password123"
    })
    assert login_2.status_code == 200
    user2_token = login_2.json()["access_token"]
    
    # Register Source 2 for Org 2
    res_src2 = client.post("/sources/register", json={
        "name": "PC-2",
        "kind": "device",
        "roots": ["/root_2"]
    }, headers={"Authorization": f"Bearer {user2_token}"})
    assert res_src2.status_code == 201
    src2_id = res_src2.json()["source"]["id"]
    
    # 3. Create a Transfer Job for Org 1 using actions copy route
    res_job1 = client.post("/actions/copy", json={
        "file_path": "finance.xlsx",
        "source": src1_id,
        "destination": src1_id,
        "triggered_by": "ui"
    }, headers={"Authorization": f"Bearer {user1_token}"})
    assert res_job1.status_code == 200
    session_id = res_job1.json()["id"]
    
    # 4. User 1 initializes chunked upload
    res_init = client.post("/transfer/init", json={
        "session_id": session_id,
        "total_chunks": 2,
        "chunk_size": 1024,
        "file_sha256": "82e3f6ef6",
        "file_path": "finance.xlsx"
    }, headers={"Authorization": f"Bearer {user1_token}"})
    assert res_init.status_code == 200
    
    # Assert directory is created under org1_id subfolder
    org1_session_dir = STAGING_ROOT / org1_id / session_id
    assert org1_session_dir.exists(), f"Staging directory not created at: {org1_session_dir}"
    
    # 5. User 1 uploads chunk 0
    chunk_data = b"Hello, tenant isolation!"
    chunk_sha = hashlib.sha256(chunk_data).hexdigest()
    
    res_upload = client.post(
        f"/transfer/{session_id}/chunk/0",
        content=chunk_data,
        headers={
            "Authorization": f"Bearer {user1_token}",
            "X-Chunk-SHA256": chunk_sha
        }
    )
    assert res_upload.status_code == 200
    assert (org1_session_dir / "chunk_0").exists()
    
    # 6. User 2 (Org 2) attempts malicious actions on User 1's transfer session
    # A) Attempt to read session status of Org 1
    res_mal_status = client.get(f"/transfer/{session_id}", headers={"Authorization": f"Bearer {user2_token}"})
    assert res_mal_status.status_code == 403
    
    # B) Attempt to upload chunk into Org 1 session
    res_mal_upload = client.post(
        f"/transfer/{session_id}/chunk/1",
        content=chunk_data,
        headers={
            "Authorization": f"Bearer {user2_token}",
            "X-Chunk-SHA256": chunk_sha
        }
    )
    assert res_mal_upload.status_code == 403
    
    # C) Attempt to download chunk from Org 1 session
    res_mal_download = client.get(
        f"/transfer/{session_id}/chunk/0",
        headers={"Authorization": f"Bearer {user2_token}"}
    )
    assert res_mal_download.status_code == 403
    
    # D) Attempt to finalize Org 1 session
    res_mal_finalize = client.post(f"/transfer/{session_id}/finalize", headers={"Authorization": f"Bearer {user2_token}"})
    assert res_mal_finalize.status_code == 403
    
    # Clean up disk files created in this test
    if (STAGING_ROOT / org1_id).exists():
        shutil.rmtree(STAGING_ROOT / org1_id, ignore_errors=True)
