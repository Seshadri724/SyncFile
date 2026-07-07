import hmac
import hashlib
import time
from fastapi import Request, Header, HTTPException, status
from app.config import settings

async def verify_token(
    request: Request,
    authorization: str = Header(None),
    x_setsync_timestamp: str = Header(None),
    x_setsync_signature: str = Header(None)
):
    # 1. Support direct Bearer Token auth (primarily for frontend Web UI ease of use)
    if authorization:
        token = authorization
        if authorization.startswith("Bearer "):
            token = authorization[7:]
        if token == settings.API_TOKEN:
            return token
            
    # 2. Support HMAC-SHA256 Signature verification (primarily for Agents scanning/uploading)
    if x_setsync_timestamp and x_setsync_signature:
        # Replay attack check: verify request is within 300 seconds
        try:
            req_time = int(x_setsync_timestamp)
            now = int(time.time())
            if abs(now - req_time) > 300:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Request timestamp expired or server/client clock drift"
                )
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid timestamp format"
            )
            
        # Reconstruct signed message: timestamp + "." + request_body
        body = await request.body()
        body_str = body.decode("utf-8") if body else ""
        message = f"{x_setsync_timestamp}.{body_str}"
        
        # Verify signature
        expected_sig = hmac.new(
            settings.API_TOKEN.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        
        if hmac.compare_digest(x_setsync_signature, expected_sig):
            return "hmac_verified"
            
    # If neither matched
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Unauthorized: Invalid static token or HMAC signature signature mismatch"
    )
