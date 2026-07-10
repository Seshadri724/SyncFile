import pytest
import hmac
import hashlib
import time
import json
from fastapi.testclient import TestClient
from app.main import app
from app.config import settings

@pytest.fixture(scope="module", autouse=True)
def client():
    with TestClient(app) as c:
        yield c

@pytest.fixture(scope="module")
def sources(client):
    # Register Source A
    headers = {"Authorization": f"Bearer {settings.API_TOKEN}"}
    res_a = client.post("/sources/register", json={"name": "PC-A", "kind": "device", "roots": ["/root_a"]}, headers=headers)
    assert res_a.status_code == 201
    source_a = res_a.json()["source"]
    
    # Register Source B
    res_b = client.post("/sources/register", json={"name": "PC-B", "kind": "device", "roots": ["/root_b"]}, headers=headers)
    assert res_b.status_code == 201
    source_b = res_b.json()["source"]
    
    return {"A": source_a, "B": source_b}

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

def test_authorized_access(client, sources):
    headers = {"Authorization": f"Bearer {settings.API_TOKEN}"}
    response = client.get("/inventory/status", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "sources" in data
    # Ensure source A and B are returned
    source_ids = [s["source_id"] for s in data["sources"]]
    assert sources["A"]["id"] in source_ids
    assert sources["B"]["id"] in source_ids

def test_inventory_upload_and_set_views(client, sources):
    headers = {"Authorization": f"Bearer {settings.API_TOKEN}"}
    source_a_id = sources["A"]["id"]
    source_b_id = sources["B"]["id"]
    
    # 1. Upload mock inventory for PC A
    pc_a_payload = {
        "source_id": source_a_id,
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
        "source_id": source_b_id,
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
    status_data = status_response.json()["sources"]
    
    # Map sources
    status_map = {s["source_id"]: s for s in status_data}
    assert status_map[source_a_id]["count"] == 2
    assert status_map[source_b_id]["count"] == 2

    # 4. View computed sets
    sets_url = f"/sets/view?type=union&source_x={source_a_id}&source_y={source_b_id}"
    sets_response = client.get(sets_url, headers=headers)
    assert sets_response.status_code == 200
    data = sets_response.json()
    assert data["summary"]["union_count"] == 3  # file1.txt (A), file2.txt (B), conflict.txt (both/conflict)
    assert data["summary"]["conflict_count"] == 1
    assert len(data["files"]) == 3

    # 5. Filter for conflicts
    conflicts_url = f"/sets/view?type=conflicts&source_x={source_a_id}&source_y={source_b_id}"
    conflicts_response = client.get(conflicts_url, headers=headers)
    assert conflicts_response.status_code == 200
    conflicts_data = conflicts_response.json()
    assert conflicts_data["summary"]["conflict_count"] == 1
    assert len(conflicts_data["files"]) == 1
    assert conflicts_data["files"][0]["relative_path"] == "conflict.txt"
    assert conflicts_data["files"][0]["location"] == "Conflict"

def test_hmac_signature_auth(client, sources):
    source_a_id = sources["A"]["id"]
    
    # 1. Correct signature
    payload = {"source_id": source_a_id, "files": []}
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
    tampered_data = json.dumps({"source_id": sources["B"]["id"], "files": []}, separators=(',', ':'))
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

def test_inventory_delta_uploads(client, sources):
    source_a_id = sources["A"]["id"]
    
    # 1. Post a base empty scan for PC-A first via bearer token
    base_headers = {"Authorization": f"Bearer {settings.API_TOKEN}"}
    client.post("/inventory/upload", json={"source_id": source_a_id, "files": []}, headers=base_headers)
    
    # 2. Perform delta upsert via HMAC-SHA256 signature
    delta_payload = {
        "source_id": source_a_id,
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
    status_res = client.get("/inventory/status", headers=base_headers).json()["sources"]
    status_map = {s["source_id"]: s for s in status_res}
    assert status_map[source_a_id]["count"] == 1
    
    # 3. Perform delta delete via HMAC-SHA256 signature
    delete_payload = {
        "source_id": source_a_id,
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
    status_after = client.get("/inventory/status", headers=base_headers).json()["sources"]
    status_map_after = {s["source_id"]: s for s in status_after}
    assert status_map_after[source_a_id]["count"] == 0

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

@pytest.mark.anyio
async def test_block_delta_sync(tmp_path):
    from app.transfer.delta_sync import (
        generate_block_signatures,
        compute_delta,
        apply_delta
    )
    
    # Create two large matching files with small difference
    src_file = tmp_path / "source.txt"
    dest_file = tmp_path / "destination.txt"
    
    # 256KB of data split into blocks of 64KB (4 blocks)
    block_a = b"A" * 65536
    block_b = b"B" * 65536
    block_c = b"C" * 65536
    block_d = b"D" * 65536
    
    # Destination has A, B, C, D
    dest_file.write_bytes(block_a + block_b + block_c + block_d)
    
    # Source has A, B_MODIFIED, C, D
    block_b_mod = b"B" * 32768 + b"X" * 32768
    src_file.write_bytes(block_a + block_b_mod + block_c + block_d)
    
    # 1. Compute Signatures of Dest
    sigs = generate_block_signatures(str(dest_file), block_size=65536)
    assert len(sigs) == 4
    
    # 2. Compute Delta from Source
    delta = compute_delta(sigs, str(src_file), block_size=65536)
    
    # Ops list should copy block 0, send raw data for block 1, copy block 2, copy block 3
    assert len(delta) == 4
    assert delta[0] == ("copy", 0)
    assert delta[1][0] == "data"
    assert len(delta[1][1]) == 65536
    assert delta[2] == ("copy", 2)
    assert delta[3] == ("copy", 3)
    
    # 3. Apply Delta
    temp_dest = str(dest_file) + ".tmp"
    apply_delta(delta, str(dest_file), temp_dest, block_size=65536)
    
    # Dest file should be rebuilt and matches source
    assert dest_file.read_bytes() == src_file.read_bytes()
