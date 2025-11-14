"""
Order Extractor Module
Fetch orders from WooCommerce between dates and export to Excel

VERSION HISTORY:
1.3.0 - Added transaction ID and column reordering - 11/12/25
      ADDITIONS:
      - Transaction ID now included in export
      - Columns reordered: S.No, Order #, Name, Items Ordered, Total Items,
        Shipping Address, Mobile Number, Customer Notes, Order Total,
        Payment Method, Transaction ID, Order Status
      - Empty customer notes filled with "-"
1.2.0 - Added payment method column to export - 11/11/25
      ADDITIONS:
      - Payment method now included in Orders sheet export
      - Pulled from WooCommerce API payment_method_title field
1.1.0 - Added customer notes column to export - 11/11/25
      ADDITIONS:
      - Customer notes now included in Orders sheet export
      - Notes pulled from WooCommerce API customer_note field
      - Displayed in both preview table and Excel download
1.0.0 - WooCommerce order extractor with Excel export - 11/11/25
KEY FUNCTIONS:
- Fetch orders from WooCommerce API with date filters (max 31 days)
- Pagination support (100 orders per page)
- Selectable orders with persistent checkboxes
- Two-sheet Excel export (Orders + Item Summary)
- Payment method, customer notes, and transaction ID extraction
- Rate limiting and retry logic
- Activity logging for audit trail
"""
import streamlit as st
import pandas as pd
import requests
from io import BytesIO
from datetime import datetime, timedelta
import xlsxwriter
import time
from auth.session import SessionManager
from config.database import ActivityLogger

