import pytest
import time
from fastapi.testclient import TestClient
from app.main import app
from app.config import settings

def test_sliding_window_rate_limiter():
    from app.services.rate_limiter import RateLimitingMiddleware
    RateLimitingMiddleware.request_history.clear()
    
    client = TestClient(app)
    
    # 1. Override settings to narrow limits for rapid verification
    original_max = settings.RATE_LIMIT_MAX_REQUESTS
    original_window = settings.RATE_LIMIT_WINDOW_SECONDS
    
    settings.RATE_LIMIT_MAX_REQUESTS = 3
    settings.RATE_LIMIT_WINDOW_SECONDS = 2
    
    try:
        # 2. Fire 3 requests within threshold
        for i in range(3):
            res = client.get("/")
            assert res.status_code == 200
            
        # 3. Fire 4th request -> MUST fail with HTTP 429 Too Many Requests
        res_limit = client.get("/")
        assert res_limit.status_code == 429
        assert "Rate limit exceeded" in res_limit.text
        
        # 4. Wait for window to slide/expire (2.1 seconds)
        time.sleep(2.1)
        
        # 5. Request should now succeed again
        res_retry = client.get("/")
        assert res_retry.status_code == 200
        
    finally:
        # Restore configuration
        settings.RATE_LIMIT_MAX_REQUESTS = original_max
        settings.RATE_LIMIT_WINDOW_SECONDS = original_window
