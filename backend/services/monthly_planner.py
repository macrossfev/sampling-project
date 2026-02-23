"""Generate monthly sampling plans with trip grouping and scheduling.

Supports three scheduling schemes:
- compact: Minimize days, back-to-back scheduling
- balanced: Even spacing with rest days between trips
- relaxed: Maximum spacing, one trip type per week
"""

import calendar
from datetime import date, timedelta
from sqlalchemy.orm import Session

from backend.models import Company, SamplingTrip, Contract, WaterPlant, DetectionItem


def generate_monthly_plan(db: Session, year: int, month: int, scheme: str = "balanced") -> dict:
    """Generate a monthly sampling plan.

    Returns dict with 'trips' list and 'stats' summary.
    """
    # Delete existing trips for this month
    db.query(SamplingTrip).filter(
        SamplingTrip.year == year,
        SamplingTrip.month == month,
    ).delete(synchronize_session="fetch")

    # Get all companies that have active contracts covering this month
    target_date = date(year, month, 1)
    companies = (
        db.query(Company)
        .join(Contract)
        .filter(
            Contract.start_date <= date(year, month, calendar.monthrange(year, month)[1]),
            Contract.end_date >= target_date,
        )
        .all()
    )

    if not companies:
        db.commit()
        return {"trips": [], "stats": {"total": 0, "two_day": 0, "single_day": 0}}

    # Separate by trip type
    two_day = [c for c in companies if c.trip_type == "two_day"]
    single_day = [c for c in companies if c.trip_type != "two_day"]

    # Build sampling notes for each company from their contract detection items
    company_notes = {}
    for c in companies:
        notes_parts = []
        for contract in c.contracts:
            if contract.start_date and contract.start_date > date(year, month, calendar.monthrange(year, month)[1]):
                continue
            if contract.end_date and contract.end_date < target_date:
                continue
            for wp in contract.water_plants:
                # Collect items that are due this month
                items_for_wp = []
                for di in wp.detection_items:
                    if _is_plannable(di) and _is_due(di, month):
                        level_tag = ""
                        dl = getattr(di, "detection_level", None) or ""
                        if dl:
                            level_tag = f"({dl})"
                        items_for_wp.append(f"{di.sample_type or '样品'}{level_tag}")
                if items_for_wp:
                    notes_parts.append(f"{wp.name}: {'＋'.join(items_for_wp)}")
        company_notes[c.id] = "\n".join(notes_parts) if notes_parts else ""

    # Calculate working days (skip weekends)
    _, days_in_month = calendar.monthrange(year, month)
    workdays = []
    for d in range(1, days_in_month + 1):
        dt = date(year, month, d)
        if dt.weekday() < 5:  # Mon-Fri
            workdays.append(dt)

    # Schedule trips based on scheme
    trips = _schedule(db, year, month, two_day, single_day, company_notes, workdays, scheme)

    db.add_all(trips)
    db.commit()

    return {
        "trips": len(trips),
        "stats": {
            "total": len(trips),
            "two_day": sum(1 for t in trips if t.trip_type == "two_day"),
            "single_day": sum(1 for t in trips if t.trip_type == "single_day"),
        },
    }


_FULL_ANALYSIS_MONTHS = [6, 11]

_SKIP_KEYWORDS = ["采样费", "服务费", "应急", "待定"]


def _is_plannable(di) -> bool:
    """Return False for fee-only or contingency items that should not appear in plans."""
    if not (di.detection_project or "").strip():
        return False
    text = (di.sample_type or "") + (di.detection_project or "")
    return not any(kw in text for kw in _SKIP_KEYWORDS)


def _is_due(di: DetectionItem, month: int) -> bool:
    """Check if a detection item is due in the given month.

    Detection level logic:
    - 全分析: only due in designated full-analysis months (6, 11)
    - 常规: due every month EXCEPT full-analysis months (replaced by 全分析)
    - None/empty: follow normal frequency rules
    """
    level = getattr(di, "detection_level", None) or ""

    if level == "全分析":
        return month in _FULL_ANALYSIS_MONTHS
    if level == "常规":
        if month in _FULL_ANALYSIS_MONTHS:
            return False
        return _check_frequency(di, month)

    return _check_frequency(di, month)


def _check_frequency(di: DetectionItem, month: int) -> bool:
    """Check if a detection item is due based on its frequency setting."""
    ft = di.frequency_type
    if not ft or ft == "月":
        return True
    if ft == "季":
        return month in (3, 6, 9, 12)
    if ft == "半年":
        return month in (6, 12)
    if ft == "年":
        return month == 6
    return True


def _schedule(db, year, month, two_day_companies, single_day_companies,
              company_notes, workdays, scheme):
    """Schedule trips across 4 groups using the selected scheme."""
    trips = []
    num_groups = 4

    # Scheme parameters
    if scheme == "compact":
        gap_after_two_day = 0  # No gap between batches
        gap_after_single = 0
    elif scheme == "relaxed":
        gap_after_two_day = 2  # 2 rest days after two-day batch
        gap_after_single = 1
    else:  # balanced
        gap_after_two_day = 1  # 1 rest day after two-day batch
        gap_after_single = 0

    day_idx = 0  # Pointer into workdays

    # Phase 1: Schedule two-day trips (each takes 2 consecutive workdays)
    batches_2d = [two_day_companies[i:i + num_groups]
                  for i in range(0, len(two_day_companies), num_groups)]

    for batch in batches_2d:
        if day_idx + 1 >= len(workdays):
            break
        d1 = workdays[day_idx]
        d2 = workdays[day_idx + 1] if day_idx + 1 < len(workdays) else d1

        for g, company in enumerate(batch):
            cname = company.short_name or company.name
            route = (f"{d1.month}.{d1.day}公司出发去{cname}\n"
                     f"{d2.month}.{d2.day}{cname}采样后返回公司")
            trip = SamplingTrip(
                year=year, month=month, group_no=g + 1,
                company_id=company.id, trip_type="two_day",
                start_date=d1, end_date=d2,
                route_notes=route,
                sampling_notes=company_notes.get(company.id, ""),
            )
            trips.append(trip)

        day_idx += 2 + gap_after_two_day

    # Phase 2: Schedule single-day trips (each takes 1 workday)
    batches_1d = [single_day_companies[i:i + num_groups]
                  for i in range(0, len(single_day_companies), num_groups)]

    for batch in batches_1d:
        if day_idx >= len(workdays):
            break
        d1 = workdays[day_idx]

        for g, company in enumerate(batch):
            cname = company.short_name or company.name
            route = (f"{d1.month}.{d1.day}公司出发{cname}采样后返回公司")
            trip = SamplingTrip(
                year=year, month=month, group_no=g + 1,
                company_id=company.id, trip_type="single_day",
                start_date=d1, end_date=d1,
                route_notes=route,
                sampling_notes=company_notes.get(company.id, ""),
            )
            trips.append(trip)

        day_idx += 1 + gap_after_single

    return trips
