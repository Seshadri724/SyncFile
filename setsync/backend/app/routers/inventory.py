from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.dependencies import verify_token
from app.schemas.inventory import InventoryUpload, InventoryStatusResponse, InventoryDelta
from app.services.inventory_service import handle_inventory_upload, get_inventory_status, handle_inventory_delta

router = APIRouter(
    prefix="/inventory",
    tags=["inventory"],
    dependencies=[Depends(verify_token)]
)

@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_inventory(
    upload: InventoryUpload,
    db: AsyncSession = Depends(get_db)
):
    if upload.source_pc not in ("A", "B"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="source_pc must be 'A' or 'B'"
        )
    count = await handle_inventory_upload(db, upload)
    return {"message": "Inventory uploaded successfully", "records_ingested": count}

@router.patch("/delta", status_code=status.HTTP_200_OK)
async def patch_inventory_delta(
    delta: InventoryDelta,
    db: AsyncSession = Depends(get_db)
):
    if delta.source_pc not in ("A", "B"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="source_pc must be 'A' or 'B'"
        )
    if delta.action not in ("upsert", "delete"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="action must be 'upsert' or 'delete'"
        )
    await handle_inventory_delta(db, delta)
    return {"message": f"Inventory delta processed successfully: {delta.action} on {delta.file.relative_path}"}

@router.get("/status", response_model=InventoryStatusResponse)
async def get_status(db: AsyncSession = Depends(get_db)):
    try:
        status_data = await get_inventory_status(db)
        return status_data
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
