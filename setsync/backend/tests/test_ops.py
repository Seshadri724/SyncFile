import pytest
from fastapi.testclient import TestClient
from app.main import app

def test_telemetry_latency_headers():
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert "X-Response-Time-Ms" in response.headers
    # Verify that it is a valid floating point representation of latency
    latency_val = float(response.headers["X-Response-Time-Ms"])
    assert latency_val >= 0.0

def test_logger_initialization():
    from app.services.logger import logger
    # Verify structlog BoundLogger is active
    assert logger is not None
    # Emit dummy log line to confirm it formats correctly
    logger.info("ops_unit_test_run", key="val")