def show():
    """Main entry point for Order Extractor module"""
    
    # Ensure user has access to this module
    SessionManager.require_module_access('order_extractor')
    
    # Get current user info
    user = SessionManager.get_user()
    profile = SessionManager.get_user_profile()
    
    # Module header
    st.markdown("### 📦 Order Extractor")
    st.markdown("Extract orders from WooCommerce between dates and export to Excel")
    st.markdown("---")
    
    # Validate API credentials
    try:
        WC_API_URL = st.secrets["woocommerce"]["api_url"]
        WC_CONSUMER_KEY = st.secrets["woocommerce"]["consumer_key"]
        WC_CONSUMER_SECRET = st.secrets["woocommerce"]["consumer_secret"]
    except KeyError as e:
        st.error("⚠️ WooCommerce API credentials are missing from secrets!")
        st.info("""
        **Required secrets:**
        ```toml
        [woocommerce]
        api_url = "https://your-site.com/wp-json/wc/v3"
        consumer_key = "ck_xxxxx"
        consumer_secret = "cs_xxxxx"
        ```
        """)
        st.stop()
    
    # Initialize session state with namespacing
    if "order_extractor_orders_df" not in st.session_state:
        st.session_state.order_extractor_orders_df = None
    if "order_extractor_orders_data" not in st.session_state:
        st.session_state.order_extractor_orders_data = None
    
    # Date selection
    st.markdown("#### 📅 Select Date Range")
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Start Date", datetime.today())
    with col2:
        end_date = st.date_input("End Date", datetime.today())
    
    # Validate date range
    date_range_valid = True
    if start_date > end_date:
        st.error("❌ Start date cannot be after end date.")
        date_range_valid = False
    elif (end_date - start_date).days > 31:
        st.error("❌ Date range cannot exceed 31 days. Please select a shorter period.")
        date_range_valid = False
    
    # Fetch button
    if st.button("🔍 Fetch Orders", disabled=not date_range_valid, type="primary"):
        with st.spinner("Fetching orders from WooCommerce..."):
            orders = fetch_orders(
                WC_API_URL, 
                WC_CONSUMER_KEY, 
                WC_CONSUMER_SECRET, 
                start_date, 
                end_date
            )
            
            if orders:
                st.session_state.order_extractor_orders_data = orders
                st.session_state.order_extractor_orders_df = process_orders(orders)
                st.success(f"✅ Successfully fetched {len(orders)} orders!")
                
                # Log fetch activity
                ActivityLogger.log(
                    user_id=user['id'],
                    action_type='order_fetch',
                    module_key='order_extractor',
                    description=f"Fetched {len(orders)} orders from {start_date} to {end_date}",
                    metadata={
                        'start_date': str(start_date),
                        'end_date': str(end_date),
                        'order_count': len(orders)
                    }
                )
            else:
                st.session_state.order_extractor_orders_data = None
                st.session_state.order_extractor_orders_df = None
                st.warning("No orders found for the selected date range.")
    
    # Display orders
    if st.session_state.order_extractor_orders_df is not None:
        df = st.session_state.order_extractor_orders_df
        
        # Remove Line Items for display to avoid PyArrow errors
        display_df = df.drop(columns=["Line Items"]).copy()
        
        # Cast numeric columns safely
        numeric_cols = ["Order ID", "No of Items", "Order Value", "Total Items"]
        for col in numeric_cols:
            if col in display_df.columns:
                if col in ["Order ID", "No of Items", "Total Items"]:
                    display_df[col] = display_df[col].astype(int)
                elif col == "Order Value":
                    display_df[col] = display_df[col].astype(float)
        
        st.markdown("---")
        st.write(f"### 📊 Total Orders Found: {len(display_df)}")
        
        # Editable table with persistent checkboxes
        edited_df = st.data_editor(
            display_df,
            hide_index=True,
            column_config={
                "Select": st.column_config.CheckboxColumn(
                    "Select",
                    help="Select orders to download",
                    default=True,
                    required=False
                )
            },
            width='stretch',
            key="order_extractor_orders_table"
        )
        
        # Sync Select column immediately back to session_state
        st.session_state.order_extractor_orders_df['Select'] = edited_df['Select']
        
        # Build selected_orders from full data safely
        selected_order_ids = st.session_state.order_extractor_orders_df.loc[
            st.session_state.order_extractor_orders_df['Select'] == True, 'Order ID'
        ].tolist()
        
        if st.session_state.order_extractor_orders_data is not None:
            selected_orders_list = [
                o for o in st.session_state.order_extractor_orders_data 
                if o['id'] in selected_order_ids
            ]
        else:
            selected_orders_list = []
        
        selected_orders = process_orders(selected_orders_list)
        
        if not selected_orders.empty:
            st.success(f"✅ {len(selected_orders)} orders selected for download.")
            
            # Generate Excel
            excel_data = generate_excel(selected_orders)
            
            # Filename with cleaner format
            filename = f"orders_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.xlsx"
            
            # Download button with logging
            if st.download_button(
                label="📥 Download Selected Orders as Excel",
                data=excel_data,
                file_name=filename,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary"
            ):
                # Log the download
                ActivityLogger.log(
                    user_id=user['id'],
                    action_type='order_download',
                    module_key='order_extractor',
                    description=f"Downloaded {len(selected_orders)} orders from {start_date} to {end_date}",
                    metadata={
                        'start_date': str(start_date),
                        'end_date': str(end_date),
                        'order_count': len(selected_orders),
                        'order_ids': selected_order_ids,
                        'filename': filename
                    }
                )
                st.toast("✅ Download logged successfully!", icon="✅")
        else:
            st.info("ℹ️ Select at least one order to enable download.")
    else:
        st.info("ℹ️ Fetch orders by selecting a date range and clicking 'Fetch Orders'.")
    
    # Help section
    with st.expander("ℹ️ Help & Instructions"):
        st.markdown("""
        ### How to use Order Extractor:
        
        1. **Select Date Range**: Choose start and end dates (max 31 days)
        2. **Fetch Orders**: Click to retrieve orders from WooCommerce
        3. **Review Orders**: Check the order list and select which ones to download
        4. **Download Excel**: Export selected orders to Excel with two sheets:
           - **Orders Sheet**: Customer details and order information
           - **Item Summary Sheet**: Aggregated item quantities
        
        ### Excel Output:
        - **Sheet 1 (Orders)**: Order number, customer name, items, address, total, status
        - **Sheet 2 (Item Summary)**: Item ID, name, total quantity across all orders
        
        ### Troubleshooting:
        - **No orders found**: Check date range and WooCommerce order dates
        - **API errors**: Contact admin to verify WooCommerce API credentials
        - **Timeout**: Try a shorter date range (fewer orders)
        """)


