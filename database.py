import os
from supabase import create_client, Client
from dotenv import load_dotenv

# Load keys from .env file
load_dotenv()

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")

if not url or not key:
    raise ValueError("Missing Supabase keys in .env file")

supabase: Client = create_client(url, key)

def upload_file(file_bytes, file_name, content_type):
    """Uploads file to Supabase Storage and returns the Public URL"""
    bucket_name = "invoices"
    try:
        # Upload file (overwrite if exists)
        response = supabase.storage.from_(bucket_name).upload(
            path=file_name,
            file=file_bytes,
            file_options={"content-type": content_type, "upsert": "true"}
        )
        # Get Public URL
        public_url = supabase.storage.from_(bucket_name).get_public_url(file_name)
        return public_url
    except Exception as e:
        print(f"Upload Error: {e}")
        return None

def save_invoice_record(data, file_url):
    """Saves the extracted data to the Supabase Database"""
    try:
        payload = {
            "vendor_name": data.get("vendor_name"),
            "invoice_date": data.get("invoice_date"),
            "total_amount": data.get("total_amount"),
            "currency": data.get("currency"),
            "status": "Verified", 
            "file_url": file_url,
            "ai_raw_data": data # Store full JSON for audit
        }
        # Insert into table
        data, count = supabase.table("invoices").insert(payload).execute()
        return data
    except Exception as e:
        print(f"DB Error: {e}")
        return None

def fetch_all_invoices():
    """Fetches all invoices for the dashboard"""
    try:
        response = supabase.table("invoices").select("*").order("created_at", desc=True).execute()
        return response.data
    except Exception as e:
        print(f"Fetch Error: {e}")
        return []