import os
import json
import copy
import hashlib
import time
from datetime import datetime
from typing import Any, Dict, Optional

import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-flash-latest")
API_KEYS = []
for i in range(1, 10):
    key = os.getenv(f"GOOGLE_API_KEY_{i}" if i > 1 else "GOOGLE_API_KEY")
    if key:
        API_KEYS.append(key)

if not API_KEYS:
    raise ValueError("No GOOGLE_API_KEY found in environment")

current_key_index = 0
failed_keys = set()
last_reset_date = datetime.utcnow().date()

CACHE: Dict[str, Dict[str, Any]] = {}


class ExtractionError(Exception):
    pass


def _daily_reset():
    global current_key_index, failed_keys, last_reset_date
    today = datetime.utcnow().date()
    if today != last_reset_date:
        failed_keys.clear()
        current_key_index = 0
        last_reset_date = today


def _prompt() -> str:
    return """
You are an invoice extraction engine. Return ONLY valid JSON with this structure:
{
  "vendor_name": {"value": "string", "confidence": 0.0},
  "invoice_number": {"value": "string", "confidence": 0.0},
  "invoice_date": {"value": "YYYY-MM-DD", "confidence": 0.0},
  "currency": {"value": "string", "confidence": 0.0},
  "total_amount": {"value": 0.0, "confidence": 0.0},
  "line_items": [
    {
      "description": {"value": "string", "confidence": 0.0},
      "quantity": {"value": 0, "confidence": 0.0},
      "unit_price": {"value": 0.0, "confidence": 0.0},
      "total_price": {"value": 0.0, "confidence": 0.0}
    }
  ],
  "overall_confidence": 0.0,
  "explanations": {
    "vendor_name": "where found",
    "invoice_number": "where found",
    "invoice_date": "where found",
    "total_amount": "where found"
  }
}
"""


def extract_structured_data(file_bytes: bytes, mime_type: str) -> Dict[str, Any]:
    file_hash = hashlib.md5(file_bytes).hexdigest()
    if file_hash in CACHE:
        return CACHE[file_hash]

    _daily_reset()
    response = None
    attempts_per_key = 2

    global current_key_index

    content = [_prompt(), {"mime_type": mime_type, "data": file_bytes}]

    for _ in range(len(API_KEYS)):
        if current_key_index in failed_keys:
            current_key_index = (current_key_index + 1) % len(API_KEYS)
            continue

        genai.configure(api_key=API_KEYS[current_key_index])
        model = genai.GenerativeModel(MODEL_NAME)

        for attempt in range(attempts_per_key):
            try:
                response = model.generate_content(content)
                current_key_index = (current_key_index + 1) % len(API_KEYS)
                break
            except Exception as ex:
                message = str(ex)
                if "429" in message:
                    failed_keys.add(current_key_index)
                    break
                if attempt < attempts_per_key - 1:
                    time.sleep(2)

        if response:
            break
        current_key_index = (current_key_index + 1) % len(API_KEYS)

    if not response:
        raise ExtractionError("Extraction failed: all AI retries exhausted")

    try:
        cleaned = response.text.strip().replace("```json", "").replace("```", "")
        parsed = json.loads(cleaned)

        parsed["ai_raw_structured"] = copy.deepcopy(parsed)
        parsed["confidence_score"] = parsed.get("overall_confidence", 0.0)

        for field in ["vendor_name", "invoice_number", "invoice_date", "currency", "total_amount"]:
            if isinstance(parsed.get(field), dict):
                parsed[field] = parsed[field].get("value")

        for item in parsed.get("line_items", []):
            for key in list(item.keys()):
                if isinstance(item[key], dict):
                    item[key] = item[key].get("value")

        CACHE[file_hash] = parsed
        return parsed
    except Exception as ex:
        raise ExtractionError(f"Extraction failed: AI parsing error: {ex}")
