from datetime import date
from sqlalchemy.orm import Session
from backend.models import Contract, DetectionItem, SamplingTask, WaterPlant
from backend.services.monthly_planner import _is_plannable


def _parse_custom_months(raw: str | None) -> list[int] | None:
    """Parse comma-separated custom month string. Returns None if not set."""
    if not raw or not raw.strip():
        return None
    try:
        months = [int(m.strip()) for m in raw.split(",") if m.strip()]
        result = sorted(m for m in months if 1 <= m <= 12)
        return result if result else None
    except ValueError:
        return None


def generate_annual_plan(db: Session, contract_id: int) -> int:
    """Generate annual sampling plan from contract detection items.

    Deletes existing contract-sourced tasks for this contract before
    regenerating so the operation is idempotent.

    Returns the number of tasks created.
    """
    contract = (
        db.query(Contract)
        .filter(Contract.id == contract_id)
        .first()
    )
    if contract is None:
        raise ValueError(f"Contract {contract_id} not found")

    # Determine the month range covered by the contract
    if contract.start_date and contract.end_date:
        start_month = contract.start_date.month
        end_month = contract.end_date.month
        start_year = contract.start_date.year
        end_year = contract.end_date.year
    else:
        start_month = 1
        end_month = 12
        start_year = contract.year or date.today().year
        end_year = start_year

    plan_year = contract.year or start_year

    # Delete existing contract-sourced tasks for this contract
    existing_task_ids = (
        db.query(SamplingTask.id)
        .join(DetectionItem, SamplingTask.detection_item_id == DetectionItem.id)
        .join(WaterPlant, DetectionItem.water_plant_id == WaterPlant.id)
        .filter(
            WaterPlant.contract_id == contract_id,
            SamplingTask.source == "contract",
        )
        .all()
    )
    if existing_task_ids:
        ids = [t[0] for t in existing_task_ids]
        db.query(SamplingTask).filter(SamplingTask.id.in_(ids)).delete(
            synchronize_session="fetch"
        )

    # Also delete by contract_no in case detection_item was removed
    db.query(SamplingTask).filter(
        SamplingTask.contract_no == contract.contract_no,
        SamplingTask.source == "contract",
    ).delete(synchronize_session="fetch")

    water_plants = (
        db.query(WaterPlant)
        .filter(WaterPlant.contract_id == contract_id)
        .all()
    )

    # Build the full set of valid months (handle same-year or cross-year)
    valid_months = _build_valid_months(start_year, start_month, end_year, end_month)

    tasks_created = 0

    for wp in water_plants:
        detection_items = (
            db.query(DetectionItem)
            .filter(DetectionItem.water_plant_id == wp.id)
            .all()
        )
        for item in detection_items:
            if not _is_plannable(item):
                continue
            level = (item.detection_level or "").strip()

            # Check for per-item custom month selection
            cm = _parse_custom_months(getattr(item, "custom_months", None))

            if cm is not None:
                months = [m for m in cm if m in valid_months]
            else:
                months = _get_months_for_frequency(
                    item.frequency_type, valid_months, plan_year
                )
            freq_value = item.frequency_value or 1

            for m in months:
                for _ in range(freq_value):
                    task = SamplingTask(
                        source="contract",
                        detection_item_id=item.id,
                        company_id=contract.company_id,
                        water_plant_name=wp.name,
                        contract_no=contract.contract_no,
                        year=plan_year,
                        month=m,
                        planned_date=date(plan_year, m, 15),
                        sample_type=item.sample_type,
                        detection_project=item.detection_project,
                        detection_standard=item.detection_standard,
                        status="待采样",
                    )
                    db.add(task)
                    tasks_created += 1

    db.commit()
    return tasks_created


def _build_valid_months(
    start_year: int, start_month: int, end_year: int, end_month: int
) -> list[int]:
    """Return a list of month numbers (1-12) covered by the contract within a
    single plan year. For simplicity, we flatten to months 1-12."""
    if start_year == end_year:
        return list(range(start_month, end_month + 1))
    # Cross-year: assume we want all 12 months
    return list(range(1, 13))


def _get_months_for_frequency(
    frequency_type: str | None,
    valid_months: list[int],
    plan_year: int,
) -> list[int]:
    """Return the months in which tasks should be generated based on frequency."""
    if not frequency_type:
        return valid_months

    ft = frequency_type.strip()

    if ft in ("月", "monthly"):
        return valid_months

    if ft in ("季", "quarterly"):
        quarterly_months = [3, 6, 9, 12]
        return [m for m in quarterly_months if m in valid_months]

    if ft in ("半年", "semi-annual"):
        semi_months = [6, 12]
        return [m for m in semi_months if m in valid_months]

    if ft in ("年", "annual"):
        # Mid-year if available, otherwise last valid month
        if 6 in valid_months:
            return [6]
        return [valid_months[-1]] if valid_months else []

    # Default: treat as monthly
    return valid_months
