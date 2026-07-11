import hashlib
from fastapi import APIRouter, Depends, HTTPException, status, Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.tenant import Organization, User

router = APIRouter(prefix="/auth", tags=["Authentication"])

class OrgCreate(BaseModel):
    name: str

class UserCreate(BaseModel):
    email: str
    password: str
    role: str = "viewer"  # "viewer", "operator", "admin"
    org_id: str

class LoginRequest(BaseModel):
    email: str
    password: str

@router.post("/organizations", status_code=201)
async def create_organization(payload: OrgCreate, db: AsyncSession = Depends(get_db)):
    org = Organization(name=payload.name)
    db.add(org)
    await db.commit()
    await db.refresh(org)
    return org.to_dict()

@router.post("/users", status_code=201)
async def create_user(payload: UserCreate, db: AsyncSession = Depends(get_db)):
    if payload.role not in ["viewer", "operator", "admin"]:
        raise HTTPException(status_code=400, detail="Invalid role. Must be 'viewer', 'operator', or 'admin'.")

    # Verify org exists
    org = await db.get(Organization, payload.org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found.")

    # Check duplicate email
    stmt = select(User).where(User.email == payload.email)
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered.")

    hashed = hashlib.sha256(payload.password.encode("utf-8")).hexdigest()
    user = User(
        email=payload.email,
        hashed_password=hashed,
        role=payload.role,
        org_id=payload.org_id
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user.to_dict()

@router.post("/login")
async def login(payload: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)):
    stmt = select(User).where(User.email == payload.email)
    user = (await db.execute(stmt)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    hashed = hashlib.sha256(payload.password.encode("utf-8")).hexdigest()
    if user.hashed_password != hashed:
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    token = f"user:{user.id}"
    response.set_cookie(
        key="setsync_session",
        value=token,
        httponly=True,
        samesite="strict",
        secure=False,  # Set to True in production with TLS/HTTPS
        max_age=3600 * 24 * 7  # 1 week
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user.to_dict()
    }

@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(key="setsync_session")
    return {"message": "Logged out successfully"}
