"""
woocommerce_zoho_export.py

Streamlit module wrapper for "WooCommerce → Accounting Export Tool"
Uses:
- SessionManager for access control
- ActivityLogger for logging actions/errors
- Credentials from st.secrets with keys: api_url, consumer_key, consumer_secret

Notes:
- Starting sequence has NO default. User must enter a valid integer.
- Item DB can be uploaded via the UI or read from item_database.xlsx in the app folder.
- Output: ZIP containing CSV (line items) and XLSX (summary + order details).
"""

import streamlit as st
import pandas as pd
import requests
from datetime import datetime
from dateutil.parser import parse
from collections import Counter
from io import BytesIO
from zipfile import ZipFile
from openpyxl.utils import get_column_letter
from openpyxl.styles import Font, Alignment
from openpyxl import Workbook

from auth import SessionManager
from config.database import ActivityLogger

TOOL_NAME = "WooCommerce → Accounting Export Tool (Module)"

# Utility
def to_float(x):
    try:
        if x is None or x == "":
            return 0.0
        return float(x)
    except Exception:
        return 0.0

def read_item_database(uploaded_file):
    """
    Read item database either from uploaded file or from disk (item_database.xlsx).
    Returns name_mapping dict (lowercase woo_name -> {'zoho', 'hsn', 'usage_unit'}) and dataframe (or None).
    """
    try:
        if uploaded_file:
            item_db_df = pd.read_excel(uploaded_file, dtype=str)
        else:
            item_db_df = pd.read_excel("item_database.xlsx", dtype=str)
        # Normalize headers
        item_db_df.columns = [str(col).strip().lower() for col in item_db_df.columns]
        required_columns = ["woocommerce name", "zoho name", "hsn", "usage unit"]
        for col in required_columns:
            if col not in item_db_df.columns:
                st.warning(f"item_database.xlsx missing required column: '{col}'")
                # Proceed with whichever columns exist; mapping will be partial
        # Build mapping
        name_mapping = {}
        for _, row in item_db_df.iterrows():
            woo_raw = row.get("woocommerce name", "")
            woo = str(woo_raw).strip().lower()
            if not woo:
                continue
            if woo in name_mapping:
                continue
            zoho = "" if pd.isna(row.get("zoho name")) else str(row.get("zoho name")).strip()
            hsn_val = "" if pd.isna(row.get("hsn")) else str(row.get("hsn")).strip()
            usage_val = "" if pd.isna(row.get("usage unit")) else str(row.get("usage unit")).strip()
            name_mapping[woo] = {"zoho": zoho, "hsn": hsn_val, "usage_unit": usage_val}
        return name_mapping, item_db_df
    except FileNotFoundError:
        st.info("No item_database.xlsx found in app folder and no upload provided. Proceeding without mapping.")
        return {}, None
    except Exception as e:
        st.error(f"Error reading item database: {e}")
        ActivityLogger.log(
            user_id=SessionManager.get_user()['id'],
            action_type='module_error',
            module_key='woocommerce_export',
            description=f"Error reading item_database.xlsx: {e}",
            success=False
        )
        return {}, None

def fetch_orders_from_woocommerce(api_url, consumer_key, consumer_secret, start_iso, end_iso):
    """
    Fetch orders via WooCommerce REST API with pagination.
    Returns list of orders (JSON).
    """
    all_orders = []
    page = 1
    try:
        with st.spinner("Fetching orders from WooCommerce..."):
            while True:
                resp = requests.get(
                    f"{api_url.rstrip('/')}/orders",
                    params={
                        "after": start_iso,
                        "before": end_iso,
                        "per_page": 100,
                        "page": page
                    },
                    auth=(consumer_key, consumer_secret),
                    timeout=30
                )
                resp.raise_for_status()
                orders = resp.json()
                if not orders:
                    break
                all_orders.extend(orders)
                page += 1
        return all_orders
    except requests.exceptions.RequestException as e:
        raise

