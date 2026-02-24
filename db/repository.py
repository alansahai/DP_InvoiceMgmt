import hashlib
from datetime import datetime
from typing import Any, Dict, List, Optional

from db.client import supabase


def upload_invoice_file(file_bytes: bytes, file_name: str, content_type: str) -> Optional[str]:
    try:
        supabase.storage.from_("invoices").upload(
            path=file_name,
            file=file_bytes,
            file_options={"content-type": content_type, "upsert": "true"},
        )
        return supabase.storage.from_("invoices").get_public_url(file_name)
    except Exception:
        return None


def create_user(email: str, role: str, name: str = "") -> Optional[Dict[str, Any]]:
    """Create a user without storing password (password is stored in-memory in auth/routes.py)"""
    # Generate name from email if not provided
    if not name:
        name = email.split("@")[0].title()
    
    payload = {
        "email": email,
        "role": role,
        "name": name,
    }
    try:
        response = supabase.table("users").insert(payload).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        print(f"[DB ERROR] create_user failed for {email}: {type(e).__name__}: {e}")
        return None


def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    try:
        response = supabase.table("users").select("*").eq("email", email).limit(1).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        print(f"[DB ERROR] get_user_by_email failed for {email}: {type(e).__name__}: {e}")
        return None


def list_users(limit: int = 200) -> List[Dict[str, Any]]:
    try:
        response = (
            supabase.table("users")
            .select("id,email,role,created_at")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return response.data or []
    except Exception:
        return []


def compute_document_hash(file_bytes: bytes) -> str:
    return hashlib.sha256(file_bytes).hexdigest()


def check_duplicate_hash(document_hash: str) -> bool:
    if not document_hash:
        return False
    try:
        response = supabase.table("invoices").select("id").eq("document_hash", document_hash).execute()
        return bool(response.data)
    except Exception:
        return False


def check_duplicate_vendor_invoice_number(vendor_name: Optional[str], invoice_number: Optional[str]) -> bool:
    if not vendor_name or not invoice_number:
        return False
    try:
        response = (
            supabase.table("invoices")
            .select("id")
            .eq("vendor_name", vendor_name)
            .contains("ai_raw_data", {"invoice_number": invoice_number})
            .execute()
        )
        return bool(response.data)
    except Exception:
        return False


def create_invoice(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    try:
        response = supabase.table("invoices").insert(payload).execute()
        return response.data[0] if response.data else None
    except Exception as write_error:
        if "document_hash" in str(write_error):
            fallback = dict(payload)
            fallback.pop("document_hash", None)
            response = supabase.table("invoices").insert(fallback).execute()
            return response.data[0] if response.data else None
        return None


def get_invoice(invoice_id: int) -> Optional[Dict[str, Any]]:
    try:
        response = supabase.table("invoices").select("*").eq("id", invoice_id).limit(1).execute()
        return response.data[0] if response.data else None
    except Exception:
        return None


def list_invoices(limit: int = 200) -> List[Dict[str, Any]]:
    try:
        response = supabase.table("invoices").select("*").order("created_at", desc=True).limit(limit).execute()
        return response.data or []
    except Exception:
        return []


def update_route(invoice_id: int, route_stage: str, reviewed_by: Optional[str] = None) -> Optional[Dict[str, Any]]:
    payload = {
        "approval_stage": route_stage,
        "reviewed_by": reviewed_by,
        "last_reviewed_by": reviewed_by,
        "approval_timestamp": datetime.utcnow().isoformat() if route_stage in ["READY_FOR_FINANCE_MANAGER", "APPROVED", "REJECTED"] else None,
    }
    try:
        response = supabase.table("invoices").update(payload).eq("id", invoice_id).execute()
        return response.data[0] if response.data else None
    except Exception:
        return None


def get_dashboard_metrics() -> Dict[str, Any]:
    invoices = list_invoices(limit=1000)
    total_processed = len(invoices)
    flagged = 0
    duplicates = 0
    processing_times = []

    for item in invoices:
        risk_level = (item.get("risk_level") or "").upper()
        reason = (item.get("flag_reason") or "").upper()
        if risk_level in ["MEDIUM", "HIGH"] or "COMPLIANCE" in reason or "DUP" in reason:
            flagged += 1
        if "DUP" in reason:
            duplicates += 1

        created_at = item.get("created_at")
        reviewed_at = item.get("approval_timestamp")
        if created_at and reviewed_at:
            try:
                start = datetime.fromisoformat(str(created_at).replace("Z", "+00:00"))
                end = datetime.fromisoformat(str(reviewed_at).replace("Z", "+00:00"))
                processing_times.append((end - start).total_seconds() / 60)
            except Exception:
                pass

    avg_processing_time = round(sum(processing_times) / len(processing_times), 2) if processing_times else 0

    return {
        "total_processed": total_processed,
        "flagged": flagged,
        "duplicates": duplicates,
        "avg_processing_time_min": avg_processing_time,
    }
