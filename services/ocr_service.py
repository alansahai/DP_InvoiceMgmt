from typing import Tuple

SUPPORTED_TYPES = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/jpg",
}


def validate_invoice_file(file_bytes: bytes, mime_type: str) -> Tuple[bool, str]:
    if not file_bytes:
        return False, "Empty file content"
    if mime_type not in SUPPORTED_TYPES:
        return False, f"Unsupported mime type: {mime_type}"
    return True, "OK"
