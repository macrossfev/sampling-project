from datetime import date
from typing import Optional, List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, case

from backend.database import get_db
from backend.models import SamplingTask, Company
from backend.schemas import (
    DashboardSummary,
    CompanyStats,
    StatusBreakdown,
    MonthlyStats,
    MonthlyTaskGroup,
    SamplingTaskResponse,
)

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummary)
def get_summary(
    year: int = Query(default=None, description="Year to summarize"),
    db: Session = Depends(get_db),
):
    if year is None:
        year = date.today().year

    base_query = db.query(SamplingTask).filter(SamplingTask.year == year)

    total_tasks = base_query.count()

    completed_tasks = base_query.filter(
        SamplingTask.status == "已出报告"
    ).count()

    # Overdue: status is 待采样 and planned_date < today
    today = date.today()
    overdue_tasks = base_query.filter(
        SamplingTask.status == "待采样",
        SamplingTask.planned_date < today,
    ).count()

    # By company
    company_rows = (
        db.query(
            SamplingTask.company_id,
            Company.name,
            func.count(SamplingTask.id).label("total"),
            func.sum(
                case(
                    (SamplingTask.status == "已出报告", 1),
                    else_=0,
                )
            ).label("completed"),
        )
        .join(Company, SamplingTask.company_id == Company.id)
        .filter(SamplingTask.year == year)
        .group_by(SamplingTask.company_id, Company.name)
        .all()
    )
    by_company = [
        CompanyStats(
            company_id=row[0],
            company_name=row[1],
            total=row[2],
            completed=int(row[3] or 0),
        )
        for row in company_rows
    ]

    # By status
    status_rows = (
        db.query(
            SamplingTask.status,
            func.count(SamplingTask.id),
        )
        .filter(SamplingTask.year == year)
        .group_by(SamplingTask.status)
        .all()
    )
    by_status = [
        StatusBreakdown(status=row[0], count=row[1]) for row in status_rows
    ]

    return DashboardSummary(
        year=year,
        total_tasks=total_tasks,
        completed_tasks=completed_tasks,
        overdue_tasks=overdue_tasks,
        by_company=by_company,
        by_status=by_status,
    )


@router.get("/monthly", response_model=MonthlyStats)
def get_monthly(
    year: int = Query(default=None),
    month: int = Query(default=None),
    db: Session = Depends(get_db),
):
    if year is None:
        year = date.today().year
    if month is None:
        month = date.today().month

    tasks = (
        db.query(SamplingTask)
        .filter(SamplingTask.year == year, SamplingTask.month == month)
        .order_by(SamplingTask.company_id, SamplingTask.id)
        .all()
    )

    # Group by company
    company_map: dict[int, dict] = {}
    for task in tasks:
        cid = task.company_id
        if cid not in company_map:
            company = db.query(Company).filter(Company.id == cid).first()
            company_map[cid] = {
                "company_id": cid,
                "company_name": company.name if company else "Unknown",
                "tasks": [],
            }
        company_map[cid]["tasks"].append(task)

    groups = []
    for cid, data in company_map.items():
        groups.append(
            MonthlyTaskGroup(
                company_id=data["company_id"],
                company_name=data["company_name"],
                tasks=[SamplingTaskResponse.model_validate(t) for t in data["tasks"]],
            )
        )

    return MonthlyStats(
        year=year,
        month=month,
        total_tasks=len(tasks),
        groups=groups,
    )
