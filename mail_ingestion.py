import os
import imaplib
import email
from email.header import decode_header
from email.utils import parseaddr
from datetime import datetime
from typing import Dict, List, Tuple

import processor
from compliance import evaluate_invoice_compliance
from database import upload_file, save_invoice_record, is_duplicate, compute_document_hash, is_duplicate_hash


SUPPORTED_MIME_TYPES = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/jpg",
}

SUPPORTED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _decode_header_text(value: str) -> str:
    if not value:
        return ""
    decoded_parts = decode_header(value)
    result = []
    for part, encoding in decoded_parts:
        if isinstance(part, bytes):
            result.append(part.decode(encoding or "utf-8", errors="replace"))
        else:
            result.append(part)
    return "".join(result)


def _safe_filename(name: str) -> str:
    if not name:
        return f"invoice_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.bin"
    clean = "".join(ch if ch.isalnum() or ch in {".", "_", "-"} else "_" for ch in name)
    return clean[:150] or "invoice.bin"


def _allowed_sender(sender_email: str) -> bool:
    raw = os.getenv("MAIL_ALLOWED_SENDERS", "").strip()
    if not raw:
        return True

    allowed = {s.strip().lower() for s in raw.split(",") if s.strip()}
    return sender_email.lower() in allowed


def _subject_matches_filters(subject: str) -> bool:
    raw = os.getenv("MAIL_SUBJECT_KEYWORDS", "").strip()
    if not raw:
        return True

    subject_lower = (subject or "").lower()
    keywords = [k.strip().lower() for k in raw.split(",") if k.strip()]
    if not keywords:
        return True

    return any(keyword in subject_lower for keyword in keywords)


def _is_supported_file(filename: str, mime_type: str, strict_mode: bool) -> bool:
    lower_name = (filename or "").lower()

    if strict_mode:
        if mime_type in SUPPORTED_MIME_TYPES:
            return True
        return any(lower_name.endswith(ext) for ext in SUPPORTED_EXTENSIONS)

    if mime_type in SUPPORTED_MIME_TYPES:
        return True

    return any(lower_name.endswith(ext) for ext in SUPPORTED_EXTENSIONS)


def is_mail_ingestion_configured() -> Tuple[bool, str]:
    required = ["IMAP_HOST", "IMAP_USER", "IMAP_PASSWORD"]
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        return False, f"Missing env: {', '.join(missing)}"
    return True, "Configured"


def _extract_supported_attachments(msg, strict_mode: bool, max_attachment_size_bytes: int) -> Tuple[List[Dict], Dict]:
    attachments = []
    skipped = {
        "skipped_by_type": 0,
        "skipped_by_size": 0,
    }

    for part in msg.walk():
        content_disposition = str(part.get("Content-Disposition", "")).lower()
        filename = _decode_header_text(part.get_filename() or "")

        if strict_mode and "attachment" not in content_disposition and not filename:
            continue

        if not strict_mode and "attachment" not in content_disposition and not filename:
            continue

        mime_type = part.get_content_type()
        if not _is_supported_file(filename, mime_type, strict_mode):
            skipped["skipped_by_type"] += 1
            continue

        file_bytes = part.get_payload(decode=True)
        if not file_bytes:
            continue

        if max_attachment_size_bytes > 0 and len(file_bytes) > max_attachment_size_bytes:
            skipped["skipped_by_size"] += 1
            continue

        attachments.append(
            {
                "filename": _safe_filename(filename),
                "mime_type": mime_type,
                "file_bytes": file_bytes,
            }
        )

    return attachments, skipped


