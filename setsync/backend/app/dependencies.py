import hmac
import hashlib
import time
import datetime
from fastapi import Request, Header, HTTPException, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.config import settings
from app.database import get_db

async def verify_token(
    request: Request,
    authorization: str = Header(None),
    x_setsync_timestamp: str = Header(None),
    x_setsync_signature: str = Header(None),
    x_setsync_source_id: str = Header(None),
    x_setsync_agent_key: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    # 1. Support direct Bearer Token auth (primarily for frontend Web UI ease of use)
    if authorization and not x_setsync_source_id:
        token = authorization
        if authorization.startswith("Bearer "):
            token = authorization[7:]
        if token == settings.API_TOKEN:
            return token
        if token.startswith("user:"):
            user_id = token[5:]
            from app.models.tenant import User
            user = await db.get(User, user_id)
            if user:
                return f"user:{user.id}:{user.role}:{user.org_id}"

    # 2. Support Agent authentication per-source using agent key hash
    if x_setsync_source_id:
        token = x_setsync_agent_key
        if not token and authorization:
            token = authorization
            if authorization.startswith("Bearer "):
                token = authorization[7:]
        
        if token:
            token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
            from app.models.source import Source
            result = await db.execute(
                select(Source).where(Source.id == x_setsync_source_id)
            )
            source = result.scalar_one_or_none()
            if source and source.agent_key_hash == token_hash:
                source.last_seen_at = datetime.datetime.utcnow()
                await db.commit()
                # If agent belongs to an org, convey that info in token
                org_info = f":{source.org_id}" if source.org_id else ""
                return f"agent:{source.id}{org_info}"

    # 3. Support HMAC-SHA256 Signature verification using master API_TOKEN
    if x_setsync_timestamp and x_setsync_signature:
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
            
        body = await request.body()
        body_str = body.decode("utf-8") if body else ""
        message = f"{x_setsync_timestamp}.{body_str}"
        
        expected_sig = hmac.new(
            settings.API_TOKEN.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        
        if hmac.compare_digest(x_setsync_signature, expected_sig):
            return "hmac_verified"
            
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Unauthorized: Invalid token, HMAC signature mismatch, or unregistered source"
    )

def require_role(allowed_roles: list[str]):
    async def role_checker(token: str = Depends(verify_token)):
        if token == settings.API_TOKEN or token == "hmac_verified":
            return token
        if token.startswith("user:"):
            parts = token.split(":")
            role = parts[2]
            if role not in allowed_roles:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Forbidden: Insufficient permissions for this action"
                )
            return token
        # Agents are allowed operational actions but not configuration/admin changes
        if token.startswith("agent:"):
            if "operator" in allowed_roles or "viewer" in allowed_roles:
                return token
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: Agents cannot perform admin settings actions"
            )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Insufficient permissions"
        )
    return role_checker
