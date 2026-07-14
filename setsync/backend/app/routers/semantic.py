from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.dependencies import verify_token
from app.models.file_record import FileRecord
from app.models.source import Source
from pydantic import BaseModel
from typing import List, Dict, Any

router = APIRouter(
    prefix="/analysis",
    tags=["semantic"],
    dependencies=[Depends(verify_token)]
)

class SemanticFileEntry(BaseModel):
    id: str
    source_id: str
    source_name: str
    path: str
    relative_path: str
    size_bytes: int
    mtime: str
    image_hash: str

class SemanticDuplicateGroup(BaseModel):
    representative_hash: str
    files: List[SemanticFileEntry]

def compute_hamming_distance(hex1: str, hex2: str) -> int:
    """Computes the Hamming distance between two 64-bit hexadecimal string representations."""
    try:
        val1 = int(hex1, 16)
        val2 = int(hex2, 16)
        return bin(val1 ^ val2).count("1")
    except Exception:
        return 999

@router.get("/semantic-duplicates", response_model=List[SemanticDuplicateGroup])
async def get_semantic_duplicates(
    request: Request,
    threshold: int = Query(10, ge=0, le=64, description="Maximum Hamming distance threshold for similarity"),
    db: AsyncSession = Depends(get_db)
):
    try:
        tenant_key_hex = getattr(request.state, 'tenant_key', None)
        # 1. Fetch all file records containing an image hash
        stmt = select(FileRecord).where(FileRecord.image_hash != None)
        result = await db.execute(stmt)
        records = result.scalars().all()
        
        if not records:
            return []
            
        # Cache source names and org_ids
        source_names = {}
        source_orgs = {}
        async def get_source_info(sid: str):
            if sid not in source_names:
                src = await db.get(Source, sid)
                source_names[sid] = src.name if src else "Unknown Source"
                source_orgs[sid] = src.org_id if src else None
            return source_names[sid], source_orgs[sid]

        # 2. Cluster files by Hamming distance
        clusters: List[Dict[str, Any]] = []
        
        for r in records:
            matched_cluster = None
            for c in clusters:
                dist = compute_hamming_distance(r.image_hash, c["representative_hash"])
                if dist <= threshold:
                    matched_cluster = c
                    break
            
            src_name, src_org = await get_source_info(r.source_id)
            from app.services.encryption import get_tenant_key_from_header, decrypt_deterministic
            key = get_tenant_key_from_header(tenant_key_hex, src_org)
            
            entry = SemanticFileEntry(
                id=r.id,
                source_id=r.source_id,
                source_name=src_name,
                path=decrypt_deterministic(r.path, key),
                relative_path=decrypt_deterministic(r.relative_path, key),
                size_bytes=r.size_bytes,
                mtime=r.mtime.isoformat() if r.mtime else "",
                image_hash=r.image_hash
            )
            
            if matched_cluster:
                matched_cluster["files"].append(entry)
            else:
                clusters.append({
                    "representative_hash": r.image_hash,
                    "files": [entry]
                })
                
        # 3. Filter clusters to only those containing more than 1 file (actual duplicates)
        duplicate_groups = []
        for c in clusters:
            if len(c["files"]) > 1:
                duplicate_groups.append(SemanticDuplicateGroup(
                    representative_hash=c["representative_hash"],
                    files=c["files"]
                ))
                
        return duplicate_groups
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
