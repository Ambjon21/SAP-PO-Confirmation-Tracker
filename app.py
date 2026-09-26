from datetime import datetime
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Procurement Operations Hub",
    layout="wide",
)

st.title("Procurement Operations Hub")
st.caption(
    "Plant Purchasing Exception Management: 48-Hour Order Confirmations &"
    " Blocked Invoices"
)

# Initialize Session State Data Structures
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

if "blocked_invoices" not in st.session_state:
  st.session_state.blocked_invoices = pd.DataFrame(
      columns=[
          "PO Number",
          "Invoice Number",
          "Vendor",
          "Blocking Reason",
          "Invoice Date",
          "Amount",
      ]
  )

# --- SIDEBAR: DATA IMPORT & DEMO DATA ---
with st.sidebar:
  st.header("Data Imports")

  import_type = st.radio(
      "Select Import Type:",
      ["PO Confirmations (ME2M/ME2L)", "Blocked Invoices (MRBR/MB5S)"],
  )

  uploaded_file = st.file_uploader(
      "Upload CSV or Excel File", type=["csv", "xlsx"]
  )

  if uploaded_file is not None:
    try:
      if uploaded_file.name.endswith(".csv"):
        imported_df = pd.read_csv(uploaded_file)
      else:
        imported_df = pd.read_excel(uploaded_file)

      st.success(f"Loaded {len(imported_df)} rows.")

      if import_type == "PO Confirmations (ME2M/ME2L)":
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
        req_cols = ["PO Number", "Vendor", "Issue Date", "Item Description"]
        missing = [c for c in req_cols if c not in imported_df.columns]

        if missing:
          st.error(f"Missing columns: {', '.join(missing)}")
        else:
          if "Confirmed" not in imported_df.columns:
            imported_df["Confirmed"] = False
          if st.button("Merge PO Records"):
            combined = pd.concat(
                [st.session_state.po_records, imported_df[req_cols + ["Confirmed"]]]
            )
            st.session_state.po_records = combined.drop_duplicates(
                subset=["PO Number"]
            ).reset_index(drop=True)
            st.success("PO Records updated!")
            st.rerun()

      else:  # Blocked Invoices
        col_map = {
            "Purchasing Document": "PO Number",
            "PO": "PO Number",
            "Invoice Doc.": "Invoice Number",
            "Vendor Name": "Vendor",
            "Blocking Reason": "Blocking Reason",
            "Posting Date": "Invoice Date",
            "Amount in LC": "Amount",
        }
        imported_df = imported_df.rename(columns=col_map)
        req_cols = [
            "PO Number",
            "Invoice Number",
            "Vendor",
            "Blocking Reason",
            "Invoice Date",
            "Amount",
        ]
        missing = [c for c in req_cols if c not in imported_df.columns]

        if missing:
          st.error(f"Missing columns: {', '.join(missing)}")
        else:
          if st.button("Merge Invoice Records"):
            combined = pd.concat(
                [st.session_state.blocked_invoices, imported_df[req_cols]]
            )
            st.session_state.blocked_invoices = combined.drop_duplicates(
                subset=["Invoice Number", "PO Number"]
            ).reset_index(drop=True)
            st.success("Blocked Invoices updated!")
            st.rerun()

    except Exception as e:
      st.error(f"File Parsing Error: {e}")

  st.divider()
  if st.button("Load Sample Demo Data"):
    st.session_state.po_records = pd.DataFrame([
        {
            "PO Number": "450010480",
            "Vendor": "ABC Supply Co",
            "Issue Date": "2026-09-20",
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
            "Issue Date": "2026-09-21",
            "Item Description": "Hydraulic Valves",
            "Confirmed": False,
        },
        {
            "PO Number": "450010501",
            "Vendor": "Global Industrial",
            "Issue Date": "2026-09-25",
            "Item Description": "Plant Supplies - Gloves & Towels",
            "Confirmed": False,
        },
    ])

    st.session_state.blocked_invoices = pd.DataFrame([
        {
            "PO Number": "450010480",
            "Invoice Number": "INV-90211",
            "Vendor": "ABC Supply Co",
            "Blocking Reason": "Price Variance (PO vs Invoice)",
            "Invoice Date": "2026-09-22",
            "Amount": "$1,250.00",
        },
        {
            "PO Number": "450010490",
            "Invoice Number": "INV-90884",
            "Vendor": "ABC Supply Co",
            "Blocking Reason": "Missing Goods Receipt (GR)",
            "Invoice Date": "2026-09-24",
            "Amount": "$3,400.00",
        },
        {
            "PO Number": "450010510",
            "Vendor": "Industrial Hose Ltd",
            "Invoice Number": "PENDING-SUBMISSION",
            "Blocking Reason": "No Invoice Received (Past Delivery Date)",
            "Invoice Date": "N/A",
            "Amount": "$820.00",
        },
    ])
    st.rerun()

# --- CALCULATE AGING & STATUS ---
df_po = st.session_state.po_records.copy()

if not df_po.empty:
  df_po["Issue Date"] = pd.to_datetime(df_po["Issue Date"])
  today = pd.to_datetime(datetime.now().date())
  df_po["Days Open"] = (today - df_po["Issue Date"]).dt.days

  def assign_sla(row):
    if row["Confirmed"]:
      return "Confirmed"
    elif row["Days Open"] >= 2:
      return "CRITICAL (>48 hrs)"
    else:
      return "Pending (<48 hrs)"

  df_po["SLA Status"] = df_po.apply(assign_sla, axis=1)
