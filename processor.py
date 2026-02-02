import os
import google.generativeai as genai
import json
import copy
import hashlib
import time
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Use the model alias that works for your account
model_name = "gemini-flash-latest"

# Round-robin API key management
API_KEYS = []
for i in range(1, 10):  # Support up to 9 API keys
    key = os.environ.get(f"GOOGLE_API_KEY_{i}" if i > 1 else "GOOGLE_API_KEY")
    if key:
        API_KEYS.append(key)

if not API_KEYS:
    raise ValueError("❌ No GOOGLE_API_KEY found in .env file. Add GOOGLE_API_KEY, GOOGLE_API_KEY_2, etc.")

print(f"🔑 Loaded {len(API_KEYS)} API key(s) for round-robin scheduling")

# Track current API key index and failed keys
current_key_index = 0
failed_keys = set()  # Track keys that hit quota
last_reset_date = datetime.utcnow().date()  # Track when keys were last reset

# In-memory cache for processed invoices
CACHE = {}

def process_invoice(file_bytes, mime_type):
    # Generate hash for caching
    file_hash = hashlib.md5(file_bytes).hexdigest()
    
    # Check cache first
    if file_hash in CACHE:
        print(f"⚡ Using cached AI result (hash: {file_hash[:8]}...)")
        return CACHE[file_hash]
    
    # --- STEP C: EXPLAINABILITY PROMPT ---
    prompt = """
    You are an expert invoice auditor. Extract data into this exact JSON structure.
    
    1. For every field, return an object with "value" and "confidence" (0.0-1.0).
    2. Provide a detailed "explanations" object describing WHERE you found each key field (e.g., "Top right corner", "Next to label 'Total'").

    {
      "vendor_name": {"value": "string", "confidence": 0.0},
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
        "vendor_name": "e.g. Found at top left logo",
        "invoice_date": "e.g. Labelled 'Date' in top right",
        "total_amount": "e.g. Bold text at bottom right"
      }
    }
    
    IMPORTANT GUIDELINES:
    1. 'total_amount' is the final invoice total (including tax).
    2. Extract every single line item visible.
    3. "confidence" reflects text clarity (1.0 = perfect).
    4. "explanations" must be specific to the document layout.
    5. Return ONLY valid raw JSON. No markdown.
    """
    
    content = [prompt, {"mime_type": mime_type, "data": file_bytes}]
    
    # ✅ DAILY RESET: Check if day changed and reset quota
    global current_key_index, failed_keys, last_reset_date
    today = datetime.utcnow().date()
    if today != last_reset_date:
        print(f"🌅 New day detected (was {last_reset_date}, now {today}) — resetting API key usage")
        failed_keys.clear()
        current_key_index = 0
        last_reset_date = today
        print(f"✅ API key quota reset. Starting fresh from Key #1")
    
    # Round-robin retry logic across multiple API keys
    response = None
    attempts_per_key = 2  # Try each key twice before moving to next
    
    # Try all available API keys
    for key_attempt in range(len(API_KEYS)):
        # Skip keys that already failed
        if current_key_index in failed_keys:
            current_key_index = (current_key_index + 1) % len(API_KEYS)
            continue
        
        current_api_key = API_KEYS[current_key_index]
        print(f"🔑 Using API key #{current_key_index + 1}/{len(API_KEYS)}")
        
        # Configure with current API key
        genai.configure(api_key=current_api_key)
        model = genai.GenerativeModel(model_name)
        
        # Try current key with retries
        for attempt in range(attempts_per_key):
            try:
                response = model.generate_content(content)
                print(f"✅ Success with API key #{current_key_index + 1}")
                # Successful, move to next key for next request (round-robin)
                current_key_index = (current_key_index + 1) % len(API_KEYS)
                break  # Success, exit retry loop
            except Exception as e:
                error_str = str(e)
                print(f"⚠️ API key #{current_key_index + 1}, attempt {attempt + 1}/{attempts_per_key}: {error_str[:100]}")
                
                if "429" in error_str:
                    # Quota exceeded for this key
                    print(f"❌ API key #{current_key_index + 1} quota exceeded. Trying next key...")
                    failed_keys.add(current_key_index)
                    break  # Move to next key
                elif attempt < attempts_per_key - 1:
                    # Transient error, retry same key
                    time.sleep(2)
                else:
                    # Non-quota error on last attempt
                    print(f"❌ Non-retryable error with API key #{current_key_index + 1}: {e}")
                    break
        
        if response:
            break  # Got successful response
        
        # Move to next API key
        current_key_index = (current_key_index + 1) % len(API_KEYS)
    
    # If all keys failed, return demo data
    if not response:
        if len(failed_keys) >= len(API_KEYS):
            print("❌ All API keys exhausted. Switching to demo fallback.")
        else:
            print("❌ All retry attempts failed. Switching to demo fallback.")
        
        demo_data = {
            "vendor_name": "Demo Vendor (All API Keys Exhausted)",
            "invoice_date": "2025-01-01",
            "total_amount": 1000.0,
            "currency": "USD",
            "line_items": [
                {
                    "description": "Demo Item",
                    "quantity": 1,
                    "unit_price": 1000.0,
                    "total_price": 1000.0
                }
            ],
            "confidence_score": 0.5,
            "explanations": {
                "note": f"⚠️ Fallback demo data. {len(failed_keys)}/{len(API_KEYS)} API keys hit quota limit."
            },
            "ai_raw_structured": {},
            "overall_confidence": 0.5
        }
        CACHE[file_hash] = demo_data
        return demo_data
    
    try:
        # Clean response
        cleaned_text = response.text.strip().replace("```json", "").replace("```", "")
        parsed = json.loads(cleaned_text)

        # --- FIX 3: PRESERVE STRUCTURED OUTPUT ---
        # Make a deep copy of the raw nested structure (with confidence scores)
        # BEFORE we flatten it for the UI.
        parsed["ai_raw_structured"] = copy.deepcopy(parsed)
        # -----------------------------------------

        # --- FLATTENING LOGIC (Keep values simple for UI) ---
        
        # 1. Capture metadata for DB
        parsed["confidence_score"] = parsed.get("overall_confidence", 0.0)
        # "explanations" is already in the root, so we don't need to move it.

        # 2. Flatten Header Fields
        for field in ["vendor_name", "invoice_date", "currency", "total_amount"]:
            if field in parsed and isinstance(parsed[field], dict):
                parsed[field] = parsed[field].get("value")

        # 3. Flatten Line Items
        if "line_items" in parsed:
            for item in parsed["line_items"]:
                for key in item:
                    if isinstance(item[key], dict):
                        item[key] = item[key].get("value")
        
        # Cache the successful result
        CACHE[file_hash] = parsed
        print(f"✅ Cached result for file hash: {file_hash[:8]}...")
        
        return parsed

    except Exception as e:
        print(f"❌ AI Error during parsing: {e}")
        return None