from datetime import datetime
import json
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="PO Confirmation & SLA Tracker",
    layout="wide",
)

st.title("PO Confirmation & SLA Tracker")
st.caption("Enforcing 48-Hour Vendor Order Acknowledgments & Exception Management")

# Initialize Session State Data
if "po_records" not in st.session_state:
  st.session_state.po_records = pd.DataFrame(
      columns=[
          "PO Number",
          "Vendor",
          "Issue Date",
          "Item Description",
          "Confirmed",
      ]
  )

# --- SIDEBAR: SAP / CSV FILE UPLOADER ---
with st.sidebar:
  st.header("Data Import")
  st.write("Upload your SAP (ME2M/ME2L) or CSV export:")
  uploaded_file = st.file_uploader(
      "Choose a CSV or Excel file", type=["csv", "xlsx"]
  )

  if uploaded_file is not None:
    try:
      if uploaded_file.name.endswith(".csv"):
        imported_df = pd.read_csv(uploaded_file)
      else:
        imported_df = pd.read_excel(uploaded_file)

      # Display Column Mapping Helper if needed
      st.success(f"Loaded {len(imported_df)} rows from file.")

      # Standardize Column Names (Maps common SAP export headers)
      col_map = {
          "Purchasing Document": "PO Number",
          "PO": "PO Number",
          "Vendor Name": "Vendor",
          "Name of Vendor": "Vendor",
          "Document Date": "Issue Date",
          "Created On": "Issue Date",
          "Short Text": "Item Description",
          "Material Description": "Item Description",
      }
      imported_df = imported_df.rename(columns=col_map)

      # Ensure required columns exist
      required_cols = ["PO Number", "Vendor", "Issue Date", "Item Description"]
      missing_cols = [c for c in required_cols if c not in imported_df.columns]

      if missing_cols:
        st.error(f"Missing columns in file: {', '.join(missing_cols)}")
      else:
        if "Confirmed" not in imported_df.columns:
          # If SAP Acknowledgment column is present, auto-set status
          if "Acknowledgment" in imported_df.columns:
            imported_df["Confirmed"] = imported_df["Acknowledgment"].notna()
          else:
            imported_df["Confirmed"] = False

        if st.button("Merge into Tracker"):
          # Clean PO Numbers & Strings
          imported_df["PO Number"] = imported_df["PO Number"].astype(str)
          imported_df["Vendor"] = imported_df["Vendor"].astype(str)
          imported_df["Item Description"] = imported_df[
              "Item Description"
          ].astype(str)

          # Combine with existing session state without duplicates
          combined = pd.concat(
              [st.session_state.po_records, imported_df[required_cols + ["Confirmed"]]]
          )
          combined = combined.drop_duplicates(
              subset=["PO Number"], keep="first"
          )
          st.session_state.po_records = combined.reset_index(drop=True)
          st.success("Successfully updated tracker records!")
          st.rerun()

    except Exception as e:
      st.error(f"Error parsing file: {e}")

  st.divider()
  if st.button("Load Sample Demo Data"):
    st.session_state.po_records = pd.DataFrame([
        {
            "PO Number": "450010480",
            "Vendor": "ABC Supply Co",
            "Issue Date": "2026-09-21",
            "Item Description": "Motor Assemblies & Bearings",
            "Confirmed": False,
        },
        {
            "PO Number": "450010485",
            "Vendor": "McMaster-Carr",
            "Issue Date": "2026-09-23",
            "Item Description": "Pipe Fittings & Valves",
            "Confirmed": True,
        },
        {
            "PO Number": "450010490",
            "Vendor": "ABC Supply Co",
            "Issue Date": "2026-09-22",
            "Item Description": "Hydraulic Valves",
            "Confirmed": False,
        },
        {
            "PO Number": "450010501",
            "Vendor": "Global Industrial",
            "Issue Date": "2026-09-25",
            "Item Description": "Plant Supplies - Gloves & Paper Towels",
            "Confirmed": False,
        },
    ])
    st.rerun()

# --- MAIN ENGINE: CALCULATE AGING & SLA ---
df = st.session_state.po_records.copy()

if not df.empty:
  df["Issue Date"] = pd.to_datetime(df["Issue Date"])
  today = pd.to_datetime(datetime.now().date())

  # Business Days / Age Calculation
  df["Days Open"] = (today - df["Issue Date"]).dt.days

  def assign_sla(row):
    if row["Confirmed"]:
      return "Confirmed"
    elif row["Days Open"] >= 2:
      return "CRITICAL (>48 hrs)"
    else:
      return "Pending (<48 hrs)"

  df["SLA Status"] = df.apply(assign_sla, axis=1)
