import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.database import get_db
from app.dependencies import verify_token
from app.models.file_record import FileRecord
from app.models.source import Source
from app.schemas.analysis import DuplicateAnalysisResponse, DuplicateGroup, DuplicateFileEntry, StaleOrphanEntry
from typing import List

router = APIRouter(
    prefix="/analysis",
    tags=["analysis"],
    dependencies=[Depends(verify_token)]
)

@router.get("/duplicates", response_model=DuplicateAnalysisResponse)
async def get_duplicates(db: AsyncSession = Depends(get_db)):
    try:
        # 1. Fetch all hashes that have more than 1 occurrence
        stmt = (
            select(FileRecord.hash_sha256, FileRecord.size_bytes, func.count(FileRecord.id).label("cnt"))
            .group_by(FileRecord.hash_sha256, FileRecord.size_bytes)
            .having(func.count(FileRecord.id) > 1)
        )
        result = await db.execute(stmt)
        duplicate_hashes = result.fetchall()

        # 2. For each duplicate hash, fetch the associated files and sources
        groups = []
        total_duplicate_files = 0
        space_reclaimable = 0

        # We cache source names to avoid redundant queries
        source_names = {}

        for row in duplicate_hashes:
            h_val = row.hash_sha256
            size = row.size_bytes
            count = row.cnt
            
            # Fetch all files with this hash
            files_stmt = select(FileRecord).where(FileRecord.hash_sha256 == h_val)
            files_res = await db.execute(files_stmt)
            records = files_res.scalars().all()
            
            file_entries = []
            for r in records:
                if r.source_id not in source_names:
                    src = await db.get(Source, r.source_id)
                    source_names[r.source_id] = src.name if src else "Unknown Source"
                
                file_entries.append(DuplicateFileEntry(
                    id=r.id,
                    source_id=r.source_id,
                    source_name=source_names[r.source_id],
                    path=r.path,
                    relative_path=r.relative_path,
                    size_bytes=r.size_bytes,
                    mtime=r.mtime.isoformat() if r.mtime else ""
                ))
            
            groups.append(DuplicateGroup(
                hash_sha256=h_val,
                size_bytes=size,
                files=file_entries
            ))
            
            total_duplicate_files += count
            space_reclaimable += size * (count - 1)

        return DuplicateAnalysisResponse(
            total_groups=len(groups),
            total_duplicate_files=total_duplicate_files,
            space_reclaimable_bytes=space_reclaimable,
            groups=groups
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/stale-orphans", response_model=List[StaleOrphanEntry])
async def get_stale_orphans(
    age_days: int = Query(180, ge=1, description="Minimum age of file in days since last modification"),
    db: AsyncSession = Depends(get_db)
):
    try:
        # Find files where:
        # 1. No other file has the same hash (orphan/unique)
        # 2. mtime is older than cutoff
        cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=age_days)
        
        # Subquery to find unique hashes
        unique_stmt = (
            select(FileRecord.hash_sha256)
            .group_by(FileRecord.hash_sha256)
            .having(func.count(FileRecord.id) == 1)
        )
        unique_res = await db.execute(unique_stmt)
        unique_hashes = [r[0] for r in unique_res.fetchall()]
        
        if not unique_hashes:
            return []
            
        # Select records matching those unique hashes that are older than mtime cutoff
        stmt = select(FileRecord).where(
            FileRecord.hash_sha256.in_(unique_hashes),
            FileRecord.mtime < cutoff
        )
        
        res = await db.execute(stmt)
        records = res.scalars().all()
        
        source_names = {}
        entries = []
        now = datetime.datetime.utcnow()
        
        for r in records:
            if r.source_id not in source_names:
                src = await db.get(Source, r.source_id)
                source_names[r.source_id] = src.name if src else "Unknown Source"
                
            delta = now - r.mtime
            entries.append(StaleOrphanEntry(
                id=r.id,
                source_id=r.source_id,
                source_name=source_names[r.source_id],
                path=r.path,
                relative_path=r.relative_path,
                size_bytes=r.size_bytes,
                mtime=r.mtime.isoformat() if r.mtime else "",
                age_days=delta.days
            ))
            
        return entries
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
