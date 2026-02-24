from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from auth.dependencies import get_current_user
from db.repository import get_dashboard_metrics, get_invoice, list_invoices
from services.ingestion_service import get_health_state

router = APIRouter(tags=["pages"])
templates = Jinja2Templates(directory="templates")


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request, current_user=Depends(get_current_user)):
    invoices = list_invoices(limit=100)
    metrics = get_dashboard_metrics()
    health = get_health_state()
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "invoices": invoices[:20],
            "metrics": metrics,
            "health": health,
            "current_user": current_user,
        },
    )


@router.get("/review-queue", response_class=HTMLResponse)
def review_queue(
    request: Request,
    risk: str | None = Query(default=None),
    current_user=Depends(get_current_user),
):
    invoices = list_invoices(limit=200)
    review_items = [item for item in invoices if item.get("approval_stage") in ["UPLOADED", "REVIEWED"]]
    if risk:
        review_items = [item for item in review_items if str(item.get("risk_level", "")).upper() == risk.upper()]

    return templates.TemplateResponse(
        "review_queue.html",
        {
            "request": request,
            "invoices": review_items,
            "selected_risk": risk or "",
            "current_user": current_user,
        },
    )


@router.get("/invoice/{invoice_id}", response_class=HTMLResponse)
def invoice_detail(request: Request, invoice_id: int, current_user=Depends(get_current_user)):
    invoice = get_invoice(invoice_id)
    return templates.TemplateResponse(
        "invoice_detail.html",
        {
            "request": request,
            "invoice": invoice,
            "current_user": current_user,
        },
    )