def fetch_orders(api_url, consumer_key, consumer_secret, start_date, end_date):
    """Fetch orders from WooCommerce between two dates with error handling and rate limiting"""
    all_orders = []
    page = 1
    max_retries = 3
    retry_delay = 2  # seconds
    
    while True:
        retries = 0
        while retries < max_retries:
            try:
                response = requests.get(
                    f"{api_url}/orders",
                    params={
                        "after": f"{start_date}T00:00:00",
                        "before": f"{end_date}T23:59:59",
                        "per_page": 100,
                        "page": page,
                        "status": "any",
                        "order": "asc",
                        "orderby": "id"
                    },
                    auth=(consumer_key, consumer_secret),
                    timeout=30
                )
                
                # Handle rate limiting
                if response.status_code == 429:
                    retry_after = int(response.headers.get('Retry-After', 60))
                    st.warning(f"Rate limit reached. Waiting {retry_after} seconds before retrying...")
                    time.sleep(retry_after)
                    retries += 1
                    continue
                
                # Handle other errors
                if response.status_code != 200:
                    st.error(f"Error fetching orders: {response.status_code} - {response.text}")
                    return []
                
                orders = response.json()
                
                # Validate response is a list
                if not isinstance(orders, list):
                    st.error("Invalid response format from WooCommerce API")
                    return []
                
                if not orders:
                    return all_orders
                
                all_orders.extend(orders)
                page += 1
                break  # Success, exit retry loop
            
            except requests.exceptions.Timeout:
                st.error("Network timeout. Please check your connection and try again.")
                return []
            except requests.exceptions.ConnectionError:
                st.error("Network issue - Unable to connect to WooCommerce. Please try again.")
                return []
            except requests.exceptions.RequestException as e:
                if retries < max_retries - 1:
                    st.warning(f"Request failed. Retrying in {retry_delay} seconds... (Attempt {retries + 1}/{max_retries})")
                    time.sleep(retry_delay)
                    retries += 1
                else:
                    st.error(f"Network issue - {str(e)}. Please try again.")
                    return []
            except Exception as e:
                st.error(f"Unexpected error: {str(e)}. Please try again.")
                return []
    
    return all_orders


