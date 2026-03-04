from datetime import datetime


ALLOWED_CURRENCIES = {
    "USD", "EUR", "GBP", "INR", "AED", "SGD", "AUD", "CAD", "JPY", "CNY"
}


def _is_valid_date(date_text):
    if not date_text:
        return False
    try:
        datetime.strptime(str(date_text), "%Y-%m-%d")
        return True
    except Exception:
        return False


def evaluate_invoice_compliance(invoice):
    issues = []

    vendor_name = invoice.get("vendor_name")
    invoice_date = invoice.get("invoice_date")
    total_amount = invoice.get("total_amount")
    currency = str(invoice.get("currency") or "").upper().strip()
    line_items = invoice.get("line_items") or []

    if not vendor_name:
        issues.append("Missing vendor name")

    if not _is_valid_date(invoice_date):
        issues.append("Invalid invoice date format (expected YYYY-MM-DD)")

    try:
        total_value = float(total_amount)
        if total_value <= 0:
            issues.append("Invoice total must be greater than zero")
    except Exception:
        total_value = 0.0
        issues.append("Invalid invoice total amount")

    if currency and currency not in ALLOWED_CURRENCIES:
        issues.append(f"Unsupported currency: {currency}")

    if not line_items:
        issues.append("No line items extracted")
    else:
        computed_total = 0.0
        for index, item in enumerate(line_items, start=1):
            desc = str(item.get("description") or "").strip()
            quantity = item.get("quantity")
            unit_price = item.get("unit_price")
            total_price = item.get("total_price")

            if not desc:
                issues.append(f"Line {index}: Missing description")

            try:
                quantity_value = float(quantity)
                if quantity_value <= 0:
                    issues.append(f"Line {index}: Quantity must be greater than zero")
            except Exception:
                issues.append(f"Line {index}: Invalid quantity")

            try:
                unit_price_value = float(unit_price)
                if unit_price_value < 0:
                    issues.append(f"Line {index}: Unit price cannot be negative")
            except Exception:
                issues.append(f"Line {index}: Invalid unit price")

            try:
                total_price_value = float(total_price)
                if total_price_value < 0:
                    issues.append(f"Line {index}: Total price cannot be negative")
                computed_total += total_price_value
            except Exception:
                issues.append(f"Line {index}: Invalid total price")

        if total_value > 0 and abs(total_value - computed_total) > 1.0:
            issues.append("Line-item total mismatch against invoice total")

    return {
        "compliant": len(issues) == 0,
        "issues": issues,
        "issue_count": len(issues),
    }
