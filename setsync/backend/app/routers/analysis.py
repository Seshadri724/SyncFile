import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.database import get_db
from app.dependencies import verify_token
from app.models.file_record import FileRecord
from app.models.source import Source
from app.schemas.analysis import (
    DuplicateAnalysisResponse, DuplicateGroup, DuplicateFileEntry,
    StaleOrphanEntry, FleetResponse, GovernanceResponse, GovernanceFileEntry
)
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

        # We cache source names and org_ids to avoid redundant queries
        source_names = {}
        source_orgs = {}

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
                    source_orgs[r.source_id] = src.org_id if src else None
                
                from app.services.encryption import get_tenant_key, decrypt_deterministic
                key = get_tenant_key(source_orgs[r.source_id])
                
                file_entries.append(DuplicateFileEntry(
                    id=r.id,
                    source_id=r.source_id,
                    source_name=source_names[r.source_id],
                    path=decrypt_deterministic(r.path, key),
                    relative_path=decrypt_deterministic(r.relative_path, key),
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
        source_orgs = {}
        entries = []
        now = datetime.datetime.utcnow()
        
        for r in records:
            if r.source_id not in source_names:
                src = await db.get(Source, r.source_id)
                source_names[r.source_id] = src.name if src else "Unknown Source"
                source_orgs[r.source_id] = src.org_id if src else None
                
            from app.services.encryption import get_tenant_key, decrypt_deterministic
            key = get_tenant_key(source_orgs[r.source_id])
            
            delta = now - r.mtime
            entries.append(StaleOrphanEntry(
                id=r.id,
                source_id=r.source_id,
                source_name=source_names[r.source_id],
                path=decrypt_deterministic(r.path, key),
                relative_path=decrypt_deterministic(r.relative_path, key),
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

@router.get("/fleet", response_model=FleetResponse)
async def get_fleet_analysis(
    db: AsyncSession = Depends(get_db),
    token: str = Depends(verify_token)
):
    try:
        # Resolve org_id constraint
        org_id = None
        if token.startswith("user:"):
            org_id = token.split(":")[3]

        # 1. Fetch sources
        src_stmt = select(Source)
        if org_id:
            src_stmt = src_stmt.where(Source.org_id == org_id)
        src_res = await db.execute(src_stmt)
        sources = src_res.scalars().all()
        source_ids = [s.id for s in sources]

        total_sources = len(sources)
        active_sources = sum(1 for s in sources if s.status == "online")
        offline_sources = sum(1 for s in sources if s.status == "offline")

        if not source_ids:
            return FleetResponse(
                total_sources=0,
                active_sources=0,
                offline_sources=0,
                total_files=0,
                total_bytes=0,
                unique_files_count=0,
                unique_files_bytes=0
            )

        # 2. Get file stats
        files_stmt = select(
            func.count(FileRecord.id),
            func.sum(FileRecord.size_bytes)
        ).where(FileRecord.source_id.in_(source_ids))
        files_res = await db.execute(files_stmt)
        res_row = files_res.fetchone()
        total_files = res_row[0] if res_row else 0
        total_bytes = res_row[1] if res_row and res_row[1] else 0

        # 3. Get unique file records (Data Loss Risk)
        # Unique file record = hash exists on exactly one of the source_ids
        unique_stmt = (
            select(FileRecord.hash_sha256)
            .where(FileRecord.source_id.in_(source_ids))
            .group_by(FileRecord.hash_sha256)
            .having(func.count(FileRecord.id) == 1)
        )
        unique_hashes_res = await db.execute(unique_stmt)
        unique_hashes = [r[0] for r in unique_hashes_res.fetchall()]

        unique_files_count = 0
        unique_files_bytes = 0
        if unique_hashes:
            uniq_stats_stmt = select(
                func.count(FileRecord.id),
                func.sum(FileRecord.size_bytes)
            ).where(
                FileRecord.source_id.in_(source_ids),
                FileRecord.hash_sha256.in_(unique_hashes)
            )
            uniq_stats_res = await db.execute(uniq_stats_stmt)
            uniq_row = uniq_stats_res.fetchone()
            unique_files_count = uniq_row[0] if uniq_row else 0
            unique_files_bytes = uniq_row[1] if uniq_row and uniq_row[1] else 0

        return FleetResponse(
            total_sources=total_sources,
            active_sources=active_sources,
            offline_sources=offline_sources,
            total_files=total_files,
            total_bytes=total_bytes,
            unique_files_count=unique_files_count,
            unique_files_bytes=unique_files_bytes
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/governance", response_model=GovernanceResponse)
async def get_governance_analysis(
    db: AsyncSession = Depends(get_db),
    token: str = Depends(verify_token)
):
    try:
        # Resolve org_id constraint
        org_id = None
        if token.startswith("user:"):
            org_id = token.split(":")[3]

        # 1. Fetch sources to scope query
        src_stmt = select(Source)
        if org_id:
            src_stmt = src_stmt.where(Source.org_id == org_id)
        src_res = await db.execute(src_stmt)
        sources = src_res.scalars().all()
        source_ids = [s.id for s in sources]
        source_names = {s.id: s.name for s in sources}

        if not source_ids:
            return GovernanceResponse(total_flagged_files=0, flagged_files=[])

        # 2. Fetch all file records for scoped sources
        files_stmt = select(FileRecord).where(FileRecord.source_id.in_(source_ids))
        files_res = await db.execute(files_stmt)
        records = files_res.scalars().all()

        source_orgs = {s.id: s.org_id for s in sources}
        flagged_files = []
        for r in records:
            from app.services.encryption import get_tenant_key, decrypt_deterministic
            key = get_tenant_key(source_orgs.get(r.source_id))
            decrypted_rel_path = decrypt_deterministic(r.relative_path, key) or ""
            decrypted_path = decrypt_deterministic(r.path, key) or ""
            
            name_lower = decrypted_rel_path.lower()
            reason = None
            if any(k in name_lower for k in ["salary", "payroll", "payslip"]):
                reason = "Financial / Payroll Document"
            elif any(k in name_lower for k in ["passport", "id_card", "driver_license", "ssn"]):
                reason = "Identity / PII Record"
            elif any(k in name_lower for k in ["tax", "invoice", "billing"]):
                reason = "Tax / Billing Document"
            elif name_lower.endswith(".key") or name_lower.endswith(".pem") or "credential" in name_lower or "secret" in name_lower:
                reason = "Secret Key / Credential file"
            elif "backup" in name_lower or name_lower.endswith(".bak"):
                reason = "System Backup File"

            if reason:
                flagged_files.append(GovernanceFileEntry(
                    id=r.id,
                    source_id=r.source_id,
                    source_name=source_names.get(r.source_id, "Unknown"),
                    path=decrypted_path,
                    relative_path=decrypted_rel_path,
                    size_bytes=r.size_bytes,
                    flag_reason=reason
                ))

        return GovernanceResponse(
            total_flagged_files=len(flagged_files),
            flagged_files=flagged_files
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
