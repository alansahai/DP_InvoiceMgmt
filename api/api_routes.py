from typing import Any, Dict

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel

from auth.dependencies import get_current_user, require_role
from db.repository import get_invoice, list_invoices, update_route
from services.ingestion_service import ingest_from_email, process_invoice_bytes

router = APIRouter(prefix="/api", tags=["api"])


class RouteRequest(BaseModel):
    route_stage: str
    reviewed_by: str | None = None


@router.post("/upload-invoice")
async def upload_invoice(
    file: UploadFile = File(...),
    _user: Dict[str, Any] = Depends(require_role(["AP_CLERK", "ADMIN"])),
) -> Dict[str, Any]:
    file_bytes = await file.read()
    result = process_invoice_bytes(
        file_bytes=file_bytes,
        filename=file.filename or "invoice.bin",
        mime_type=file.content_type or "application/octet-stream",
        source="UPLOAD",
    )
    if result.get("status") == "FAILED":
        raise HTTPException(status_code=422, detail=result)
    return result


@router.post("/ingest-email")
def ingest_email(_user: Dict[str, Any] = Depends(require_role(["AP_CLERK", "ADMIN"]))) -> Dict[str, Any]:
    return ingest_from_email()


@router.get("/invoices")
def get_invoices(_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    return {"items": list_invoices()}


@router.get("/invoice/{invoice_id}")
def get_invoice_by_id(invoice_id: int, _user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    invoice = get_invoice(invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return invoice


@router.post("/route/{invoice_id}")
def route_invoice(
    invoice_id: int,
    request: RouteRequest,
    _user: Dict[str, Any] = Depends(require_role(["FINANCE_MANAGER", "ADMIN"])),
) -> Dict[str, Any]:
    updated = update_route(invoice_id, request.route_stage, request.reviewed_by)
    if not updated:
        raise HTTPException(status_code=404, detail="Invoice not found or update failed")
    return updated