else:
  df = pd.DataFrame(
      columns=[
          "PO Number",
          "Vendor",
          "Issue Date",
          "Item Description",
          "Confirmed",
          "Days Open",
          "SLA Status",
      ]
  )

# --- METRIC CARDS OVERVIEW ---
col1, col2, col3, col4 = st.columns(4)
total_open = len(df[df["Confirmed"] == False])
critical_overdue = len(df[df["SLA Status"] == "CRITICAL (>48 hrs)"])
pending_ok = len(df[df["SLA Status"] == "Pending (<48 hrs)"])
total_confirmed = len(df[df["Confirmed"] == True])

col1.metric("Total Open POs", total_open)
col2.metric(
    "Critical Overdue (>48 Hrs)", critical_overdue, delta_color="inverse"
)
col3.metric("Pending On-Time (<48 Hrs)", pending_ok)
col4.metric("Confirmed", total_confirmed)

st.divider()

# --- TAB INTERFACE ---
tab_confirm, tab_exception, tab_all = st.tabs([
    "⚡ Quick Confirm PO",
    "🚨 Overdue Exception Queue (>48 Hours)",
    "📋 All Purchase Orders & Export",
])

# --- TAB 1: QUICK CONFIRMATION FORM ---
with tab_confirm:
  st.subheader("Receive & Register Order Acknowledgment")
  st.write(
      "Paste or scan a PO number below to clear it from your overdue queue:"
  )

  c1, c2 = st.columns([3, 1])
  with c1:
    po_input = st.text_input(
        "Enter PO Number:", value="", placeholder="e.g., 450010480"
    )

  with c2:
    st.write(" ")
    st.write(" ")
    if st.button("Mark as Confirmed", type="primary"):
      if po_input.strip() in st.session_state.po_records["PO Number"].values:
        st.session_state.po_records.loc[
            st.session_state.po_records["PO Number"] == po_input.strip(),
            "Confirmed",
        ] = True
        st.success(f"PO #{po_input.strip()} successfully marked as Confirmed!")
        st.rerun()
      else:
        st.error(f"PO Number '{po_input.strip()}' not found in active records.")

# --- TAB 2: OVERDUE EXCEPTION QUEUE ---
with tab_exception:
  st.subheader("Vendor Follow-Up Queue")
  overdue_df = df[df["SLA Status"] == "CRITICAL (>48 hrs)"]

  if overdue_df.empty:
    st.success("🎉 No overdue confirmations! All issued POs are acknowledged.")
  else:
    st.warning(
        f"There are {len(overdue_df)} orders issued over 48 hours ago awaiting vendor confirmation."
    )

    # Display Overdue Table
    st.dataframe(
        overdue_df[[
            "PO Number",
            "Vendor",
            "Issue Date",
            "Days Open",
            "Item Description",
        ]],
        use_container_width=True,
        hide_index=True,
    )

    st.divider()
    st.subheader("Generate Batch Vendor Email")

    vendor_options = overdue_df["Vendor"].unique()
    selected_vendor = st.selectbox(
        "Select Vendor to Generate Outbound Follow-Up Email:",
        options=vendor_options,
    )

    vendor_pos = overdue_df[overdue_df["Vendor"] == selected_vendor]

    # Build PO List Text
    po_text_list = []
    for _, row in vendor_pos.iterrows():
      formatted_date = row["Issue Date"].strftime("%m/%d/%Y")
      po_text_list.append(
          f"• PO #{row['PO Number']} (Issued: {formatted_date}) - Item:"
          f" {row['Item Description']}"
      )

    po_formatted_str = "\n".join(po_text_list)

    email_template = f"""Subject: URGENT: Order Confirmation & Acknowledgment Required - {selected_vendor} / Plant Purchasing

Hi {selected_vendor} Customer Service Team,

We issued the following Purchase Order(s) over 48 hours ago and have not yet received an official order acknowledgment or estimated ship date:

{po_formatted_str}

Please reply directly to this email with confirmation of order processing and expected delivery schedules.

Thank you,
Purchasing Department"""

    st.text_area(
        "Copy/Paste into Email (Outlook/Gmail):", value=email_template, height=240
    )

# --- TAB 3: ALL ORDERS & EXPORT REPORT ---
with tab_all:
  st.subheader("Complete Order Register")
  st.dataframe(df, use_container_width=True,hide_index=True)

  # Downloadable CSV Report
  if not df.empty:
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="📥 Download Overdue & Confirmation Report (CSV)",
        data=csv,
        file_name=f"po_confirmation_report_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv",
    )
