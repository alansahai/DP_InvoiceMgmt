import json
import os
import urllib.request


def _env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def sync_invoice_to_crm(invoice_record, event="UPSERT"):
    enabled = _env_bool("CRM_SYNC_ENABLED", False)
    webhook_url = (os.getenv("CRM_WEBHOOK_URL") or "").strip()

    if not enabled or not webhook_url:
        return {"sent": False, "reason": "disabled_or_missing_webhook"}

    payload = {
        "event": event,
        "source": "AI_INVOICE_AUDITOR",
        "invoice": invoice_record,
    }

    try:
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            webhook_url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            status = getattr(response, "status", 200)

        return {"sent": 200 <= status < 300, "status": status}
    except Exception as ex:
        return {"sent": False, "reason": str(ex)}
