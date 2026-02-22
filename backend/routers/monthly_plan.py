from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import SamplingTrip, Company
from backend.schemas import (
    SamplingTripCreate,
    SamplingTripUpdate,
    SamplingTripResponse,
    MonthlyPlanGenerate,
)
from backend.services.monthly_planner import generate_monthly_plan

router = APIRouter(prefix="/api/monthly-plan", tags=["monthly-plan"])


@router.get("/trips", response_model=List[SamplingTripResponse])
def list_trips(
    year: int = Query(...),
    month: int = Query(...),
    group_no: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(SamplingTrip).filter(
        SamplingTrip.year == year,
        SamplingTrip.month == month,
    )
    if group_no is not None:
        query = query.filter(SamplingTrip.group_no == group_no)
    trips = query.order_by(SamplingTrip.start_date, SamplingTrip.group_no).all()
    results = []
    for t in trips:
        data = SamplingTripResponse.model_validate(t)
        company = db.query(Company).filter(Company.id == t.company_id).first()
        data.company_name = company.name if company else None
        results.append(data)
    return results


@router.post("/generate")
def generate_plan(data: MonthlyPlanGenerate, db: Session = Depends(get_db)):
    if data.scheme not in ("compact", "balanced", "relaxed"):
        raise HTTPException(status_code=400, detail="scheme must be compact/balanced/relaxed")
    result = generate_monthly_plan(db, data.year, data.month, data.scheme)
    return result


@router.post("/trips", response_model=SamplingTripResponse)
def create_trip(data: SamplingTripCreate, db: Session = Depends(get_db)):
    trip = SamplingTrip(**data.model_dump())
    db.add(trip)
    db.commit()
    db.refresh(trip)
    company = db.query(Company).filter(Company.id == trip.company_id).first()
    resp = SamplingTripResponse.model_validate(trip)
    resp.company_name = company.name if company else None
    return resp


@router.put("/trips/{trip_id}", response_model=SamplingTripResponse)
def update_trip(trip_id: int, data: SamplingTripUpdate, db: Session = Depends(get_db)):
    trip = db.query(SamplingTrip).filter(SamplingTrip.id == trip_id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(trip, key, value)
    db.commit()
    db.refresh(trip)
    company = db.query(Company).filter(Company.id == trip.company_id).first()
    resp = SamplingTripResponse.model_validate(trip)
    resp.company_name = company.name if company else None
    return resp


@router.delete("/trips/{trip_id}")
def delete_trip(trip_id: int, db: Session = Depends(get_db)):
    trip = db.query(SamplingTrip).filter(SamplingTrip.id == trip_id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    db.delete(trip)
    db.commit()
    return {"detail": "Trip deleted"}