def ingest_invoices_from_email(max_messages: int = 20, ai_version: str = "gemini-flash-lite-latest") -> Dict:
    result = {
        "status": "SUCCESS",
        "messages_scanned": 0,
        "attachments_found": 0,
        "messages_with_attachments": 0,
        "ingested": 0,
        "duplicates": 0,
        "failed": 0,
        "skipped_sender": 0,
        "skipped_subject": 0,
        "skipped_by_type": 0,
        "skipped_by_size": 0,
        "errors": [],
    }

    configured, reason = is_mail_ingestion_configured()
    if not configured:
        result["status"] = "FAILED"
        result["errors"].append(reason)
        return result

    host = (os.getenv("IMAP_HOST") or "").strip()
    user = (os.getenv("IMAP_USER") or "").strip()
    password = (os.getenv("IMAP_PASSWORD") or "").strip().replace(" ", "")
    folder = (os.getenv("IMAP_FOLDER", "INBOX") or "INBOX").strip()
    unseen_only = _env_bool("MAIL_UNSEEN_ONLY", True)
    mark_as_seen = _env_bool("MAIL_MARK_AS_SEEN", True)
    strict_attachment_mode = _env_bool("MAIL_STRICT_ATTACHMENT_MODE", False)
    max_attachment_size_mb = int(os.getenv("MAIL_MAX_ATTACHMENT_SIZE_MB", "15"))
    max_attachment_size_bytes = max_attachment_size_mb * 1024 * 1024

    imap = None
    try:
        imap = imaplib.IMAP4_SSL(host, int((os.getenv("IMAP_PORT", "993") or "993").strip()))
        imap.login(user, password)
        select_status, _ = imap.select(folder)
        if select_status != "OK":
            result["status"] = "FAILED"
            result["errors"].append(f"Unable to select mailbox folder: {folder}")
            return result

        criteria = "UNSEEN" if unseen_only else "ALL"
        status, data = imap.search(None, criteria)
        if status != "OK":
            result["status"] = "FAILED"
            result["errors"].append("Unable to search mailbox")
            return result

        message_ids = data[0].split()
        if not message_ids:
            return result

        message_ids = message_ids[-max_messages:]

        for message_id in message_ids:
            result["messages_scanned"] += 1
            message_processing_attempted = False

            fetch_status, msg_data = imap.fetch(message_id, "(RFC822)")
            if fetch_status != "OK" or not msg_data or not msg_data[0]:
                result["failed"] += 1
                result["errors"].append(f"Failed to fetch message {message_id.decode(errors='ignore')}")
                continue

            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email)

            sender = parseaddr(msg.get("From", ""))[1]
            if not _allowed_sender(sender):
                result["skipped_sender"] += 1
                continue

            subject = _decode_header_text(msg.get("Subject", ""))
            if not _subject_matches_filters(subject):
                result["skipped_subject"] += 1
                continue

            attachments, skipped = _extract_supported_attachments(
                msg,
                strict_mode=strict_attachment_mode,
                max_attachment_size_bytes=max_attachment_size_bytes,
            )
            result["attachments_found"] += len(attachments)
            if attachments:
                result["messages_with_attachments"] += 1
            result["skipped_by_type"] += skipped.get("skipped_by_type", 0)
            result["skipped_by_size"] += skipped.get("skipped_by_size", 0)

            for idx, att in enumerate(attachments):
                message_processing_attempted = True
                try:
                    document_hash = compute_document_hash(att["file_bytes"])
                    if is_duplicate_hash(document_hash):
                        result["duplicates"] += 1
                        continue

                    extracted = processor.process_invoice(att["file_bytes"], att["mime_type"])
                    if not extracted:
                        result["failed"] += 1
                        result["errors"].append(processor.get_last_processing_error() or "Extraction failed")
                        continue

                    extracted["_ingest_source"] = "EMAIL"
                    extracted["_ingested_by"] = "MAIL_BOT"

                    vendor_name = extracted.get("vendor_name")
                    invoice_date = extracted.get("invoice_date")
                    total_amount = extracted.get("total_amount")
                    compliance_result = evaluate_invoice_compliance({
                        "vendor_name": vendor_name,
                        "invoice_date": invoice_date,
                        "total_amount": total_amount,
                        "currency": extracted.get("currency"),
                        "line_items": extracted.get("line_items", []),
                    })

                    if is_duplicate(vendor_name, invoice_date, total_amount):
                        result["duplicates"] += 1
                        continue

                    risk_score = 0
                    risk_level = "LOW"
                    validation_status = "Pending Review"
                    flag_reason = "Auto-ingested from email"

                    if not compliance_result.get("compliant", True):
                        risk_score += 30
                        risk_level = "MEDIUM"
                        validation_status = "Flagged"
                        flag_reason = "Compliance: " + "; ".join(compliance_result.get("issues", [])[:3])

                    storage_name = (
                        f"mail/{datetime.utcnow().strftime('%Y%m%d')}/"
                        f"msg_{message_id.decode(errors='ignore')}_{idx}_{att['filename']}"
                    )
                    public_url = upload_file(att["file_bytes"], storage_name, att["mime_type"])
                    if not public_url:
                        result["failed"] += 1
                        continue

                    payload = {
                        "vendor_name": vendor_name,
                        "invoice_date": invoice_date,
                        "total_amount": total_amount,
                        "currency": extracted.get("currency"),
                        "line_items": extracted.get("line_items", []),
                        "validation_status": validation_status,
                        "processing_status": "INGESTED_EMAIL",
                        "confidence_score": extracted.get("confidence_score", extracted.get("overall_confidence", 0.0)),
                        "flag_reason": flag_reason,
                        "document_hash": document_hash,
                        "ai_raw_data": extracted,
                        "ai_structured_output": extracted.get("ai_raw_structured"),
                        "ai_explanations": extracted.get("explanations", {}),
                        "risk_score": risk_score,
                        "risk_level": risk_level,
                        "approval_stage": "UPLOADED",
                        "reviewed_by": None,
                        "approved_by": None,
                        "approval_timestamp": None,
                        "ai_version": ai_version,
                        "created_by": "MAIL_BOT",
                    }

                    saved = save_invoice_record(payload, public_url, user_role="MAIL_BOT")
                    if saved:
                        result["ingested"] += 1
                    else:
                        result["failed"] += 1

                except Exception as ex:
                    result["failed"] += 1
                    result["errors"].append(str(ex))

            if mark_as_seen and message_processing_attempted:
                imap.store(message_id, "+FLAGS", "\\Seen")

    except Exception as ex:
        result["status"] = "FAILED"
        result["errors"].append(str(ex))
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

    if result.get("errors") and result.get("ingested", 0) == 0:
        result["status"] = "FAILED"
    elif result.get("errors") or result.get("failed", 0) > 0:
        result["status"] = "PARTIAL"
    else:
        result["status"] = "SUCCESS"

    return result
