import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.config import settings

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c

def test_semantic_duplicates_clustering(client):
    headers = {"Authorization": f"Bearer {settings.API_TOKEN}"}
    
    # 1. Register Source A
    res_a = client.post("/sources/register", json={"name": "PC-A", "kind": "device", "roots": ["/root_a"]}, headers=headers)
    assert res_a.status_code == 201
    source_a = res_a.json()["source"]
    agent_a_key = res_a.json()["agent_key"]
    
    # 2. Upload two images that have very similar hashes (distance = 1 bit)
    # Hex representation of 8: 1000, Hex representation of A: 1010. Difference is 1 bit!
    payload_a = {
        "source_id": source_a["id"],
        "files": [
            {
                "path": "/root_a/image1.png",
                "relative_path": "image1.png",
                "size_bytes": 1024,
                "mtime": "2026-07-07T12:00:00",
                "hash_sha256": "sha_img1",
                "image_hash": "a1b2c3d4e5f60708"
            },
            {
                "path": "/root_a/image2.png",
                "relative_path": "image2.png",
                "size_bytes": 1024,
                "mtime": "2026-07-07T12:00:00",
                "hash_sha256": "sha_img2",
                "image_hash": "a1b2c3d4e5f6070a"
            }
        ]
    }
    
    headers_agent = {
        "X-SetSync-Source-Id": source_a["id"],
        "X-SetSync-Agent-Key": agent_a_key
    }
    res_upload = client.post("/inventory/upload", json=payload_a, headers=headers_agent)
    assert res_upload.status_code in [200, 201]
    
    # 3. Request semantic duplicates
    res_dup = client.get("/analysis/semantic-duplicates?threshold=10", headers=headers)
    assert res_dup.status_code == 200
    clusters = res_dup.json()
    
    assert len(clusters) == 1
    assert clusters[0]["representative_hash"] == "a1b2c3d4e5f60708"
    assert len(clusters[0]["files"]) == 2
    paths = [f["relative_path"] for f in clusters[0]["files"]]
    assert "image1.png" in paths
    assert "image2.png" in paths
