import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.config import settings

@pytest.fixture(scope="module", autouse=True)
def client():
    with TestClient(app) as c:
        yield c

def test_root_route(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"status": "online", "service": "SetSync Core Service"}

def test_unauthorized_access(client):
    # Attempting to read inventory status without Authorization header should fail
    response = client.get("/inventory/status")
    assert response.status_code == 401
    assert "Unauthorized" in response.json()["detail"]

    # Attempting with invalid token
    response = client.get("/inventory/status", headers={"Authorization": "Bearer bad_token"})
    assert response.status_code == 401
    assert "Unauthorized" in response.json()["detail"]

def test_authorized_access(client):
    headers = {"Authorization": f"Bearer {settings.API_TOKEN}"}
    response = client.get("/inventory/status", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "pc_a_count" in data
    assert "pc_b_count" in data

def test_inventory_upload_and_set_views(client):
    headers = {"Authorization": f"Bearer {settings.API_TOKEN}"}
    
    # 1. Upload mock inventory for PC A
    pc_a_payload = {
        "source_pc": "A",
        "files": [
            {
                "path": "/root_a/file1.txt",
                "relative_path": "file1.txt",
                "size_bytes": 100,
                "mtime": "2026-07-07T12:00:00",
                "hash_sha256": "hash1"
            },
            {
                "path": "/root_a/conflict.txt",
                "relative_path": "conflict.txt",
                "size_bytes": 200,
                "mtime": "2026-07-07T12:00:00",
                "hash_sha256": "hash_a"
            }
        ]
    }
    response = client.post("/inventory/upload", json=pc_a_payload, headers=headers)
    assert response.status_code == 201
    assert response.json()["records_ingested"] == 2

    # 2. Upload mock inventory for PC B
    pc_b_payload = {
        "source_pc": "B",
        "files": [
            {
                "path": "/root_b/file2.txt",
                "relative_path": "file2.txt",
                "size_bytes": 150,
                "mtime": "2026-07-07T12:05:00",
                "hash_sha256": "hash2"
            },
            {
                "path": "/root_b/conflict.txt",
                "relative_path": "conflict.txt",
                "size_bytes": 200,
                "mtime": "2026-07-07T12:05:00",
                "hash_sha256": "hash_b"
            }
        ]
    }
    response = client.post("/inventory/upload", json=pc_b_payload, headers=headers)
    assert response.status_code == 201
    assert response.json()["records_ingested"] == 2

    # 3. View status
    status_response = client.get("/inventory/status", headers=headers)
    assert status_response.status_code == 200
    assert status_response.json()["pc_a_count"] == 2
    assert status_response.json()["pc_b_count"] == 2

    # 4. View computed sets
    sets_response = client.get("/sets/view?type=union", headers=headers)
    assert sets_response.status_code == 200
    data = sets_response.json()
    assert data["summary"]["union_count"] == 3  # file1.txt (A), file2.txt (B), conflict.txt (both/conflict)
    assert data["summary"]["conflict_count"] == 1
    assert len(data["files"]) == 3

    # 5. Filter for conflicts
    conflicts_response = client.get("/sets/view?type=conflicts", headers=headers)
    assert conflicts_response.status_code == 200
    conflicts_data = conflicts_response.json()
    assert conflicts_data["summary"]["conflict_count"] == 1
    assert len(conflicts_data["files"]) == 1
    assert conflicts_data["files"][0]["relative_path"] == "conflict.txt"
    assert conflicts_data["files"][0]["location"] == "Conflict"

def test_hmac_signature_auth(client):
    import hmac
    import hashlib
    import time
    import json
    
    # 1. Correct signature
    payload = {"source_pc": "A", "files": []}
    json_data = json.dumps(payload, separators=(',', ':'))
    timestamp = str(int(time.time()))
    message = f"{timestamp}.{json_data}"
    sig = hmac.new(settings.API_TOKEN.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()
    
    headers = {
        "X-SetSync-Timestamp": timestamp,
        "X-SetSync-Signature": sig,
        "Content-Type": "application/json"
    }
    
    response = client.post("/inventory/upload", data=json_data, headers=headers)
    assert response.status_code == 201
    
    # 2. Tampered payload signature mismatch
    tampered_data = json.dumps({"source_pc": "B", "files": []}, separators=(',', ':'))
    response = client.post("/inventory/upload", data=tampered_data, headers=headers)
    assert response.status_code == 401
    
    # 3. Expired timestamp check
    old_timestamp = str(int(time.time()) - 400) # 400 seconds ago (expired)
    old_message = f"{old_timestamp}.{json_data}"
    old_sig = hmac.new(settings.API_TOKEN.encode("utf-8"), old_message.encode("utf-8"), hashlib.sha256).hexdigest()
    
    expired_headers = {
        "X-SetSync-Timestamp": old_timestamp,
        "X-SetSync-Signature": old_sig,
        "Content-Type": "application/json"
    }
    response = client.post("/inventory/upload", data=json_data, headers=expired_headers)
    assert response.status_code == 401
    assert "timestamp expired" in response.json()["detail"]

def test_inventory_delta_uploads(client):
    import hmac
    import hashlib
    import time
    import json
    
    # 1. Post a base empty scan for PC-A first via bearer token
    base_headers = {"Authorization": f"Bearer {settings.API_TOKEN}"}
    client.post("/inventory/upload", json={"source_pc": "A", "files": []}, headers=base_headers)
    
    # 2. Perform delta upsert via HMAC-SHA256 signature
    delta_payload = {
        "source_pc": "A",
        "action": "upsert",
        "file": {
            "path": "/root_a/delta_file.txt",
            "relative_path": "delta_file.txt",
            "size_bytes": 1024,
            "mtime": "2026-07-07T12:00:00",
            "hash_sha256": "delta_hash_abc"
        }
    }
    json_data = json.dumps(delta_payload, separators=(',', ':'))
    timestamp = str(int(time.time()))
    message = f"{timestamp}.{json_data}"
    sig = hmac.new(settings.API_TOKEN.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()
    
    headers = {
        "X-SetSync-Timestamp": timestamp,
        "X-SetSync-Signature": sig,
        "Content-Type": "application/json"
    }
    
    response = client.patch("/inventory/delta", data=json_data, headers=headers)
    assert response.status_code == 200
    assert "processed successfully" in response.json()["message"]
    
    # Check that status updates
    status = client.get("/inventory/status", headers=base_headers).json()
    assert status["pc_a_count"] == 1
    
    # 3. Perform delta delete via HMAC-SHA256 signature
    delete_payload = {
        "source_pc": "A",
        "action": "delete",
        "file": {
            "path": "/root_a/delta_file.txt",
            "relative_path": "delta_file.txt",
            "size_bytes": 0,
            "mtime": "2026-07-07T12:00:00",
            "hash_sha256": ""
        }
    }
    del_json_data = json.dumps(delete_payload, separators=(',', ':'))
    del_message = f"{timestamp}.{del_json_data}"
    del_sig = hmac.new(settings.API_TOKEN.encode("utf-8"), del_message.encode("utf-8"), hashlib.sha256).hexdigest()
    del_headers = {
        "X-SetSync-Timestamp": timestamp,
        "X-SetSync-Signature": del_sig,
        "Content-Type": "application/json"
    }
    
    del_response = client.patch("/inventory/delta", data=del_json_data, headers=del_headers)
    assert del_response.status_code == 200
    
    # Check status updates back to 0
    status_after = client.get("/inventory/status", headers=base_headers).json()
    assert status_after["pc_a_count"] == 0

@pytest.mark.anyio
async def test_audit_log_purge():
    from app.database import AsyncSessionLocal
    from app.services.audit_service import log_action, purge_old_audit_logs
    from app.models.action_record import ActionRecord
    from sqlalchemy import select, delete
    import datetime
    
    async with AsyncSessionLocal() as db:
        # Clear existing logs
        await db.execute(delete(ActionRecord))
        await db.commit()
        
        # Log old action
        record_old = ActionRecord(
            action_type="copy",
            file_path="old.txt",
            source="A",
            destination="B",
            status="success",
            triggered_by="test",
            timestamp=datetime.datetime.utcnow() - datetime.timedelta(days=40) # 40 days old
        )
        db.add(record_old)
        
        # Log new action
        record_new = ActionRecord(
            action_type="copy",
            file_path="new.txt",
            source="A",
            destination="B",
            status="success",
            triggered_by="test",
            timestamp=datetime.datetime.utcnow() - datetime.timedelta(days=10) # 10 days old
        )
        db.add(record_new)
        await db.commit()
        
        # Purge logs older than 30 days
        deleted = await purge_old_audit_logs(db, max_age_days=30)
        assert deleted == 1
        
        # Check active database entries
        stmt = select(ActionRecord)
        records = (await db.execute(stmt)).scalars().all()
        assert len(records) == 1
        assert records[0].file_path == "new.txt"
