import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.config import settings

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c

@pytest.fixture(scope="module")
def setup_sources(client):
    headers = {"Authorization": f"Bearer {settings.API_TOKEN}"}
    
    # Register A
    res_a = client.post("/sources/register", json={"name": "PC-A", "kind": "device", "roots": ["/root_a"]}, headers=headers)
    assert res_a.status_code == 201
    source_a = res_a.json()["source"]
    agent_a_key = res_a.json()["agent_key"]
    
    # Register B
    res_b = client.post("/sources/register", json={"name": "PC-B", "kind": "device", "roots": ["/root_b"]}, headers=headers)
    assert res_b.status_code == 201
    source_b = res_b.json()["source"]
    
    # Seed files into inventories (properly authenticated with agent key + source ID headers)
    payload_a = {
        "source_id": source_a["id"],
        "files": [
            {"path": "/root_a/plan_file1.txt", "relative_path": "plan_file1.txt", "size_bytes": 100, "mtime": "2026-07-07T12:00:00", "hash_sha256": "hash1"},
            {"path": "/root_a/plan_file2.txt", "relative_path": "plan_file2.txt", "size_bytes": 200, "mtime": "2026-07-07T12:00:00", "hash_sha256": "hash2"}
        ]
    }
    
    headers_agent = {
        "X-SetSync-Source-Id": source_a["id"],
        "X-SetSync-Agent-Key": agent_a_key
    }
    res_upload = client.post("/inventory/upload", json=payload_a, headers=headers_agent)
    assert res_upload.status_code in [200, 201]
    
    return {"A": source_a, "B": source_b, "agent_a_key": agent_a_key}

def test_plans_workflow_create_execute_undo(client, setup_sources):
    headers = {"Authorization": f"Bearer {settings.API_TOKEN}"}
    
    # 1. Create a draft plan containing two copy items
    plan_data = {
        "name": "Consolidate PC-A into PC-B",
        "items": [
            {
                "action_type": "copy",
                "file_path": "plan_file1.txt",
                "source_id": setup_sources["A"]["id"],
                "destination_id": setup_sources["B"]["id"],
                "sequence": 0
            },
            {
                "action_type": "copy",
                "file_path": "plan_file2.txt",
                "source_id": setup_sources["A"]["id"],
                "destination_id": setup_sources["B"]["id"],
                "sequence": 1
            }
        ]
    }
    
    res = client.post("/plans", json=plan_data, headers=headers)
    assert res.status_code == 201
    plan = res.json()
    assert plan["status"] == "draft"
    assert len(plan["items"]) == 2
    
    plan_id = plan["id"]
    
    # 2. Approve and Execute the plan
    run_res = client.post(f"/plans/{plan_id}/approve", headers=headers)
    assert run_res.status_code == 200
    plan_run = run_res.json()
    assert plan_run["status"] == "completed"
    assert plan_run["items"][0]["status"] == "completed"
    assert plan_run["items"][0]["executed_action_id"] is not None
    
    # Simulate agent completing the transfer jobs (which creates the UndoRecords)
    agent_headers = {
        "X-SetSync-Source-Id": setup_sources["A"]["id"],
        "X-SetSync-Agent-Key": setup_sources["agent_a_key"]
    }
    for item in plan_run["items"]:
        action_id = item["executed_action_id"]
        job_res = client.post(f"/jobs/{action_id}/status", json={"status": "completed"}, headers=agent_headers)
        assert job_res.status_code == 200
        
    # 3. Rollback (Undo) the entire plan
    undo_res = client.post(f"/plans/{plan_id}/undo", headers=headers)
    assert undo_res.status_code == 200
    plan_undone = undo_res.json()
    assert plan_undone["status"] == "undone"
    assert plan_undone["items"][0]["status"] == "pending"
    assert plan_undone["items"][0]["executed_action_id"] is None
