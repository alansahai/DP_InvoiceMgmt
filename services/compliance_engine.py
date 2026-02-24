from datetime import datetime
from typing import Any, Dict, List

ALLOWED_CURRENCIES = {
    "USD", "EUR", "GBP", "INR", "AED", "SGD", "AUD", "CAD", "JPY", "CNY"
}


def _is_valid_date(date_text: Any) -> bool:
    if not date_text:
        return False
    try:
        datetime.strptime(str(date_text), "%Y-%m-%d")
        return True
    except Exception:
        return False


def calculate_compliance_score(invoice: Dict[str, Any], duplicate_vendor_invoice_number: bool) -> Dict[str, Any]:
    score = 100
    reasons: List[str] = []

    required_fields = [
        invoice.get("vendor_name"),
        invoice.get("invoice_date"),
        invoice.get("total_amount"),
        invoice.get("currency"),
    ]
    if any(field in [None, ""] for field in required_fields):
        score -= 25
        reasons.append("REQ_FIELDS_MISSING")

    if not _is_valid_date(invoice.get("invoice_date")):
        score -= 15
        reasons.append("INVALID_DATE")

    currency = str(invoice.get("currency") or "").upper().strip()
    if currency and currency not in ALLOWED_CURRENCIES:
        score -= 10
        reasons.append("UNSUPPORTED_CURRENCY")

    total_amount = invoice.get("total_amount")
    line_items = invoice.get("line_items") or []

    try:
        total_value = float(total_amount)
    except Exception:
        total_value = None

    if not line_items:
        score -= 20
        reasons.append("MISSING_LINE_ITEMS")
    elif total_value is not None:
        computed = 0.0
        for item in line_items:
            try:
                computed += float(item.get("total_price") or 0)
            except Exception:
                pass
        if abs(computed - total_value) > 1.0:
            score -= 20
            reasons.append("LINE_TOTAL_MISMATCH")

    if duplicate_vendor_invoice_number:
        score -= 35
        reasons.append("DUP_VENDOR_INV_NO")

    score = max(0, min(100, score))
    return {
        "compliance_score": score,
        "reason_codes": reasons,
    }
