from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.orm import Session, joinedload

from backend.database import get_db
from backend.models import Contract, WaterPlant, DetectionItem, SamplingTask
from backend.schemas import (
    ContractCreate,
    ContractUpdate,
    ContractResponse,
    ContractListResponse,
)
from backend.services.plan_generator import generate_annual_plan
from backend.services.pdf_parser import parse_contract_pdf
from backend.services.word_parser import parse_contract_word

router = APIRouter(prefix="/api/contracts", tags=["contracts"])


@router.get("", response_model=List[ContractListResponse])
def list_contracts(
    company_id: Optional[int] = Query(None),
    year: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(Contract)
    if company_id is not None:
        query = query.filter(Contract.company_id == company_id)
    if year is not None:
        query = query.filter(Contract.year == year)
    return query.order_by(Contract.id.desc()).all()


@router.post("", response_model=ContractResponse, status_code=201)
def create_contract(data: ContractCreate, db: Session = Depends(get_db)):
    # Check uniqueness of contract_no
    existing = (
        db.query(Contract)
        .filter(Contract.contract_no == data.contract_no)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Contract number '{data.contract_no}' already exists",
        )

    contract_data = data.model_dump(exclude={"water_plants"})
    contract = Contract(**contract_data)
    db.add(contract)
    db.flush()

    if data.water_plants:
        for wp_data in data.water_plants:
            wp_dict = wp_data.model_dump(exclude={"detection_items"})
            wp_dict["contract_id"] = contract.id
            wp = WaterPlant(**wp_dict)
            db.add(wp)
            db.flush()

            if wp_data.detection_items:
                for di_data in wp_data.detection_items:
                    di_dict = di_data.model_dump()
                    di_dict["water_plant_id"] = wp.id
                    di = DetectionItem(**di_dict)
                    db.add(di)

    db.commit()
    # Reload with relationships
    contract = (
        db.query(Contract)
        .options(
            joinedload(Contract.water_plants).joinedload(
                WaterPlant.detection_items
            )
        )
        .filter(Contract.id == contract.id)
        .first()
    )
    return contract


@router.get("/{contract_id}", response_model=ContractResponse)
def get_contract(contract_id: int, db: Session = Depends(get_db)):
    contract = (
        db.query(Contract)
        .options(
            joinedload(Contract.water_plants).joinedload(
                WaterPlant.detection_items
            )
        )
        .filter(Contract.id == contract_id)
        .first()
    )
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    return contract


@router.put("/{contract_id}", response_model=ContractResponse)
def update_contract(
    contract_id: int, data: ContractUpdate, db: Session = Depends(get_db)
):
    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    update_data = data.model_dump(exclude_unset=True)
    # Check uniqueness if contract_no is being changed
    if "contract_no" in update_data and update_data["contract_no"] != contract.contract_no:
        existing = (
            db.query(Contract)
            .filter(Contract.contract_no == update_data["contract_no"])
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Contract number '{update_data['contract_no']}' already exists",
            )
    for key, value in update_data.items():
        setattr(contract, key, value)
    db.commit()
    # Reload with relationships
    contract = (
        db.query(Contract)
        .options(
            joinedload(Contract.water_plants).joinedload(
                WaterPlant.detection_items
            )
        )
        .filter(Contract.id == contract_id)
        .first()
    )
    return contract


@router.delete("/{contract_id}")
def delete_contract(contract_id: int, db: Session = Depends(get_db)):
    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")

    # Delete related sampling tasks (via detection_items or by contract_no)
    wp_ids = (
        db.query(WaterPlant.id)
        .filter(WaterPlant.contract_id == contract_id)
        .all()
    )
    wp_id_list = [w[0] for w in wp_ids]

    if wp_id_list:
        di_ids = (
            db.query(DetectionItem.id)
            .filter(DetectionItem.water_plant_id.in_(wp_id_list))
            .all()
        )
        di_id_list = [d[0] for d in di_ids]
        if di_id_list:
            db.query(SamplingTask).filter(
                SamplingTask.detection_item_id.in_(di_id_list)
            ).delete(synchronize_session="fetch")

    # Also delete tasks matched by contract_no
    db.query(SamplingTask).filter(
        SamplingTask.contract_no == contract.contract_no,
        SamplingTask.source == "contract",
    ).delete(synchronize_session="fetch")

    # Delete contract (cascade handles water_plants and detection_items)
    db.delete(contract)
    db.commit()
    return {"detail": "Contract deleted"}


@router.post("/{contract_id}/generate-plan")
def trigger_plan_generation(contract_id: int, db: Session = Depends(get_db)):
    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    try:
        count = generate_annual_plan(db, contract_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"detail": f"Generated {count} tasks", "tasks_generated": count}


_ALLOWED_EXTENSIONS = {".pdf", ".docx"}


async def _parse_document(file: UploadFile) -> dict:
    filename = (file.filename or "").lower()
    ext = ""
    for e in _ALLOWED_EXTENSIONS:
        if filename.endswith(e):
            ext = e
            break
    if not ext:
        raise HTTPException(
            status_code=400,
            detail="仅支持 PDF 和 Word(.docx) 文件",
        )

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="上传文件为空")

    try:
        if ext == ".pdf":
            result = parse_contract_pdf(file_bytes)
        else:
            result = parse_contract_word(file_bytes)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"文件解析出错: {str(e)}",
        )

    return result


@router.post("/parse-document")
async def parse_document(file: UploadFile = File(...)):
    """Parse a contract PDF or Word file and return structured data for review."""
    return await _parse_document(file)
