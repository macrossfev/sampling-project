from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import DetectionItem
from backend.schemas import DetectionItemCreate, DetectionItemResponse

router = APIRouter(prefix="/api/detection-items", tags=["detection_items"])


@router.get("", response_model=List[DetectionItemResponse])
def list_detection_items(
    water_plant_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(DetectionItem)
    if water_plant_id is not None:
        query = query.filter(DetectionItem.water_plant_id == water_plant_id)
    return query.order_by(DetectionItem.id).all()


@router.post("", response_model=DetectionItemResponse, status_code=201)
def create_detection_item(
    data: DetectionItemCreate, db: Session = Depends(get_db)
):
    if not data.water_plant_id:
        raise HTTPException(
            status_code=400, detail="water_plant_id is required"
        )
    di = DetectionItem(**data.model_dump())
    db.add(di)
    db.commit()
    db.refresh(di)
    return di


@router.put("/{item_id}", response_model=DetectionItemResponse)
def update_detection_item(
    item_id: int, data: DetectionItemCreate, db: Session = Depends(get_db)
):
    di = db.query(DetectionItem).filter(DetectionItem.id == item_id).first()
    if not di:
        raise HTTPException(status_code=404, detail="Detection item not found")
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(di, key, value)
    db.commit()
    db.refresh(di)
    return di


@router.delete("/{item_id}")
def delete_detection_item(item_id: int, db: Session = Depends(get_db)):
    di = db.query(DetectionItem).filter(DetectionItem.id == item_id).first()
    if not di:
        raise HTTPException(status_code=404, detail="Detection item not found")
    db.delete(di)
    db.commit()
    return {"detail": "Detection item deleted"}
