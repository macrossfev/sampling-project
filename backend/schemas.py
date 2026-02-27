from datetime import date, datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict


# ---------- Company ----------

class CompanyCreate(BaseModel):
    name: str
    short_name: Optional[str] = None
    group_name: Optional[str] = None
    address: Optional[str] = None
    contact_person: Optional[str] = None
    contact_phone: Optional[str] = None
    trip_type: str = "single_day"


class CompanyUpdate(BaseModel):
    name: Optional[str] = None
    short_name: Optional[str] = None
    group_name: Optional[str] = None
    address: Optional[str] = None
    contact_person: Optional[str] = None
    contact_phone: Optional[str] = None
    trip_type: Optional[str] = None


class CompanyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    short_name: Optional[str] = None
    group_name: Optional[str] = None
    address: Optional[str] = None
    contact_person: Optional[str] = None
    contact_phone: Optional[str] = None
    trip_type: str = "single_day"
    created_at: Optional[datetime] = None


# ---------- DetectionItem ----------

class DetectionItemCreate(BaseModel):
    water_plant_id: Optional[int] = None
    sample_type: Optional[str] = None
    detection_project: Optional[str] = None
    detection_standard: Optional[str] = None
    frequency_type: Optional[str] = None
    frequency_value: int = 1
    unit_price: Optional[float] = None
    annual_count: Optional[int] = None
    subtotal: Optional[float] = None
    detection_level: Optional[str] = None
    custom_months: Optional[str] = None


class DetectionItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    water_plant_id: int
    sample_type: Optional[str] = None
    detection_project: Optional[str] = None
    detection_standard: Optional[str] = None
    frequency_type: Optional[str] = None
    frequency_value: int = 1
    unit_price: Optional[float] = None
    annual_count: Optional[int] = None
    subtotal: Optional[float] = None
    detection_level: Optional[str] = None
    custom_months: Optional[str] = None
    created_at: Optional[datetime] = None


# ---------- WaterPlant ----------

class WaterPlantCreate(BaseModel):
    name: str
    scale: Optional[str] = None
    contract_id: Optional[int] = None
    sampling_points: Optional[str] = None
    detection_items: Optional[List[DetectionItemCreate]] = None


class WaterPlantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    scale: Optional[str] = None
    contract_id: int
    sampling_points: Optional[str] = None
    created_at: Optional[datetime] = None
    detection_items: List[DetectionItemResponse] = []


# ---------- Contract ----------

class ContractCreate(BaseModel):
    contract_no: str
    company_id: int
    year: Optional[int] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    total_amount: Optional[float] = None
    full_analysis_months: Optional[str] = "6,11"
    notes: Optional[str] = None
    water_plants: Optional[List[WaterPlantCreate]] = None


class ContractUpdate(BaseModel):
    contract_no: Optional[str] = None
    company_id: Optional[int] = None
    year: Optional[int] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    total_amount: Optional[float] = None
    full_analysis_months: Optional[str] = None
    notes: Optional[str] = None
    water_plants: Optional[List[WaterPlantCreate]] = None


class ContractResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    contract_no: str
    company_id: int
    year: Optional[int] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    total_amount: Optional[float] = None
    full_analysis_months: Optional[str] = "6,11"
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    water_plants: List[WaterPlantResponse] = []


class ContractListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    contract_no: str
    company_id: int
    year: Optional[int] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    total_amount: Optional[float] = None
    full_analysis_months: Optional[str] = "6,11"
    notes: Optional[str] = None
    created_at: Optional[datetime] = None


# ---------- SamplingTask ----------

class SamplingTaskCreate(BaseModel):
    company_id: int
    water_plant_name: Optional[str] = None
    contract_no: Optional[str] = None
    year: Optional[int] = None
    month: Optional[int] = None
    planned_date: Optional[date] = None
    sample_type: Optional[str] = None
    detection_project: Optional[str] = None
    detection_standard: Optional[str] = None
    status: str = "待采样"
    executor: Optional[str] = None
    notes: Optional[str] = None


class SamplingTaskUpdate(BaseModel):
    status: Optional[str] = None
    actual_date: Optional[date] = None
    executor: Optional[str] = None
    notes: Optional[str] = None
    planned_date: Optional[date] = None
    water_plant_name: Optional[str] = None
    sample_type: Optional[str] = None
    detection_project: Optional[str] = None
    detection_standard: Optional[str] = None
    month: Optional[int] = None
    year: Optional[int] = None


class SamplingTaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source: str = "contract"
    detection_item_id: Optional[int] = None
    company_id: int
    water_plant_name: Optional[str] = None
    contract_no: Optional[str] = None
    year: Optional[int] = None
    month: Optional[int] = None
    planned_date: Optional[date] = None
    sample_type: Optional[str] = None
    detection_project: Optional[str] = None
    detection_standard: Optional[str] = None
    status: str = "待采样"
    actual_date: Optional[date] = None
    executor: Optional[str] = None
    notes: Optional[str] = None
    created_at: Optional[datetime] = None


class BatchStatusUpdate(BaseModel):
    task_ids: List[int]
    status: str


# ---------- SamplingTrip ----------

class SamplingTripCreate(BaseModel):
    year: int
    month: int
    group_no: int
    company_id: int
    trip_type: str = "single_day"
    start_date: date
    end_date: date
    route_notes: Optional[str] = None
    sampling_notes: Optional[str] = None


class SamplingTripUpdate(BaseModel):
    group_no: Optional[int] = None
    company_id: Optional[int] = None
    trip_type: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    route_notes: Optional[str] = None
    sampling_notes: Optional[str] = None
    status: Optional[str] = None


class SamplingTripResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    year: int
    month: int
    group_no: int
    company_id: int
    company_name: Optional[str] = None
    company_short_name: Optional[str] = None
    trip_type: str = "single_day"
    start_date: date
    end_date: date
    route_notes: Optional[str] = None
    sampling_notes: Optional[str] = None
    status: str = "待安排"
    created_at: Optional[datetime] = None


class MonthlyPlanGenerate(BaseModel):
    year: int
    month: int
    scheme: str = "balanced"  # compact / balanced / relaxed
    group_first: bool = False  # 优先同集团一起采


# ---------- Dashboard ----------

class CompanyStats(BaseModel):
    company_id: int
    company_name: str
    total: int
    completed: int


class StatusBreakdown(BaseModel):
    status: str
    count: int


class DashboardSummary(BaseModel):
    year: int
    total_tasks: int
    completed_tasks: int
    overdue_tasks: int
    by_company: List[CompanyStats]
    by_status: List[StatusBreakdown]


class MonthlyTaskGroup(BaseModel):
    company_id: int
    company_name: str
    tasks: List[SamplingTaskResponse]


class MonthlyStats(BaseModel):
    year: int
    month: int
    total_tasks: int
    groups: List[MonthlyTaskGroup]
