from fastapi import APIRouter, Depends, HTTPException, Query, status
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
    threshold: int = Query(10, ge=0, le=64, description="Maximum Hamming distance threshold for similarity"),
    db: AsyncSession = Depends(get_db)
):
    try:
        # 1. Fetch all file records containing an image hash
        stmt = select(FileRecord).where(FileRecord.image_hash != None)
        result = await db.execute(stmt)
        records = result.scalars().all()
        
        if not records:
            return []
            
        # Cache source names
        source_names = {}
        async def get_source_name(sid: str) -> str:
            if sid not in source_names:
                src = await db.get(Source, sid)
                source_names[sid] = src.name if src else "Unknown Source"
            return source_names[sid]

        # 2. Cluster files by Hamming distance
        clusters: List[Dict[str, Any]] = []
        
        for r in records:
            matched_cluster = None
            for c in clusters:
                dist = compute_hamming_distance(r.image_hash, c["representative_hash"])
                if dist <= threshold:
                    matched_cluster = c
                    break
                    
            entry = SemanticFileEntry(
                id=r.id,
                source_id=r.source_id,
                source_name=await get_source_name(r.source_id),
                path=r.path,
                relative_path=r.relative_path,
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
