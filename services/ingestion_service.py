import email
import imaplib
import os
import threading
from datetime import datetime
from email.header import decode_header
from email.utils import parseaddr
from typing import Any, Dict, List, Optional

from db import repository
from services.compliance_engine import calculate_compliance_score
from services.extraction_service import ExtractionError, extract_structured_data
from services.ocr_service import validate_invoice_file
from services.risk_engine import calculate_risk, route_invoice


SUPPORTED_MIME_TYPES = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/jpg",
}


_health_lock = threading.Lock()
_health_state = {
    "last_poll": None,
    "last_success": None,
    "last_error": None,
    "failed_count": 0,
}


def _update_health(last_poll: bool = False, success: bool = False, error: Optional[str] = None):
    with _health_lock:
        now = datetime.utcnow().isoformat()
        if last_poll:
            _health_state["last_poll"] = now
        if success:
            _health_state["last_success"] = now
        if error:
            _health_state["last_error"] = error
            _health_state["failed_count"] += 1


def get_health_state() -> Dict[str, Any]:
    with _health_lock:
        return dict(_health_state)


def _decode_header_text(value: str) -> str:
    if not value:
        return ""
    decoded_parts = decode_header(value)
    result = []
    for part, enc in decoded_parts:
        if isinstance(part, bytes):
            result.append(part.decode(enc or "utf-8", errors="replace"))
        else:
            result.append(part)
    return "".join(result)


def _safe_filename(name: str) -> str:
    if not name:
        return f"invoice_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.bin"
    return "".join(ch if ch.isalnum() or ch in {".", "_", "-"} else "_" for ch in name)[:160]


def process_invoice_bytes(file_bytes: bytes, filename: str, mime_type: str, source: str = "UPLOAD") -> Dict[str, Any]:
    ok, reason = validate_invoice_file(file_bytes, mime_type)
    if not ok:
        _update_health(error=reason)
        return {"status": "FAILED", "error": reason}

    document_hash = repository.compute_document_hash(file_bytes)
    if repository.check_duplicate_hash(document_hash):
        return {"status": "DUPLICATE", "error": "Duplicate document hash", "document_hash": document_hash}

    storage_name = f"{source.lower()}/{datetime.utcnow().strftime('%Y%m%d')}/{_safe_filename(filename)}"
    file_url = repository.upload_invoice_file(file_bytes, storage_name, mime_type)
    if not file_url:
        _update_health(error="Failed to upload file to storage")
        return {"status": "FAILED", "error": "Failed to upload file to storage"}

    try:
        extracted = extract_structured_data(file_bytes, mime_type)
    except ExtractionError as ex:
        _update_health(error=str(ex))
        return {"status": "FAILED", "error": str(ex)}

    duplicate_vendor_invoice_number = repository.check_duplicate_vendor_invoice_number(
        extracted.get("vendor_name"), extracted.get("invoice_number")
    )

    compliance = calculate_compliance_score(extracted, duplicate_vendor_invoice_number)
    risk = calculate_risk(
        compliance_score=compliance["compliance_score"],
        confidence_score=float(extracted.get("confidence_score") or 0.0),
        reason_codes=list(compliance["reason_codes"]),
    )

    route_stage = route_invoice(
        confidence_score=float(extracted.get("confidence_score") or 0.0),
        risk_score=int(risk["risk_score"]),
        duplicate_found=duplicate_vendor_invoice_number,
    )

    flag_reason = ", ".join(risk["reason_codes"]) if risk["reason_codes"] else None

    payload = {
        "vendor_name": extracted.get("vendor_name"),
        "invoice_date": extracted.get("invoice_date"),
        "total_amount": extracted.get("total_amount"),
        "currency": extracted.get("currency"),
        "status": "READY" if route_stage == "READY_FOR_FINANCE_MANAGER" else "REVIEW_REQUIRED",
        "processing_status": "COMPLETED",
        "confidence_score": extracted.get("confidence_score", 0.0),
        "flag_reason": flag_reason,
        "file_url": file_url,
        "document_hash": document_hash,
        "ai_raw_data": {
            **extracted,
            "reason_codes": risk["reason_codes"],
            "compliance_score": compliance["compliance_score"],
            "routing_decision": route_stage,
            "source": source,
        },
        "ai_structured_output": extracted.get("ai_raw_structured", {}),
        "created_by": "MAIL_BOT" if source == "EMAIL" else "SYSTEM",
        "last_reviewed_by": None,
        "ai_explanations": extracted.get("explanations", {}),
        "risk_score": risk["risk_score"],
        "risk_level": risk["risk_level"],
        "approval_stage": "REVIEWED" if route_stage == "READY_FOR_FINANCE_MANAGER" else "UPLOADED",
        "reviewed_by": None,
        "approved_by": None,
        "approval_timestamp": None,
        "audited": False,
        "ai_version": os.getenv("GEMINI_MODEL", "gemini-flash-latest"),
        "reprocessed_at": None,
    }

    created = repository.create_invoice(payload)
    if not created:
        _update_health(error="Database insert failed")
        return {"status": "FAILED", "error": "Database insert failed"}

    _update_health(success=True)
    return {
        "status": "SUCCESS",
        "invoice": created,
        "compliance_score": compliance["compliance_score"],
        "risk_score": risk["risk_score"],
        "reason_codes": risk["reason_codes"],
        "routing_decision": route_stage,
    }