else:
  df_po = pd.DataFrame(
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

df_inv = st.session_state.blocked_invoices.copy()

# --- TOP METRIC CARDS ---
c1, c2, c3, c4 = st.columns(4)
c1.metric("Open POs", len(df_po[df_po["Confirmed"] == False]))
c2.metric(
    "Overdue Confirmations (>48 Hrs)",
    len(df_po[df_po["SLA Status"] == "CRITICAL (>48 hrs)"]),
    delta_color="inverse",
)
c3.metric(
    "Blocked / Late Invoices", len(df_inv), delta_color="inverse"
)
c4.metric("Confirmed POs", len(df_po[df_po["Confirmed"] == True]))

st.divider()

# --- TAB INTERFACE ---
tab1, tab2, tab3 = st.tabs([
    "🚨 48-Hour Order Confirmation Queue",
    "🛑 Blocked & Missing Invoices (MRBR)",
    "📋 Master Register & Reports",
])

# ==========================================
# TAB 1: ORDER CONFIRMATIONS
# ==========================================
with tab1:
  st.subheader("Overdue Order Acknowledgments (>48 Hours)")

  overdue_po = df_po[df_po["SLA Status"] == "CRITICAL (>48 hrs)"]

  if overdue_po.empty:
    st.success("🎉 All issued orders are confirmed within 48 hours!")
  else:
    st.dataframe(
        overdue_po[[
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
    col_a, col_b = st.columns([1, 2])

    with col_a:
      st.subheader("Quick Confirm Entry")
      po_to_confirm = st.text_input("Scan / Enter PO Number:")
      if st.button("Mark Confirmed", type="primary"):
        if (
            po_to_confirm.strip()
            in st.session_state.po_records["PO Number"].values
        ):
          st.session_state.po_records.loc[
              st.session_state.po_records["PO Number"] == po_to_confirm.strip(),
              "Confirmed",
          ] = True
          st.success(f"PO #{po_to_confirm.strip()} Confirmed!")
          st.rerun()
        else:
          st.error("PO Number not found.")

    with col_b:
      st.subheader("Generate Vendor Confirmation Email")
      selected_vendor_po = st.selectbox(
          "Select Vendor:", options=overdue_po["Vendor"].unique(), key="po_v"
      )

      v_pos = overdue_po[overdue_po["Vendor"] == selected_vendor_po]
      po_list_str = "\n".join([
          f"• PO #{r['PO Number']} (Issued: {r['Issue Date'].strftime('%m/%d/%Y')}) - {r['Item Description']}"
          for _, r in v_pos.iterrows()
      ])

      email_po_text = f"""Subject: URGENT: Order Confirmation Required - {selected_vendor_po} / Plant Purchasing

Hi {selected_vendor_po} Customer Service Team,

We issued the following Purchase Order(s) over 48 hours ago and have not received an order acknowledgment or estimated ship date:

{po_list_str}

Please reply immediately with order confirmation and expected delivery schedules.

Thank you,
Purchasing Department"""

      st.text_area(
          "Copy/Paste Email Template:",
          value=email_po_text,
          height=200,
          key="ta_po",
      )

# ==========================================
# TAB 2: BLOCKED & MISSING INVOICES
# ==========================================
with tab2:
  st.subheader("Blocked & Un-submitted Vendor Invoices")

  if df_inv.empty:
    st.info(
        "No blocked invoices loaded. Upload an SAP MRBR/MB5S export or click"
        " 'Load Sample Demo Data' in the sidebar."
    )
  else:
    st.dataframe(df_inv, use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("Generate Invoice Resolution Email")

    selected_vendor_inv = st.selectbox(
        "Select Vendor with Blocked/Late Invoices:",
        options=df_inv["Vendor"].unique(),
        key="inv_v",
    )

    v_invs = df_inv[df_inv["Vendor"] == selected_vendor_inv]
    inv_list_str = "\n".join([
        f"• PO #{r['PO Number']} | Invoice #{r['Invoice Number']} | Issue: {r['Blocking Reason']} | Amount: {r['Amount']}"
        for _, r in v_invs.iterrows()
    ])

    email_inv_text = f"""Subject: Action Required: Blocked / Missing Invoice Resolution - {selected_vendor_inv} / Plant Procurement

Hi {selected_vendor_inv} Accounts Receivable Team,

Our Accounts Payable / SAP system indicates an issue with invoice processing for the following order(s):

{inv_list_str}

Please review the blocking reasons above:
1. If Invoice is Missing: Submit tax-compliant invoices via Ariba Network or email directly to Accounts Payable referencing the PO #.
2. If Price/Quantity Variance: Reply with corrected pricing or contact purchasing for a PO amendment.

Thank you,
Purchasing Department"""

    st.text_area(
        "Copy/Paste Invoice Resolution Email:",
        value=email_inv_text,
        height=220,
        key="ta_inv",
    )

# ==========================================
# TAB 3: MASTER REGISTER & EXPORT
# ==========================================
with tab3:
  st.subheader("Full Purchase Order Register")
  if not df_po.empty:
    st.dataframe(df_po, use_container_width=True, hide_index=True)

    csv_po = df_po.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="Download PO Master Report (CSV)",
        data=csv_po,
        file_name=f"po_master_report_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv",
    )

  st.divider()
  st.subheader("Full Blocked Invoice Register")
  if not df_inv.empty:
    st.dataframe(df_inv, use_container_width=True, hide_index=True)

    csv_inv = df_inv.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="Download Blocked Invoice Report (CSV)",
        data=csv_inv,
        file_name=f"blocked_invoice_report_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv",
    )
