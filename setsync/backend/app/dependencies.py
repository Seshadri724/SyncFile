import hmac
import hashlib
import time
import datetime
from fastapi import Request, Header, HTTPException, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.config import settings
from app.database import get_db, set_tenant_context

async def verify_token(
    request: Request,
    authorization: str = Header(None),
    x_setsync_timestamp: str = Header(None),
    x_setsync_signature: str = Header(None),
    x_setsync_source_id: str = Header(None),
    x_setsync_agent_key: str = Header(None),
    x_setsync_tenant_key: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    # Stash client-provided tenant encryption key on request.state (RAM only, never persisted)
    request.state.tenant_key = x_setsync_tenant_key
    
    verified_token = None

    # 1. Support direct Bearer Token or Cookie auth (primarily for frontend Web UI ease of use)
    token = None
    if authorization and not x_setsync_source_id:
        if authorization.startswith("Bearer "):
            token = authorization[7:]
        else:
            token = authorization
    else:
        token = request.cookies.get("setsync_session")

    if token:
        if token == settings.API_TOKEN:
            await set_tenant_context(db, None)
            verified_token = token
        else:
            import jwt
            try:
                payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
                user_id = payload.get("sub")
                if user_id:
                    from app.models.tenant import User
                    user = await db.get(User, user_id)
                    if user:
                        await set_tenant_context(db, user.org_id)
                        verified_token = f"user:{user.id}:{user.role}:{user.org_id}"
            except jwt.PyJWTError:
                pass

    # 2. Support Agent authentication per-source using agent key hash
    if not verified_token and x_setsync_source_id:
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
                await set_tenant_context(db, source.org_id)
                org_info = f":{source.org_id}" if source.org_id else ""
                verified_token = f"agent:{source.id}{org_info}"

    # 3. Support HMAC-SHA256 Signature verification using master API_TOKEN
    if not verified_token and x_setsync_timestamp and x_setsync_signature:
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
            await set_tenant_context(db, None)
            verified_token = "hmac_verified"
            
    if not verified_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: Invalid token, HMAC signature mismatch, or unregistered source"
        )

    # 4. Zero-Knowledge Key Consistency Verification
    if x_setsync_tenant_key:
        org_id = get_current_org_id(verified_token)
        if org_id:
            from app.models.tenant import Organization
            org = await db.get(Organization, org_id)
            if org:
                # Resolve key bytes and compute check hash
                try:
                    key_bytes = bytes.fromhex(x_setsync_tenant_key)
                    if len(key_bytes) != 32:
                        raise ValueError()
                except ValueError:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Invalid key format. Must be a 64-character hex string."
                    )
                
                from app.services.encryption import compute_tenant_key_check_hash
                computed_hash = compute_tenant_key_check_hash(key_bytes)
                
                if org.tenant_key_check_hash is None:
                    # Initialize on first write
                    org.tenant_key_check_hash = computed_hash
                    await db.commit()
                elif org.tenant_key_check_hash != computed_hash:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Tenant encryption key consistency verification failed: mixed key usage detected."
                    )
    return verified_token

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

from typing import Optional

def get_current_org_id(token: str) -> Optional[str]:
    """Helper to extract organization ID from token credentials."""
    if not token:
        return None
    if token.startswith("user:"):
        parts = token.split(":")
        if len(parts) >= 4:
            return parts[3]
    elif token.startswith("agent:"):
        parts = token.split(":")
        if len(parts) >= 3:
            return parts[2]
    return None