def transform_orders_to_rows(all_orders, name_mapping, invoice_prefix, start_sequence):
    """
    Transform completed orders to CSV rows and produce replacements log.
    Returns (csv_rows_list, replacements_log_list, completed_orders_list)
    """
    all_orders.sort(key=lambda x: x["id"])
    completed_orders = [o for o in all_orders if o.get("status","").lower() == "completed"]
    if not completed_orders:
        return [], [], []

    csv_rows = []
    replacements_log = []
    sequence_number = start_sequence

    for order in completed_orders:
        order_id = order["id"]
        invoice_number = f"{invoice_prefix}{sequence_number:05d}"
        sequence_number += 1
        invoice_date = parse(order["date_created"]).strftime("%Y-%m-%d %H:%M:%S")
        customer_name = f"{order['billing'].get('first_name','')} {order['billing'].get('last_name','')}".strip()
        place_of_supply = order['billing'].get('state', '')
        currency = order.get('currency','')
        shipping_charge = to_float(order.get('shipping_total',0))
        entity_discount = to_float(order.get('discount_total',0))

        for item in order.get("line_items", []):
            product_meta = item.get("meta_data",[]) or []
            # Default - try to pick HSN & usage unit from item's meta_data first
            hsn = ""
            usage_unit = ""
            for meta in product_meta:
                key = str(meta.get("key","")).lower()
                if key == "hsn":
                    hsn_val = meta.get("value","")
                    hsn = "" if hsn_val is None else str(hsn_val)
                if key == "usage unit":
                    usage_val = meta.get("value","")
                    usage_unit = "" if usage_val is None else str(usage_val)

            # Replace item name using mapping (case-insensitive)
            original_item_name = item.get("name","")
            item_name_lower = str(original_item_name).strip().lower()
            if item_name_lower in name_mapping:
                mapping = name_mapping[item_name_lower]
                item_name_final = mapping.get("zoho", original_item_name) or original_item_name
                hsn_from_db = mapping.get("hsn", "")
                usage_from_db = mapping.get("usage_unit", "")
                if hsn_from_db:
                    hsn = hsn_from_db
                if usage_from_db:
                    usage_unit = usage_from_db
                replacements_log.append({
                    "Original WooCommerce Name": original_item_name,
                    "Replaced Zoho Name": item_name_final,
                    "HSN": hsn,
                    "Usage unit": usage_unit
                })
            else:
                item_name_final = original_item_name

            # Ensure tax numeric
            tax_class = item.get("tax_class") or ""
            try:
                item_tax_pct = float(tax_class)
            except (TypeError, ValueError):
                item_tax_pct = 0.0

            row = {
                "Invoice Number": invoice_number,
                "PurchaseOrder": order_id,
                "Invoice Date": invoice_date,
                "Invoice Status": order.get("status","").capitalize(),
                "Customer Name": customer_name,
                "Place of Supply": place_of_supply,
                "Currency Code": currency,
                "Item Name": item_name_final,
                "HSN/SAC": hsn,
                "Item Type": item.get("type","goods"),
                "Quantity": item.get("quantity",0),
                "Usage unit": usage_unit,
                "Item Price": to_float(item.get("price",0)),
                "Is Inclusive Tax":"FALSE",
                "Item Tax %": item_tax_pct,
                "Discount Type":"entity_level",
                "Is Discount Before Tax":"TRUE",
                "Entity Discount Amount":entity_discount,
                "Shipping Charge":shipping_charge,
                "Item Tax Exemption Reason":"ITEM EXEMPT FROM GST",
                "Supply Type":"Exempted",
                "GST Treatment":"consumer"
            }
            csv_rows.append(row)
    return csv_rows, replacements_log, completed_orders

def build_summary_and_order_details(completed_orders, invoice_prefix, start_sequence):
    # Summary metrics
    all_orders_count = len(completed_orders)
    status_counts = Counter(o.get("status","").lower() for o in completed_orders)

    first_order_id = completed_orders[0]["id"] if completed_orders else None
    last_order_id = completed_orders[-1]["id"] if completed_orders else None
    first_invoice_number = f"{invoice_prefix}{start_sequence:05d}"
    last_invoice_number = f"{invoice_prefix}{(start_sequence + len(completed_orders) - 1):05d}" if completed_orders else None

    total_revenue_by_order_total = 0.0
    order_details_rows = []
    seq_temp = start_sequence
    for order in completed_orders:
        order_total = to_float(order.get("total",0))
        refunds = order.get("refunds") or []
        refund_total = sum(to_float(r.get("amount") or r.get("total") or r.get("refund_total") or 0) for r in refunds)
        net_total = order_total - refund_total
        total_revenue_by_order_total += net_total

        invoice_number_temp = f"{invoice_prefix}{seq_temp:05d}"
        seq_temp += 1
        order_details_rows.append({
            "Invoice Number": invoice_number_temp,
            "Order Number": order["id"],
            "Date": parse(order["date_created"]).strftime("%Y-%m-%d %H:%M:%S"),
            "Customer Name": f"{order['billing'].get('first_name','')} {order['billing'].get('last_name','')}".strip(),
            "Order Total": net_total
        })

    summary_metrics = {
        "Metric":[
            "Total Orders Fetched",
            "Completed Orders",
            "Total Revenue (Net of Refunds)",
            "Completed Order ID Range",
            "Invoice Number Range"
        ],
        "Value":[
            all_orders_count,
            all_orders_count,
            total_revenue_by_order_total,
            f"{first_order_id} → {last_order_id}" if completed_orders else "",
            f"{first_invoice_number} → {last_invoice_number}" if completed_orders else ""
        ]
    }
    summary_df = pd.DataFrame(summary_metrics)
    order_details_df = pd.DataFrame(order_details_rows)
    grand_total = order_details_df["Order Total"].sum() if not order_details_df.empty else 0.0
    grand_total_row = {
        "Invoice Number": "Grand Total",
        "Order Number": "",
        "Date": "",
        "Customer Name": "",
        "Order Total": grand_total
    }
    if not order_details_df.empty:
        order_details_df = pd.concat([order_details_df, pd.DataFrame([grand_total_row])], ignore_index=True)
    else:
        order_details_df = pd.DataFrame([grand_total_row])
    return summary_df, order_details_df

