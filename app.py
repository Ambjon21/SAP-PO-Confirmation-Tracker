import streamlit as st
import openai
import pandas as pd
import json
import pypdf

st.set_page_config(page_title="SAP PO Confirmation & ME2A Tracker", layout="wide")

st.title("📦 SAP Purchase Order Confirmation & Exception Tracker")
st.write("Extract supplier confirmations, process ME2A delinquent acknowledgment follow-ups, and flag SAP PO discrepancies automatically.")

# Sidebar Configuration
with st.sidebar:
    st.header("⚙️ Configuration")
    api_key = st.text_input("Enter OpenAI API Key:", type="password")
    st.markdown("---")
    st.subheader("SAP Processing Criteria")
    st.info("Tracks 'Ackn. Req.' (Acknowledgment Required) flags and identifies line-item delivery/price mismatches.")

# Extraction function
def process_confirmation(text, api_key):
    client = openai.OpenAI(api_key=api_key)
    
    prompt = f"""
    You are an automated SAP Procurement & Operations Assistant.
    Analyze the following vendor order acknowledgment or email and extract structured line-item status details.

    Extract into a valid JSON array of objects with these exact keys:
    - "po_number": Purchase Order number (string)
    - "line_item": SAP Line Item Number e.g. 10, 20, 30 (integer)
    - "material_id": Material / Part Number or description if unavailable (string)
    - "qty_ordered": Originally ordered quantity (integer or null if not stated)
    - "qty_confirmed": Confirmed quantity (integer)
    - "promised_delivery_date": Confirmed delivery date in YYYY-MM-DD format (string)
    - "confirmed_unit_price": Confirmed unit price (float or null if unchanged)
    - "status": Exact string, choose ONE from: ["CONFIRMED", "PARTIAL_SHIPMENT", "DELAYED", "PRICE_DISCREPANCY", "UNCONFIRMED_REJECTED"]
    - "exception_flag": True if status is NOT "CONFIRMED", otherwise False (boolean)
    - "notes": Brief explanation of any delay, price change, or backorder reason

    Document / Email Text:
    {text}

    Respond ONLY with a raw JSON array. Do not wrap in markdown code blocks.
    """

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": "You are a precise SAP data extraction engine that outputs raw JSON arrays."},
                  {"role": "user", "content": prompt}],
        temperature=0.0
    )
    
    return json.loads(response.choices[0].message.content.strip())

# Input Selection
input_type = st.radio("Select Input Source:", ["Paste Vendor Confirmation Email/Text", "Upload Confirmation PDF Document"])

raw_text = ""

if input_type == "Paste Vendor Confirmation Email/Text":
    raw_text = st.text_area("Paste Confirmation Message:", height=220, 
                            placeholder="Regarding PO #4500912300, Line 10 (Part #BR-8890) is confirmed for delivery on 2026-10-15...")
else:
    uploaded_file = st.file_uploader("Upload Confirmation PDF", type=["pdf"])
    if uploaded_file:
        pdf_reader = pypdf.PdfReader(uploaded_file)
        for page in pdf_reader.pages:
            raw_text += page.extract_text() or ""

if st.button("🚀 Process & Map to SAP ME2A Tracker"):
    if not api_key:
        st.error("Please enter your OpenAI API key in the sidebar.")
    elif not raw_text.strip():
        st.warning("Please provide input text or upload a PDF document.")
    else:
        with st.spinner("Analyzing confirmation against SAP PO requirements..."):
            try:
                extracted_data = process_confirmation(raw_text, api_key)
                df = pd.DataFrame(extracted_data)
                
                st.success("Successfully processed supplier confirmation!")
                
                # Summary Metrics
                total_items = len(df)
                exceptions = df[df["exception_flag"] == True]
                
                col1, col2, col3 = st.columns(3)
                col1.metric("Total Line Items Processed", total_items)
                col2.metric("Fully Confirmed Items", total_items - len(exceptions))
                col3.metric("Flagged Exceptions (ME2A Action)", len(exceptions), delta_color="inverse")
                
                # Full Extracted Table
                st.subheader("📋 Extracted SAP Line-Item Status Table")
                st.dataframe(df, use_container_width=True)
                
                # Exception Callout Box
                if not exceptions.empty:
                    st.error(f"⚠️ Action Required: {len(exceptions)} Line Item(s) have discrepancies/delays:")
                    st.table(exceptions[["po_number", "line_item", "material_id", "status", "promised_delivery_date", "notes"]])
                else:
                    st.balloons()
                    st.info("✅ All line items match PO expectations with zero discrepancies.")
                
                # Export Button
                csv_data = df.to_csv(index=False).encode("utf-8")
                st.download_button(
                    label="📥 Download SAP Status File (CSV)",
                    data=csv_data,
                    file_name="sap_po_me2a_status_update.csv",
                    mime="text/csv"
                )

            except Exception as e:
                st.error(f"Error processing confirmation document: {e}")
