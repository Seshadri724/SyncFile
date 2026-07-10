import asyncio
import hashlib
import uuid
from typing import List, Optional, Dict, Any
from mcp.server.fastmcp import FastMCP
from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models.source import Source
from app.models.file_record import FileRecord
from app.models.action_record import ActionRecord
from app.services.set_engine import get_computed_sets_from_db, get_summary_from_db
from app.services.action_service import get_dry_run_preview, execute_action as service_execute_action, undo_action
from app.services.inventory_service import get_inventory_status
from app.routers.analysis import get_duplicates as run_duplicates_analysis

mcp = FastMCP("SetSync")

# Plan-before-act safety tokens set
valid_dry_run_tokens = set()

def _generate_safety_token(source: str, destination: str, file_path: str, action_type: str) -> str:
    msg = f"{source}:{destination}:{file_path}:{action_type}"
    return hashlib.sha256(msg.encode("utf-8")).hexdigest()

@mcp.tool()
async def list_sources() -> List[Dict[str, Any]]:
    """List all registered devices and cloud remote sources in the system."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Source))
        sources = result.scalars().all()
        return [s.to_dict() for s in sources]

@mcp.tool()
async def query_files(
    source_x: str,
    source_y: str,
    view_type: str = "union",
    q: Optional[str] = None,
    min_size: Optional[int] = None,
    max_size: Optional[int] = None,
    limit: int = 100,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """Query and filter file sets across two selected sources.
    view_type can be 'union', 'intersection', 'only_a', 'only_b', or 'conflicts'."""
    async with AsyncSessionLocal() as db:
        rows = await get_computed_sets_from_db(
            db,
            source_x=source_x,
            source_y=source_y,
            view_type=view_type,
            q=q,
            min_size=min_size,
            max_size=max_size,
            limit=limit,
            offset=offset
        )
        return [r.model_dump() for r in rows]

@mcp.tool()
async def compare_sources(source_x: str, source_y: str) -> Dict[str, Any]:
    """Compare two sources and return a summary of identical, unique, and conflicting files."""
    async with AsyncSessionLocal() as db:
        summary = await get_summary_from_db(db, source_x, source_y)
        return {
            "total_files": summary.total_files,
            "union_count": summary.union_count,
            "intersection_count": summary.intersection_count,
            "only_a_count": summary.only_a_count,
            "only_b_count": summary.only_b_count,
            "conflict_count": summary.conflict_count
        }

@mcp.tool()
async def find_duplicates() -> Dict[str, Any]:
    """Identify duplicate files across all registered devices and estimate reclaimable storage space."""
    async with AsyncSessionLocal() as db:
        res = await run_duplicates_analysis(db)
        # DuplicateAnalysisResponse structure to dict
        return {
            "total_groups": res.total_groups,
            "total_duplicate_files": res.total_duplicate_files,
            "space_reclaimable_bytes": res.space_reclaimable_bytes,
            "groups": [
                {
                    "hash_sha256": g.hash_sha256,
                    "size_bytes": g.size_bytes,
                    "files": [
                        {
                            "id": f.id,
                            "source_id": f.source_id,
                            "source_name": f.source_name,
                            "path": f.path,
                            "relative_path": f.relative_path,
                            "size_bytes": f.size_bytes,
                            "mtime": f.mtime
                        } for f in g.files
                    ]
                } for g in res.groups
            ]
        }

@mcp.tool()
async def get_audit_log(limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
    """Retrieve the recent audit log history of sync operations."""
    async with AsyncSessionLocal() as db:
        stmt = select(ActionRecord).order_by(ActionRecord.timestamp.desc()).limit(limit).offset(offset)
        res = await db.execute(stmt)
        records = res.scalars().all()
        return [r.to_dict() for r in records]

@mcp.tool()
async def dry_run_action(
    file_path: str,
    source: str,
    destination: str,
    action_type: str # "copy", "move", "delete"
) -> Dict[str, Any]:
    """Perform a pre-flight dry-run of a file operation to check for overwrites and age conflicts.
    Returns preview analysis along with a validation token required for execute_action."""
    async with AsyncSessionLocal() as db:
        preview = await get_dry_run_preview(
            db=db,
            relative_path=file_path,
            source=source,
            destination=destination,
            action_type=action_type
        )
        
        # Generate plan-before-act safety validation token
        token = _generate_safety_token(source, destination, file_path, action_type)
        valid_dry_run_tokens.add(token)
        
        preview["validation_token"] = token
        preview["instruction"] = "Use this validation_token to authorize execute_action tool call."
        return preview

@mcp.tool()
async def execute_action(
    file_path: str,
    source: str,
    destination: str,
    action_type: str, # "copy", "move", "delete"
    validation_token: str,
    force: bool = False
) -> Dict[str, Any]:
    """Execute a file sync action (copy, move, or delete) on registered devices.
    Requires a matching validation_token from dry_run_action to enforce plan-before-act policy."""
    # Enforce plan-before-act safety check
    expected_token = _generate_safety_token(source, destination, file_path, action_type)
    if validation_token != expected_token or validation_token not in valid_dry_run_tokens:
        raise ValueError(
            "Safety Block: execute_action requires a matching validation_token from a prior dry_run_action call. "
            "Enforce plan-before-act!"
        )
    
    # Consume token
    valid_dry_run_tokens.discard(validation_token)

    async with AsyncSessionLocal() as db:
        action_rec = await service_execute_action(
            db=db,
            relative_path=file_path,
            source=source,
            destination=destination,
            action_type=action_type,
            triggered_by="mcp_ai",
            force=force
        )
        return action_rec.to_dict()

@mcp.tool()
async def revert_action(action_id: str) -> Dict[str, Any]:
    """Undo a previously completed copy or move action, restoring the overwritten or moved target files."""
    async with AsyncSessionLocal() as db:
        action_rec = await undo_action(db, action_id)
        return action_rec.to_dict()

if __name__ == "__main__":
    # Initialize and run stdio server
    mcp.run()
