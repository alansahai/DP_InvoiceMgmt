from typing import Any, Dict, List


def classify_risk(risk_score: int) -> str:
    if risk_score >= 60:
        return "HIGH"
    if risk_score >= 30:
        return "MEDIUM"
    return "LOW"


def calculate_risk(compliance_score: int, confidence_score: float, reason_codes: List[str]) -> Dict[str, Any]:
    risk_score = 100 - int(compliance_score)
    if confidence_score < 0.70:
        risk_score = min(100, risk_score + 10)
        if "LOW_CONFIDENCE" not in reason_codes:
            reason_codes.append("LOW_CONFIDENCE")

    risk_level = classify_risk(risk_score)
    return {
        "risk_score": risk_score,
        "risk_level": risk_level,
        "reason_codes": reason_codes,
    }


def route_invoice(confidence_score: float, risk_score: int, duplicate_found: bool, confidence_threshold: float = 0.70, risk_threshold: int = 60) -> str:
    if duplicate_found or confidence_score < confidence_threshold or risk_score >= risk_threshold:
        return "REVIEW_QUEUE"
    return "READY_FOR_FINANCE_MANAGER"
