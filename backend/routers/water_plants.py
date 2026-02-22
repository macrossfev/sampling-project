from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from backend.database import get_db
from backend.models import WaterPlant
from backend.schemas import WaterPlantCreate, WaterPlantResponse

router = APIRouter(prefix="/api/water-plants", tags=["water_plants"])


@router.get("", response_model=List[WaterPlantResponse])
def list_water_plants(
    contract_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(WaterPlant).options(
        joinedload(WaterPlant.detection_items)
    )
    if contract_id is not None:
        query = query.filter(WaterPlant.contract_id == contract_id)
    return query.order_by(WaterPlant.id).all()


@router.post("", response_model=WaterPlantResponse, status_code=201)
def create_water_plant(data: WaterPlantCreate, db: Session = Depends(get_db)):
    if not data.contract_id:
        raise HTTPException(
            status_code=400, detail="contract_id is required"
        )
    wp_data = data.model_dump(exclude={"detection_items"})
    wp = WaterPlant(**wp_data)
    db.add(wp)
    db.commit()
    db.refresh(wp)
    # Reload with detection_items
    wp = (
        db.query(WaterPlant)
        .options(joinedload(WaterPlant.detection_items))
        .filter(WaterPlant.id == wp.id)
        .first()
    )
    return wp


@router.put("/{wp_id}", response_model=WaterPlantResponse)
def update_water_plant(
    wp_id: int, data: WaterPlantCreate, db: Session = Depends(get_db)
):
    wp = db.query(WaterPlant).filter(WaterPlant.id == wp_id).first()
    if not wp:
        raise HTTPException(status_code=404, detail="Water plant not found")
    update_data = data.model_dump(exclude={"detection_items"}, exclude_unset=True)
    for key, value in update_data.items():
        setattr(wp, key, value)
    db.commit()
    wp = (
        db.query(WaterPlant)
        .options(joinedload(WaterPlant.detection_items))
        .filter(WaterPlant.id == wp_id)
        .first()
    )
    return wp


@router.delete("/{wp_id}")
def delete_water_plant(wp_id: int, db: Session = Depends(get_db)):
    wp = db.query(WaterPlant).filter(WaterPlant.id == wp_id).first()
    if not wp:
        raise HTTPException(status_code=404, detail="Water plant not found")
    db.delete(wp)
    db.commit()
    return {"detail": "Water plant deleted"}