def create_excel_bytes(summary_df, order_details_df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        summary_df.to_excel(writer, index=False, sheet_name="Summary Metrics")
        order_details_df.to_excel(writer, index=False, sheet_name="Order Details")
        for sheet_name in writer.sheets:
            ws = writer.sheets[sheet_name]
            # header formatting
            for cell in ws[1]:
                cell.font = Font(bold=True)
                cell.alignment = Alignment(horizontal="center")
            # adjust column widths
            for col in ws.columns:
                max_length = max(len(str(c.value)) if c.value is not None else 0 for c in col) + 2
                ws.column_dimensions[get_column_letter(col[0].column)].width = max_length
    return output.getvalue()

def create_zip_bytes(csv_bytes, excel_bytes, start_date, end_date):
    zip_buffer = BytesIO()
    with ZipFile(zip_buffer, "w") as zip_file:
        zip_file.writestr(f"orders_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.csv", csv_bytes)
        zip_file.writestr(f"summary_report_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.xlsx", excel_bytes)
    zip_buffer.seek(0)
    return zip_buffer.getvalue()

# Main module show()
def show():
    """
    Streamlit entry point for the module.
    """
    SessionManager.require_module_access('woocommerce_zoho_export')
    user = SessionManager.get_user()
    profile = SessionManager.get_user_profile()

    st.markdown("### 📦 WooCommerce → Accounting Export Tool")
    st.markdown("Fetch orders from WooCommerce and export accounting CSV + Excel inside a ZIP.")
    st.markdown("---")

    # Credentials from st.secrets using requested names
    api_url = st.secrets.get("api_url")
    consumer_key = st.secrets.get("consumer_key")
    consumer_secret = st.secrets.get("consumer_secret")

    if not api_url or not consumer_key or not consumer_secret:
        missing = [k for k, v in {
            "api_url": api_url,
            "consumer_key": consumer_key,
            "consumer_secret": consumer_secret
        }.items() if not v]
        st.error("WooCommerce API credentials missing in st.secrets: " + ", ".join(missing))
        # Log and stop further UI actions
        ActivityLogger.log(
            user_id=user['id'],
            action_type='module_error',
            module_key='woocommerce_export',
            description=f"Missing WooCommerce credentials: {missing}",
            success=False
        )
        return

    # Item DB upload (optional)
    st.markdown("#### Item Database (optional)")
    st.markdown("Upload `item_database.xlsx` with columns: WooCommerce Name, Zoho Name, HSN, Usage Unit (case-insensitive).")
    uploaded_item_db = st.file_uploader("Upload item_database.xlsx (optional)", type=['xlsx', 'xls'])
    name_mapping, item_db_df = read_item_database(uploaded_item_db)
    if item_db_df is not None:
        with st.expander("Preview Item Database"):
            st.dataframe(item_db_df, use_container_width=True)

    # Date inputs
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Start Date")
    with col2:
        end_date = st.date_input("End Date")

    if start_date > end_date:
        st.error("Start date cannot be after end date.")
        return

    # Invoice prefix and starting sequence (no default for starting sequence)
    invoice_prefix = st.text_input("Invoice Prefix", value="ECHE/2526/")
    start_sequence_input = st.text_input("Starting Sequence Number (no default; required)", value="")

    # Validate sequence input only when pressing button
    fetch_button = st.button("Fetch Orders", disabled=False)

    # Space for logs
    log_container = st.empty()
    logs = []

    def append_log(msg, lvl="info"):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{timestamp}] {lvl.upper()}: {msg}"
        logs.append(line)
        # show latest logs (keep visible)
        log_container.text_area("Logs", value="\n".join(logs), height=240)

    if fetch_button:
        # Validate start sequence
        if not start_sequence_input or start_sequence_input.strip() == "":
            st.error("Please enter a Starting Sequence Number (required).")
            append_log("Missing starting sequence number.", "error")
            ActivityLogger.log(
                user_id=user['id'],
                action_type='module_error',
                module_key='woocommerce_export',
                description="Missing starting sequence number",
                success=False
            )
            return
        try:
            start_sequence = int(start_sequence_input)
            if start_sequence < 1:
                raise ValueError("Sequence must be >= 1")
        except Exception as e:
            st.error(f"Invalid starting sequence number: {e}")
            append_log(f"Invalid starting sequence number: {e}", "error")
            ActivityLogger.log(
                user_id=user['id'],
                action_type='module_error',
                module_key='woocommerce_export',
                description=f"Invalid starting sequence number: {e}",
                success=False
            )
            return

        append_log("Starting WooCommerce export...", "info")
        ActivityLogger.log(
            user_id=user['id'],
            action_type='module_use',
            module_key='woocommerce_export',
            description=f"User started WooCommerce export for {start_date} to {end_date}"
        )

        # Prepare ISO times
        start_iso = start_date.strftime("%Y-%m-%dT00:00:00")
        end_iso = end_date.strftime("%Y-%m-%dT23:59:59")

        # Fetch orders
        try:
            all_orders = fetch_orders_from_woocommerce(api_url, consumer_key, consumer_secret, start_iso, end_iso)
            append_log(f"Fetched {len(all_orders)} orders from WooCommerce.", "info")
        except Exception as e:
            st.error(f"Error fetching orders: {e}")
            append_log(f"Error fetching orders: {e}", "error")
            ActivityLogger.log(
                user_id=user['id'],
                action_type='module_error',
                module_key='woocommerce_export',
                description=f"Error fetching orders: {e}",
                success=False
            )
            return

        if not all_orders:
            st.warning("No orders found in this date range.")
            append_log("No orders found in this date range.", "info")
            ActivityLogger.log(
                user_id=user['id'],
                action_type='module_use',
                module_key='woocommerce_export',
                description=f"No orders found for {start_date} to {end_date}"
            )
            return

        # Transform orders
        csv_rows, replacements_log, completed_orders = transform_orders_to_rows(
            all_orders, name_mapping, invoice_prefix, start_sequence
        )

        if not completed_orders:
            st.warning("No completed orders found in this date range.")
            append_log("No completed orders found.", "info")
            ActivityLogger.log(
                user_id=user['id'],
                action_type='module_use',
                module_key='woocommerce_export',
                description=f"No completed orders for {start_date} to {end_date}"
            )
            return

        df = pd.DataFrame(csv_rows)
        # Show preview
        st.subheader("Line Items Preview (first 50 rows)")
        st.dataframe(df.head(50), use_container_width=True)

        if replacements_log:
            st.subheader("Item Name Replacements Log")
            st.dataframe(pd.DataFrame(replacements_log), use_container_width=True)
            append_log(f"Applied {len(replacements_log)} item name replacements.", "info")

        # Summary and Order Details
        summary_df, order_details_df = build_summary_and_order_details(completed_orders, invoice_prefix, start_sequence)
        st.subheader("Summary Metrics")
        st.dataframe(summary_df, use_container_width=True)

        # Prepare files
        try:
            csv_bytes = df.to_csv(index=False).encode('utf-8')
            excel_bytes = create_excel_bytes(summary_df, order_details_df)
            zip_bytes = create_zip_bytes(csv_bytes, excel_bytes, start_date, end_date)
        except Exception as e:
            st.error(f"Error preparing exports: {e}")
            append_log(f"Error preparing exports: {e}", "error")
            ActivityLogger.log(
                user_id=user['id'],
                action_type='module_error',
                module_key='woocommerce_export',
                description=f"Error preparing exports: {e}",
                success=False
            )
            return

        # Show totals
        total_revenue = summary_df.loc[summary_df['Metric'] == "Total Revenue (Net of Refunds)", 'Value'].values
        append_log(f"Export prepared successfully. Orders exported: {len(completed_orders)}", "info")
        st.success(f"Export ready — {len(completed_orders)} completed orders. Download below.")
        ActivityLogger.log(
            user_id=user['id'],
            action_type='module_use',
            module_key='woocommerce_export',
            description=f"Exported {len(completed_orders)} completed orders from {start_date} to {end_date}",
            metadata={'orders_exported': len(completed_orders), 'date_from': str(start_date), 'date_to': str(end_date)}
        )

        st.download_button(
            label="Download CSV + Excel (Combined ZIP)",
            data=zip_bytes,
            file_name=f"woocommerce_export_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.zip",
            mime="application/zip"
        )
