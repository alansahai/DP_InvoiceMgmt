import streamlit as st
import pandas as pd
from processor import process_invoice
from database import upload_file, save_invoice_record, fetch_all_invoices

st.set_page_config(page_title="AI Invoice Auditor", layout="wide")

st.title("🛡️ AI-Powered Invoice Auditor")
st.markdown("---")

# --- 🧠 Logic Engine: The Math Auditor ---
def validate_math(invoice_total, line_items_df):
    """
     audits the invoice by checking if the sum of line items matches the total.
     Returns: (is_valid, calculated_sum, difference)
    """
    if line_items_df.empty:
        return False, 0.0, invoice_total
    
    # 1. Calculate the expected total from the table
    # We use 'total_price' column extracted by AI
    calculated_sum = line_items_df['total_price'].sum()
    
    # 2. Compare with the Invoice Total (allowing small rounding differences)
    diff = round(abs(invoice_total - calculated_sum), 2)
    is_valid = diff == 0
    
    return is_valid, calculated_sum, diff

# --- Sidebar: Ingestion Layer ---
with st.sidebar:
    st.header("1. Upload Invoice")
    st.info("Supported: PDF, PNG, JPG")
    uploaded_file = st.file_uploader("Upload File", type=["pdf", "png", "jpg", "jpeg"])
    
    if uploaded_file and st.button("Analyze Invoice"):
        with st.spinner("🔍 AI is reading line items & checking math..."):
            file_bytes = uploaded_file.getvalue()
            
            # 1. Upload to Supabase Storage
            public_url = upload_file(file_bytes, uploaded_file.name, uploaded_file.type)
            
            if public_url:
                # 2. Run AI Extraction
                data = process_invoice(file_bytes, uploaded_file.type)
                if data:
                    st.session_state['data'] = data
                    st.session_state['url'] = public_url
                    st.rerun() # Refresh screen to show results

# --- Main Dashboard: Verification Layer ---
if 'data' in st.session_state:
    data = st.session_state['data']
    
    # Split Screen: Document (Left) vs. Data (Right) [cite: 142]
    col1, col2 = st.columns([1, 1.5])
    
    with col1:
        st.subheader("Original Document")
        if "pdf" in st.session_state['url']:
             st.markdown(f"[View PDF]({st.session_state['url']})")
        else:
            st.image(st.session_state['url'], use_container_width=True)
    
    with col2:
        st.subheader("📝 Audit Results")
        
        # 1. Header Information (Editable)
        with st.container(border=True):
            st.caption("Invoice Metadata")
            c1, c2 = st.columns(2)
            vendor = c1.text_input("Vendor", data.get("vendor_name"))
            date = c2.text_input("Date", data.get("invoice_date"))
            
            c3, c4 = st.columns(2)
            extracted_total = c3.number_input("Invoice Total ($)", value=float(data.get("total_amount", 0.0)))
            currency = c4.text_input("Currency", data.get("currency"))

        # 2. Line Items Table (The "Smart" Part)
        st.write("📦 **Line Items Extraction**")
        st.caption("Check the table below. You can edit values if the AI misread them.")
        
        # Convert JSON list to Pandas DataFrame
        items_df = pd.DataFrame(data.get("line_items", []))
        
        # Show an editable table [cite: 146]
        edited_df = st.data_editor(
            items_df, 
            num_rows="dynamic", 
            use_container_width=True,
            key="editor"
        )
        
        # 3. REAL-TIME VALIDATION ENGINE
        st.markdown("### 🧮 Auto-Validation")
        
        is_valid, calc_sum, diff = validate_math(extracted_total, edited_df)
        
        if is_valid:
            st.success(f"✅ **PASSED:** Line items sum ({calc_sum}) matches Invoice Total.")
            status = "Verified"
        else:
            st.error(f"❌ **MISMATCH:** Line items sum to **{calc_sum}**, but Invoice Total is **{extracted_total}**.")
            st.warning(f"⚠️ Discrepancy of **{diff}**. Please fix the table or the total.")
            status = "Flagged"

        # 4. Final Action
        st.divider()
        if st.button("💾 Save Record"):
            final_data = {
                "vendor_name": vendor,
                "invoice_date": date,
                "total_amount": extracted_total,
                "currency": currency,
                "line_items": edited_df.to_dict("records"), # Saves the *corrected* table
                "validation_status": status,
                "math_discrepancy": diff
            }
            save_invoice_record(final_data, st.session_state['url'])
            st.toast("Invoice saved to database!", icon="✅")

# --- Historical Database View ---
st.divider()
st.subheader("📂 Processed Invoices (Database)")
invoices = fetch_all_invoices()
if invoices:
    st.dataframe(invoices)