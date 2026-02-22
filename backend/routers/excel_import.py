from datetime import date, datetime
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from io import BytesIO

from backend.database import get_db
from backend.services.excel_parser import import_contract_from_excel, generate_template

router = APIRouter(prefix="/api/import", tags=["excel_import"])


@router.post("/excel")
async def upload_excel(
    file: UploadFile = File(...),
    company_id: int = Form(...),
    contract_no: str = Form(...),
    year: int = Form(...),
    start_date: str = Form(...),
    end_date: str = Form(...),
    total_amount: float = Form(0.0),
    db: Session = Depends(get_db),
):
    if not file.filename or not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(
            status_code=400,
            detail="Only .xlsx or .xls files are accepted",
        )

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    # Parse dates
    try:
        parsed_start = _parse_date(start_date)
        parsed_end = _parse_date(end_date)
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid date format: {e}. Use YYYY-MM-DD.",
        )

    contract_data = {
        "contract_no": contract_no,
        "year": year,
        "start_date": parsed_start,
        "end_date": parsed_end,
        "total_amount": total_amount,
    }

    try:
        result = import_contract_from_excel(db, company_id, contract_data, file_bytes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error processing Excel file: {str(e)}",
        )

    return result


@router.get("/template")
def download_template():
    template_bytes = generate_template()
    buffer = BytesIO(template_bytes)
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": "attachment; filename=contract_template.xlsx"
        },
    )


def _parse_date(date_str: str) -> date:
    """Parse a date string in YYYY-MM-DD format."""
    for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(date_str.strip(), fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Cannot parse date: {date_str}")
