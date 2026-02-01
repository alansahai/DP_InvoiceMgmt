import os
import google.generativeai as genai
import json
from dotenv import load_dotenv

load_dotenv()

# Use the model alias that we confirmed works for your account
model_name = "gemini-flash-latest" 
api_key = os.environ.get("GOOGLE_API_KEY")

if not api_key:
    raise ValueError("❌ GOOGLE_API_KEY not found in .env file")

genai.configure(api_key=api_key)

def process_invoice(file_bytes, mime_type):
    model = genai.GenerativeModel(model_name)
    
    # New Prompt: Explicitly requesting a list of objects for math validation
    prompt = """
    You are an expert invoice auditor. Extract data into this exact JSON structure:
    {
        "vendor_name": "string",
        "invoice_date": "YYYY-MM-DD",
        "currency": "string",
        "total_amount": 0.00,
        "line_items": [
            {
                "description": "string",
                "quantity": 0,
                "unit_price": 0.00,
                "total_price": 0.00
            }
        ]
    }
    
    IMPORTANT GUIDELINES:
    1. 'total_amount' is the final invoice total (including tax).
    2. Extract every single line item visible in the table.
    3. Ensure all numbers are floats/integers, NOT strings.
    4. If a unit price is missing, try to calculate it from Total / Quantity.
    5. Return ONLY valid raw JSON. No markdown formatting.
    """
    
    content = [prompt, {"mime_type": mime_type, "data": file_bytes}]
    
    try:
        response = model.generate_content(content)
        # Clean response to ensure it parses correctly
        cleaned_text = response.text.strip().replace("```json", "").replace("```", "")
        return json.loads(cleaned_text)
    except Exception as e:
        print(f"AI Error: {e}")
        return None