import uuid
import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.dependencies import verify_token
from app.models.plan import Plan, PlanItem
from app.schemas.plans import PlanCreate, PlanResponse
from app.services.action_service import execute_action as service_execute_action, undo_action as service_undo_action
from app.models.file_record import FileRecord
from app.services.policy import validate_action_policy
from typing import List

router = APIRouter(
    prefix="/plans",
    tags=["plans"],
    dependencies=[Depends(verify_token)]
)

@router.post("", response_model=PlanResponse, status_code=status.HTTP_201_CREATED)
async def create_plan(payload: PlanCreate, db: AsyncSession = Depends(get_db)):
    plan_id = str(uuid.uuid4())
    
    new_plan = Plan(
        id=plan_id,
        name=payload.name,
        status="draft"
    )
    db.add(new_plan)
    
    # Validate each item against the policy engine before saving!
    for idx, item in enumerate(payload.items):
        # 1. Fetch file record size and hash if present to check rules
        file_stmt = select(FileRecord).where(
            FileRecord.source_id == item.source_id,
            FileRecord.relative_path == item.file_path
        )
        file_res = await db.execute(file_stmt)
        file_rec = file_res.scalar_one_or_none()
        
        size = file_rec.size_bytes if file_rec else 0
        is_unique = False
        if file_rec:
            from sqlalchemy import func
            dup_stmt = select(func.count(FileRecord.id)).where(
                FileRecord.hash_sha256 == file_rec.hash_sha256,
                FileRecord.source_id != item.source_id
            )
            dup_count = (await db.execute(dup_stmt)).scalar_one()
            is_unique = (dup_count < 1)
            
        try:
            # Check policy rules (raise exception if violated)
            validate_action_policy(
                relative_path=item.file_path,
                action_type=item.action_type,
                size_bytes=size,
                is_unique=is_unique,
                force=False # Draft creation checks strict limits
            )
        except ValueError as e:
            await db.rollback()
            raise HTTPException(status_code=400, detail=f"Policy violation in item {idx + 1}: {str(e)}")
            
        plan_item = PlanItem(
            id=str(uuid.uuid4()),
            plan_id=plan_id,
            action_type=item.action_type,
            file_path=item.file_path,
            source_id=item.source_id,
            destination_id=item.destination_id,
            status="pending",
            sequence=item.sequence or idx
        )
        db.add(plan_item)
        
    await db.commit()
    await db.refresh(new_plan)
    
    # Reload with items loaded
    plan_stmt = select(Plan).where(Plan.id == plan_id)
    plan_res = await db.execute(plan_stmt)
    full_plan = plan_res.scalar_one()
    
    return full_plan.to_dict()

@router.get("", response_model=List[PlanResponse])
async def list_plans(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Plan).order_by(Plan.created_at.desc()))
    plans = result.scalars().all()
    return [p.to_dict() for p in plans]

@router.get("/{id}", response_model=PlanResponse)
async def get_plan(id: str, db: AsyncSession = Depends(get_db)):
    plan = await db.get(Plan, id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    return plan.to_dict()

@router.post("/{id}/approve", response_model=PlanResponse)
async def approve_and_run_plan(id: str, db: AsyncSession = Depends(get_db)):
    plan = await db.get(Plan, id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
        
    if plan.status not in ["draft", "failed"]:
        raise HTTPException(status_code=400, detail=f"Cannot run plan in status: {plan.status}")
        
    plan.status = "executing"
    await db.commit()
    
    # Sort items by sequence to run in order
    items = sorted(plan.items, key=lambda x: x.sequence)
    
    failed_any = False
    for item in items:
        if item.status == "completed":
            continue # Skip already completed items (resuming after failure)
            
        item.status = "executing"
        await db.commit()
        
        try:
            # Execute the action (since the plan was approved, we pass force=True to bypass size warnings)
            action_rec = await service_execute_action(
                db=db,
                relative_path=item.file_path,
                source=item.source_id,
                destination=item.destination_id,
                action_type=item.action_type,
                triggered_by="plan_executor",
                force=True
            )
            item.executed_action_id = action_rec.id
            item.status = "completed"
            await db.commit()
        except Exception as e:
            item.status = "failed"
            item.error_message = str(e)
            failed_any = True
            await db.commit()
            break # Stop executing subsequent items on first error (checkpoint)
            
    plan.status = "failed" if failed_any else "completed"
    plan.updated_at = datetime.datetime.utcnow()
    await db.commit()
    
    return plan.to_dict()

@router.post("/{id}/undo", response_model=PlanResponse)
async def rollback_plan(id: str, db: AsyncSession = Depends(get_db)):
    plan = await db.get(Plan, id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
        
    if plan.status not in ["completed", "failed"]:
        raise HTTPException(status_code=400, detail=f"Cannot rollback plan in status: {plan.status}")
        
    # Sort successfully executed items in descending sequence order (reverse undo!)
    items_to_undo = sorted([item for item in plan.items if item.status == "completed"], key=lambda x: x.sequence, reverse=True)
    
    for item in items_to_undo:
        if not item.executed_action_id:
            continue
        try:
            await service_undo_action(db, item.executed_action_id)
            item.status = "pending" # Reset to pending
            item.executed_action_id = None
            await db.commit()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Rollback failed on item {item.file_path}: {str(e)}")
            
    plan.status = "undone"
    plan.updated_at = datetime.datetime.utcnow()
    await db.commit()
    
    return plan.to_dict()