def process_orders(orders):
    """Process raw WooCommerce orders into a structured DataFrame with validation"""
    data = []
    for idx, order in enumerate(sorted(orders, key=lambda x: x.get('id', 0))):
        try:
            # Safely get order data with defaults
            order_id = order.get('id', 'N/A')
            date_created = order.get('date_created', '')
            
            # Parse date safely
            try:
                order_date = datetime.strptime(date_created, "%Y-%m-%dT%H:%M:%S").strftime("%Y-%m-%d")
            except:
                order_date = date_created[:10] if date_created else 'N/A'
            
            # Build Items Ordered with quantities
            line_items = order.get('line_items', [])
            items_ordered = ", ".join([
                f"{item.get('name', 'Unknown')} x {item.get('quantity', 1)}" 
                for item in line_items
            ])
            
            # Total items (sum of quantities)
            total_items = sum(item.get('quantity', 1) for item in line_items)
            
            # Safely get shipping address
            shipping = order.get("shipping", {})
            shipping_address = ", ".join(filter(None, [
                shipping.get("address_1"),
                shipping.get("address_2"),
                shipping.get("city"),
                shipping.get("state"),
                shipping.get("postcode"),
                shipping.get("country")
            ]))
            
            # Safely get billing info
            billing = order.get('billing', {})
            full_name = f"{billing.get('first_name', '')} {billing.get('last_name', '')}".strip()
            if not full_name:
                full_name = "N/A"

            # Get customer notes and fill empty with "-"
            customer_notes = order.get('customer_note', '').strip()
            if not customer_notes:
                customer_notes = "-"

            # Get transaction ID
            transaction_id = order.get('transaction_id', '')
            if not transaction_id:
                transaction_id = "-"

            # Reordered columns as per user request
            data.append({
                "S.No": idx + 1,
                "Select": True,
                "Order ID": order_id,
                "Date": order_date,
                "Name": full_name,
                "Items Ordered": items_ordered if items_ordered else 'N/A',
                "Total Items": total_items,
                "Shipping Address": shipping_address if shipping_address else 'N/A',
                "Mobile Number": billing.get('phone', ''),
                "Customer Notes": customer_notes,
                "Order Value": float(order.get('total', 0)),
                "Payment Method": order.get('payment_method_title', ''),
                "Transaction ID": transaction_id,
                "Order Status": order.get('status', 'unknown'),
                "No of Items": len(line_items),  # Keep for backward compatibility
                "Line Items": line_items  # for Sheet 2
            })
        except Exception as e:
            st.warning(f"Skipped order due to data error: {str(e)}")
            continue
    
    return pd.DataFrame(data)


def generate_excel(df):
    """Generate a customized Excel file with two sheets: Orders and Item Summary"""
    output = BytesIO()

    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        # --- Sheet 1: Orders ---
        # Reordered columns as per user request
        sheet1_df = df[[
            "Order ID", "Name", "Items Ordered", "Total Items",
            "Shipping Address", "Mobile Number", "Customer Notes",
            "Order Value", "Payment Method", "Transaction ID", "Order Status"
        ]].copy()

        # Rename columns for better display
        sheet1_df.rename(columns={
            "Order ID": "Order #",
            "Order Value": "Order Total"
        }, inplace=True)

        # Insert S.No as first column
        sheet1_df.insert(0, "S.No", range(1, len(sheet1_df)+1))
        sheet1_df.to_excel(writer, index=False, sheet_name='Orders')
        workbook = writer.book
        worksheet1 = writer.sheets['Orders']
        
        # Format headers
        header_format = workbook.add_format({'bold': True, 'font_color': 'black'})
        for col_num, value in enumerate(sheet1_df.columns.values):
            worksheet1.write(0, col_num, value, header_format)
            worksheet1.set_column(col_num, col_num, 30)
        
        # Row height
        for row_num in range(1, len(sheet1_df) + 1):
            worksheet1.set_row(row_num, 20)
        
        # --- Sheet 2: Item Summary ---
        items_list = []
        for line_items in df['Line Items']:
            for item in line_items:
                items_list.append((
                    item.get('product_id', None),
                    item.get('variation_id', None),
                    item.get('name', ''),
                    item.get('quantity', 1)
                ))
        
        summary_df = pd.DataFrame(items_list, columns=['Item ID', 'Variation ID', 'Item Name', 'Quantity'])
        summary_df = summary_df.groupby(['Item ID', 'Variation ID', 'Item Name'], as_index=False).sum()
        summary_df = summary_df.sort_values(['Item ID', 'Variation ID', 'Item Name'])
        
        summary_df.to_excel(writer, index=False, sheet_name='Item Summary')
        worksheet2 = writer.sheets['Item Summary']
        
        # Format headers
        for col_num, value in enumerate(summary_df.columns.values):
            worksheet2.write(0, col_num, value, header_format)
            worksheet2.set_column(col_num, col_num, 25)
        
        # Row height
        for row_num in range(1, len(summary_df) + 1):
            worksheet2.set_row(row_num, 20)
    
    output.seek(0)
    return output
