import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.config import settings
from app.routers.query import _fallback_parse_prompt

@pytest.fixture(scope="module")
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

def test_fallback_regex_parser():
    # 1. Test conflicts
    res1 = _fallback_parse_prompt("show me conflict files")
    assert res1["view_type"] == "conflicts"
    
    # 2. Test larger than 1MB
    res2 = _fallback_parse_prompt("find files larger than 2MB only on A")
    assert res2["min_size"] == 2097152
    assert res2["view_type"] == "only_a"
    
    # 3. Test smaller than 500KB
    res3 = _fallback_parse_prompt("files smaller than 100KB on B")
    assert res3["max_size"] == 102400
    assert res3["view_type"] == "only_b"

    # 4. Test extension filter
    res4 = _fallback_parse_prompt("show me all .png files on both")
    assert res4["q"] == ".png"
    assert res4["view_type"] == "intersection"

def test_natural_query_endpoint(client, sources):
    headers = {"Authorization": f"Bearer {settings.API_TOKEN}"}
    
    payload = {
        "prompt": "show files larger than 10 bytes in conflicts",
        "source_x": sources["A"]["id"],
        "source_y": sources["B"]["id"]
    }
    
    response = client.post("/query/natural", json=payload, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "filters" in data
    assert "summary" in data
    assert "files" in data
    assert data["filters"]["min_size"] == 10
    assert data["filters"]["view_type"] == "conflicts"
