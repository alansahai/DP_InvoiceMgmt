import streamlit as st
from supabase import create_client, Client

# ---------------------------------------------------
# SECURE SUPABASE CONNECTION (Works on Streamlit Cloud)
# ---------------------------------------------------

try:
    # First try Streamlit Secrets (for deployed app)
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
except Exception:
    # Optional: fallback for local development (if needed)
    import os
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")

if not url or not key:
    raise ValueError("❌ Supabase credentials not found. Add them in Streamlit Secrets.")

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

# --- VENDOR MEMORY LOGIC ---
def update_vendor_profile(vendor_name, total_amount, invoice_date):
    """Updates the historical profile for a specific vendor"""
    try:
        # 1. Check if vendor exists
        existing = supabase.table("vendors").select("*").eq("vendor_name", vendor_name).execute().data
        
        if existing:
            record = existing[0]
            old_count = record["invoice_count"]
            old_avg = float(record["avg_invoice_value"])
            
            # Calculate new running average
            new_count = old_count + 1
            new_avg = ((old_avg * old_count) + float(total_amount)) / new_count
            
            # Update existing record
            supabase.table("vendors").update({
                "avg_invoice_value": new_avg,
                "invoice_count": new_count,
                "last_invoice_date": invoice_date
            }).eq("vendor_name", vendor_name).execute()
        else:
            # Create new record
            supabase.table("vendors").insert({
                "vendor_name": vendor_name,
                "avg_invoice_value": total_amount,
                "invoice_count": 1,
                "last_invoice_date": invoice_date
            }).execute()
            
    except Exception as e:
        print(f"Vendor Update Error: {e}")

# --- HELPER: GET VENDOR AVERAGE ---
def get_vendor_average(vendor_name):
    """Fetches the historical average invoice value for anomaly detection"""
    try:
        response = supabase.table("vendors").select("avg_invoice_value").eq("vendor_name", vendor_name).execute()
        if response.data and len(response.data) > 0:
            return float(response.data[0]['avg_invoice_value'])
        return None
    except Exception as e:
        return None

# --- DUPLICATE DETECTION ---
def is_duplicate(vendor_name, invoice_date, total_amount, exclude_id=None):
    """
    Checks if an invoice with the same Vendor, Date, and Amount already exists.
    exclude_id: Optional ID to ignore (useful when editing an existing invoice).
    """
    try:
        query = supabase.table("invoices")\
            .select("id")\
            .eq("vendor_name", vendor_name)\
            .eq("invoice_date", invoice_date)\
            .eq("total_amount", total_amount)
            
        # If we are editing a record, don't count itself as a duplicate
        if exclude_id:
            query = query.neq("id", exclude_id)
            
        response = query.execute()
        return len(response.data) > 0
    except Exception as e:
        print(f"Duplicate Check Error: {e}")
        return False

# --- AUDIT LOGGING ---
def log_edit(invoice_id, field_name, old_val, new_val):
    """Records a specific change made by the human reviewer"""
    try:
        supabase.table("invoice_edits").insert({
            "invoice_id": invoice_id,
            "field_name": field_name,
            "old_value": str(old_val),
            "new_value": str(new_val)
        }).execute()
    except Exception as e:
        print(f"Audit Log Error: {e}")

# --- UPDATED SAVE FUNCTION ---
def save_invoice_record(data, file_url, user_role="Unknown", invoice_id=None):
    """Saves invoice and returns the entire record (including ID)
    If invoice_id is provided, UPDATE the existing record instead of INSERT.
    """
    try:
        payload = {
            "vendor_name": data.get("vendor_name"),
            "invoice_date": data.get("invoice_date"),
            "total_amount": data.get("total_amount"),
            "currency": data.get("currency"),
            "status": data.get("validation_status"),
            "processing_status": "COMPLETED",
            "confidence_score": data.get("confidence_score", 0.0),
            "flag_reason": data.get("flag_reason"),
            "file_url": file_url,
            "ai_raw_data": data.get("ai_raw_data"),
            "ai_structured_output": data.get("ai_structured_output"),
            
            # --- FIX: Preserve Creator & Track Reviewer Correctly ---
            "created_by": data.get("created_by", user_role),
            "last_reviewed_by": data.get("reviewed_by", user_role),
            # ------------------------------------------------------
            
            "ai_explanations": data.get("ai_explanations"),
            
            # Risk
            "risk_score": data.get("risk_score", 0),
            "risk_level": data.get("risk_level", "LOW"),
            
            # Workflow
            "approval_stage": data.get("approval_stage", "UPLOADED"),
            "reviewed_by": data.get("reviewed_by"),
            "approved_by": data.get("approved_by"),
            "approval_timestamp": data.get("approval_timestamp"),
            "audited": data.get("approval_stage") == "AUDITED",  # ✅ FIX: Track audit status
            
            # Versioning
            "ai_version": data.get("ai_version"),
            "reprocessed_at": data.get("reprocessed_at")
        }
        
        # ✅ FIX: UPDATE if invoice_id exists, otherwise INSERT
        if invoice_id:
            response = supabase.table("invoices").update(payload).eq("id", invoice_id).execute()
        else:
            response = supabase.table("invoices").insert(payload).execute()
        
        # Update Vendor Memory only if fully Approved
        if data.get("approval_stage") == "APPROVED":
             update_vendor_profile(
                data.get("vendor_name"), 
                data.get("total_amount"), 
                data.get("invoice_date")
            )
        
        # ✅ FIX: Log audit if marked as AUDITED
        if data.get("approval_stage") == "AUDITED" and response.data:
            try:
                saved_id = response.data[0].get("id")
                supabase.table("invoice_audits").insert({
                    "invoice_id": saved_id,
                    "audited_by": data.get("reviewed_by", "AUDITOR"),
                    "audit_note": data.get("flag_reason", "Audited and Verified")
                }).execute()
                print(f"✅ Audit logged for invoice {saved_id}")
            except Exception as e:
                print(f"Audit Log Error: {e}")
            
        return response.data[0] if response.data else None
    except Exception as e:
        print(f"DB Error: {e}")
        return None

# --- FETCH INVOICE EDITS ---
def fetch_invoice_edits(invoice_id):
    """Fetches all edit records for a specific invoice"""
    try:
        response = supabase.table("invoice_edits").select("*").eq("invoice_id", invoice_id).execute()
        return response.data if response.data else []
    except Exception as e:
        print(f"Fetch Invoice Edits Error: {e}")
        return []

def fetch_all_invoices():
    """Fetches all invoices for the dashboard"""
    try:
        response = supabase.table("invoices").select("*").order("created_at", desc=True).execute()
        return response.data
    except Exception as e:
        print(f"Fetch Error: {e}")
        return []