def ingest_from_email(max_messages: int = 20) -> Dict[str, Any]:
    _update_health(last_poll=True)

    required = ["IMAP_HOST", "IMAP_USER", "IMAP_PASSWORD"]
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        error = f"Missing env: {', '.join(missing)}"
        _update_health(error=error)
        return {"status": "FAILED", "errors": [error], "ingested": 0}

    host = os.getenv("IMAP_HOST", "").strip()
    port = int((os.getenv("IMAP_PORT", "993") or "993").strip())
    user = os.getenv("IMAP_USER", "").strip()
    password = os.getenv("IMAP_PASSWORD", "").strip().replace(" ", "")
    folder = os.getenv("IMAP_FOLDER", "INBOX").strip()

    result = {
        "status": "SUCCESS",
        "messages_scanned": 0,
        "attachments_found": 0,
        "ingested": 0,
        "duplicates": 0,
        "failed": 0,
        "errors": [],
    }

    imap = None
    try:
        imap = imaplib.IMAP4_SSL(host, port)
        imap.login(user, password)
        select_status, _ = imap.select(folder)
        if select_status != "OK":
            raise RuntimeError(f"Unable to select mailbox folder: {folder}")

        search_status, data = imap.search(None, "UNSEEN")
        if search_status != "OK":
            raise RuntimeError("Unable to search mailbox")

        message_ids = data[0].split()[-max_messages:]
        for message_id in message_ids:
            result["messages_scanned"] += 1
            fetch_status, msg_data = imap.fetch(message_id, "(RFC822)")
            if fetch_status != "OK" or not msg_data or not msg_data[0]:
                result["failed"] += 1
                result["errors"].append(f"Failed to fetch message {message_id.decode(errors='ignore')}")
                continue

            msg = email.message_from_bytes(msg_data[0][1])
            sender = parseaddr(msg.get("From", ""))[1]
            _ = sender

            for part in msg.walk():
                disposition = str(part.get("Content-Disposition", "")).lower()
                if "attachment" not in disposition:
                    continue
                mime_type = part.get_content_type()
                if mime_type not in SUPPORTED_MIME_TYPES:
                    continue

                filename = _safe_filename(_decode_header_text(part.get_filename() or "invoice.bin"))
                file_bytes = part.get_payload(decode=True)
                if not file_bytes:
                    continue

                result["attachments_found"] += 1
                processed = process_invoice_bytes(file_bytes, filename, mime_type, source="EMAIL")

                if processed["status"] == "SUCCESS":
                    result["ingested"] += 1
                elif processed["status"] == "DUPLICATE":
                    result["duplicates"] += 1
                else:
                    result["failed"] += 1
                    if processed.get("error"):
                        result["errors"].append(processed["error"])

            imap.store(message_id, "+FLAGS", "\\Seen")

    except Exception as ex:
        result["status"] = "FAILED"
        result["errors"].append(str(ex))
        _update_health(error=str(ex))
    finally:
        if imap:
            try:
                imap.close()
            except Exception:
                pass
            try:
                imap.logout()
            except Exception:
                pass

    if result["errors"] and result["ingested"] == 0:
        result["status"] = "FAILED"
    elif result["errors"] or result["failed"] > 0:
        result["status"] = "PARTIAL"

    if result["status"] in ["SUCCESS", "PARTIAL"]:
        _update_health(success=True)

    return result
