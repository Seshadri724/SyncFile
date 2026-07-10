from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.dependencies import verify_token
from app.schemas.sets import SetViewResponse, SetSummaryStrip, UnifiedFileRow
from app.services.set_engine import get_computed_sets_from_db, get_summary_from_db
from typing import Optional, List

router = APIRouter(
    prefix="/sets",
    tags=["sets"],
    dependencies=[Depends(verify_token)]
)

@router.post("/compute", response_model=SetSummaryStrip)
async def trigger_recompute(db: AsyncSession = Depends(get_db)):
    # With direct SQL queries, recomputing is instant. We return the live summary.
    return await get_summary_from_db(db)

@router.get("/view", response_model=SetViewResponse)
async def view_sets(
    type: str = Query("union", description="Type of view: union, intersection, only_a, only_b, conflicts"),
    q: Optional[str] = Query(None, description="Fuzzy match on filename or path"),
    min_size: Optional[int] = Query(None, description="Minimum size in bytes"),
    max_size: Optional[int] = Query(None, description="Maximum size in bytes"),
    limit: int = Query(100, ge=1, le=1000, description="Max files to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: AsyncSession = Depends(get_db)
):
    try:
        summary = await get_summary_from_db(db)
        files = await get_computed_sets_from_db(
            db, 
            view_type=type, 
            q=q, 
            min_size=min_size, 
            max_size=max_size,
            limit=limit,
            offset=offset
        )
        return SetViewResponse(summary=summary, files=files)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/search", response_model=List[UnifiedFileRow])
async def search_files(
    q: str = Query(..., description="Search query"),
    db: AsyncSession = Depends(get_db)
):
    try:
        # Search across all union records
        return await get_computed_sets_from_db(db, view_type="union", q=q)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
