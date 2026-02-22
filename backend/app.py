import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates

from backend.database import engine, Base
from backend.routers import (
    companies,
    contracts,
    water_plants,
    detection_items,
    tasks,
    dashboard,
    excel_import,
    monthly_plan,
)

TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create all tables on startup
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Water Quality Sampling Scheduling System",
    description="Backend API for managing water quality sampling tasks",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware - allow all origins for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Jinja2 templates
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# Include API routers
app.include_router(companies.router)
app.include_router(contracts.router)
app.include_router(water_plants.router)
app.include_router(detection_items.router)
app.include_router(tasks.router)
app.include_router(dashboard.router)
app.include_router(excel_import.router)
app.include_router(monthly_plan.router)


# ---------- Page routes (server-side rendered) ----------

@app.get("/")
def page_dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "active_page": "dashboard",
    })


@app.get("/companies")
def page_companies(request: Request):
    return templates.TemplateResponse("companies.html", {
        "request": request,
        "active_page": "companies",
    })


@app.get("/contracts")
def page_contracts(request: Request):
    return templates.TemplateResponse("contracts.html", {
        "request": request,
        "active_page": "contracts",
    })


@app.get("/tasks")
def page_tasks(request: Request):
    return templates.TemplateResponse("tasks.html", {
        "request": request,
        "active_page": "tasks",
    })


@app.get("/pdf-import")
def page_pdf_import(request: Request):
    return templates.TemplateResponse("pdf_import.html", {
        "request": request,
        "active_page": "pdf_import",
    })


@app.get("/monthly-plan")
def page_monthly_plan(request: Request):
    return templates.TemplateResponse("monthly_plan.html", {
        "request": request,
        "active_page": "monthly_plan",
    })
