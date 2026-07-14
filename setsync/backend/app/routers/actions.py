from fastapi import APIRouter, Depends, HTTPException, Request as FastAPIRequest, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.dependencies import verify_token
from app.schemas.actions import ActionRequest, ActionResponse, DryRunResponse
from app.services.action_service import get_dry_run_preview, execute_action, undo_action
from app.models.action_record import ActionRecord

router = APIRouter(
    prefix="/actions",
    tags=["actions"],
    dependencies=[Depends(verify_token)]
)

@router.post("/dry-run", response_model=DryRunResponse)
async def dry_run_action(
    request: ActionRequest,
    action_type: str = Query("copy", description="Action type: copy or move"),
    db: AsyncSession = Depends(get_db)
):
    try:
        preview = await get_dry_run_preview(
            db=db,
            relative_path=request.file_path,
            source=request.source,
            destination=request.destination,
            action_type=action_type
        )
        return preview
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post("/copy", response_model=ActionResponse)
async def copy_file(request: ActionRequest, http_request: FastAPIRequest, db: AsyncSession = Depends(get_db)):
    try:
        tenant_key_hex = getattr(http_request.state, 'tenant_key', None)
        action_rec = await execute_action(
            db,
            relative_path=request.file_path,
            source=request.source,
            destination=request.destination,
            action_type="copy",
            triggered_by=request.triggered_by or "ui",
            tenant_key_hex=tenant_key_hex
        )
        return action_rec.to_dict()
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post("/move", response_model=ActionResponse)
async def move_file(request: ActionRequest, http_request: FastAPIRequest, db: AsyncSession = Depends(get_db)):
    try:
        tenant_key_hex = getattr(http_request.state, 'tenant_key', None)
        action_rec = await execute_action(
            db,
            relative_path=request.file_path,
            source=request.source,
            destination=request.destination,
            action_type="move",
            triggered_by=request.triggered_by or "ui",
            tenant_key_hex=tenant_key_hex
        )
        return action_rec.to_dict()
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post("/delete", response_model=ActionResponse)
async def delete_file(
    request: ActionRequest,
    http_request: FastAPIRequest,
    force: bool = Query(False, description="Force delete unique content hashes"),
    db: AsyncSession = Depends(get_db)
):
    try:
        tenant_key_hex = getattr(http_request.state, 'tenant_key', None)
        action_rec = await execute_action(
            db,
            relative_path=request.file_path,
            source=request.source,
            destination=request.destination,
            action_type="delete",
            triggered_by=request.triggered_by or "ui",
            force=force,
            tenant_key_hex=tenant_key_hex
        )
        return action_rec.to_dict()
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post("/{id}/undo", response_model=ActionResponse)
async def revert_action(id: str, db: AsyncSession = Depends(get_db)):
    try:
        action_rec = await undo_action(db, id)
        return action_rec.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/{id}/status", response_model=ActionResponse)
async def get_action_status(id: str, db: AsyncSession = Depends(get_db)):
    action_rec = await db.get(ActionRecord, id)
    if not action_rec:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Action not found")
    return action_rec.to_dict()
