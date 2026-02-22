from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import SamplingTask
from backend.schemas import (
    SamplingTaskCreate,
    SamplingTaskUpdate,
    SamplingTaskResponse,
    BatchStatusUpdate,
)

router = APIRouter(prefix="/api/tasks", tags=["tasks"])

VALID_STATUSES = {"待采样", "已采样", "已送检", "已出报告"}


@router.get("", response_model=List[SamplingTaskResponse])
def list_tasks(
    company_id: Optional[int] = Query(None),
    year: Optional[int] = Query(None),
    month: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    water_plant_name: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(SamplingTask)
    if company_id is not None:
        query = query.filter(SamplingTask.company_id == company_id)
    if year is not None:
        query = query.filter(SamplingTask.year == year)
    if month is not None:
        query = query.filter(SamplingTask.month == month)
    if status is not None:
        query = query.filter(SamplingTask.status == status)
    if source is not None:
        query = query.filter(SamplingTask.source == source)
    if water_plant_name is not None:
        query = query.filter(
            SamplingTask.water_plant_name.contains(water_plant_name)
        )
    return query.order_by(SamplingTask.year, SamplingTask.month, SamplingTask.id).all()


@router.post("", response_model=SamplingTaskResponse, status_code=201)
def create_manual_task(
    data: SamplingTaskCreate, db: Session = Depends(get_db)
):
    task = SamplingTask(
        source="manual",
        detection_item_id=None,
        **data.model_dump(),
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.get("/{task_id}", response_model=SamplingTaskResponse)
def get_task(task_id: int, db: Session = Depends(get_db)):
    task = db.query(SamplingTask).filter(SamplingTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.put("/{task_id}", response_model=SamplingTaskResponse)
def update_task(
    task_id: int, data: SamplingTaskUpdate, db: Session = Depends(get_db)
):
    task = db.query(SamplingTask).filter(SamplingTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    update_data = data.model_dump(exclude_unset=True)
    if "status" in update_data and update_data["status"] not in VALID_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Must be one of: {', '.join(VALID_STATUSES)}",
        )
    for key, value in update_data.items():
        setattr(task, key, value)
    db.commit()
    db.refresh(task)
    return task


@router.delete("/{task_id}")
def delete_task(task_id: int, db: Session = Depends(get_db)):
    task = db.query(SamplingTask).filter(SamplingTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    db.delete(task)
    db.commit()
    return {"detail": "Task deleted"}


@router.patch("/batch-status")
def batch_update_status(
    data: BatchStatusUpdate, db: Session = Depends(get_db)
):
    if data.status not in VALID_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Must be one of: {', '.join(VALID_STATUSES)}",
        )
    if not data.task_ids:
        raise HTTPException(status_code=400, detail="task_ids cannot be empty")

    updated = (
        db.query(SamplingTask)
        .filter(SamplingTask.id.in_(data.task_ids))
        .update({SamplingTask.status: data.status}, synchronize_session="fetch")
    )
    db.commit()
    return {"detail": f"Updated {updated} tasks", "updated_count": updated}
