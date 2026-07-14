import time
import asyncio
from collections import defaultdict
from fastapi import Request, Response, status
from starlette.middleware.base import BaseHTTPMiddleware
from app.config import settings

class RateLimitingMiddleware(BaseHTTPMiddleware):
    request_history = defaultdict(list)
    lock = asyncio.Lock()

    def __init__(self, app):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        # Resolve client IP (fall back safely if None)
        client_ip = request.client.host if request.client else "127.0.0.1"
        now = time.time()
        
        async with RateLimitingMiddleware.lock:
            # 1. Prune timestamps older than the sliding window config
            cutoff = now - settings.RATE_LIMIT_WINDOW_SECONDS
            history = RateLimitingMiddleware.request_history[client_ip]
            
            # Keep only timestamps within the window
            updated_history = [t for t in history if t >= cutoff]
            
            # 2. Enforce sliding window ceiling
            if len(updated_history) >= settings.RATE_LIMIT_MAX_REQUESTS:
                return Response(
                    content="Too Many Requests: Rate limit exceeded. Please try again later.",
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    media_type="text/plain"
                )
                
            # 3. Add current timestamp
            updated_history.append(now)
            RateLimitingMiddleware.request_history[client_ip] = updated_history
            
        return await call_next(request)
