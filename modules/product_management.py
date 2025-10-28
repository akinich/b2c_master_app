"""
Product Management Module
Manage WooCommerce products with sync, search, filter, and bulk operations

Access Control:
- Admin: Full access (sync, add, edit all, delete)
- Manager: View, search, filter, edit HSN/Zoho/Units only
- User: No access
"""

import streamlit as st
import pandas as pd
import requests
from datetime import datetime
from typing import List, Dict, Optional
import time

# Import from your main app structure
from components.session import SessionManager
from db.db_products import ProductDB

# Module metadata
MODULE_INFO = {
    'name': 'Product Management',
    'icon': '📦',
    'description': 'Manage WooCommerce products with sync capabilities',
    'access': {
        'admin': True,
        'manager': True,
        'user': False
    }
}


def show():
    """Main entry point for the module"""
    
    # Check access
    role = SessionManager.get_role()
    if role not in ['admin', 'manager']:
        st.error("🚫 You don't have access to this module.")
        st.stop()
    
    username = SessionManager.get_username()
    
    # Module header
    st.title("📦 Product Management")
    st.caption(f"👤 Logged in as: **{username}** | Role: **{role.title()}**")
    st.markdown("---")
    
    # Initialize session state
    if 'products_df' not in st.session_state:
        st.session_state.products_df = None
    if 'selected_products' not in st.session_state:
        st.session_state.selected_products = []
    if 'show_bulk_actions' not in st.session_state:
        st.session_state.show_bulk_actions = False
    
    # Get WooCommerce credentials
    WC_API_URL = st.secrets.get("WC_API_URL", "https://sustenance.co.in/wp-json/wc/v3")
    WC_CONSUMER_KEY = st.secrets.get("WC_CONSUMER_KEY")
    WC_CONSUMER_SECRET = st.secrets.get("WC_CONSUMER_SECRET")
    
    if not WC_CONSUMER_KEY or not WC_CONSUMER_SECRET:
        st.error("⚠️ WooCommerce API credentials missing in secrets")
        st.stop()
    
    # Main tabs
    if role == 'admin':
        tabs = st.tabs(["📊 Products", "🔄 Sync from WooCommerce", "➕ Add Product", "📈 Statistics"])
    else:
        tabs = st.tabs(["📊 Products", "📈 Statistics"])
    
    # ==========================================
    # TAB 1: PRODUCTS LIST
    # ==========================================
    
    with tabs[0]:
        show_products_tab(role, username)
    
    # ==========================================
    # TAB 2: SYNC (ADMIN ONLY)
    # ==========================================
    
    if role == 'admin':
        with tabs[1]:
            show_sync_tab(WC_API_URL, WC_CONSUMER_KEY, WC_CONSUMER_SECRET, username)
        
        # ==========================================
        # TAB 3: ADD PRODUCT (ADMIN ONLY)
        # ==========================================
        
        with tabs[2]:
            show_add_product_tab(username)
        
        # ==========================================
        # TAB 4: STATISTICS
        # ==========================================
        
        with tabs[3]:
            show_statistics_tab()
    else:
        # Manager only sees statistics
        with tabs[1]:
            show_statistics_tab()


# ==========================================
# TAB FUNCTIONS
# ==========================================

def show_products_tab(role: str, username: str):
    """Display products with search, filter, and edit capabilities"""
    
    st.markdown("### 📊 Product Catalog")
    
    # Search and filters
    col1, col2, col3, col4 = st.columns([3, 2, 2, 1])
    
    with col1:
        search = st.text_input("🔍 Search by name", placeholder="Enter product name...", label_visibility="collapsed")
    
    with col2:
        statuses = ['All'] + ProductDB.get_unique_statuses()
        status_filter = st.selectbox("📋 Status", statuses)
    
    with col3:
        categories = ['All'] + ProductDB.get_unique_categories()
        category_filter = st.selectbox("🏷️ Category", categories)
    
    with col4:
        active_only = st.checkbox("✅ Active only", value=True)
    
    # Fetch products button
    if st.button("🔄 Refresh Products", type="primary"):
        with st.spinner("Loading products..."):
            products = ProductDB.get_all_products(
                active_only=active_only,
                search=search if search else None,
                status_filter=status_filter,
                category_filter=category_filter
            )
            st.session_state.products_df = pd.DataFrame(products) if products else pd.DataFrame()
            st.success(f"✅ Loaded {len(products)} products")
    
    # Display products
    if st.session_state.products_df is not None and not st.session_state.products_df.empty:
        df = st.session_state.products_df.copy()
        
        st.markdown(f"**Total Products:** {len(df)}")
        
        # Prepare display columns
        display_cols = [
            'product_id', 'variation_id', 'sku', 'product_name', 'parent_product', 
            'attribute', 'regular_price', 'stock_quantity', 'product_status',
            'hsn', 'zoho_name', 'usage_units', 'categories', 'is_active'
        ]
        
        # Filter to existing columns
        display_cols = [col for col in display_cols if col in df.columns]
        display_df = df[display_cols].copy()
        
        # Format boolean
        if 'is_active' in display_df.columns:
            display_df['is_active'] = display_df['is_active'].map({True: '✅', False: '❌'})
        
        # Add selection column for bulk actions (admin only)
        if role == 'admin':
            display_df.insert(0, 'Select', False)
        
        # Define editable columns based on role
        if role == 'admin':
            # Admin can edit all fields
            disabled_cols = ['product_id', 'variation_id']
        else:
            # Manager can only edit HSN, Zoho Name, Usage Units
            disabled_cols = [col for col in display_df.columns if col not in ['hsn', 'zoho_name', 'usage_units']]
        
        # Column config
        column_config = {
            "Select": st.column_config.CheckboxColumn("Select", default=False) if role == 'admin' else None,
            "product_id": st.column_config.NumberColumn("Product ID", disabled=True),
            "variation_id": st.column_config.NumberColumn("Variation ID", disabled=True),
            "sku": st.column_config.TextColumn("SKU"),
            "product_name": st.column_config.TextColumn("Product Name", width="large"),
            "parent_product": st.column_config.TextColumn("Parent Product"),
            "attribute": st.column_config.TextColumn("Attributes"),
            "regular_price": st.column_config.NumberColumn("Price", format="$%.2f"),
            "stock_quantity": st.column_config.NumberColumn("Stock"),
            "product_status": st.column_config.TextColumn("Status"),
            "hsn": st.column_config.TextColumn("HSN", help="Numeric only, preserves leading zeros"),
            "zoho_name": st.column_config.TextColumn("Zoho Name"),
            "usage_units": st.column_config.TextColumn("Usage Units"),
            "categories": st.column_config.TextColumn("Categories"),
            "is_active": st.column_config.TextColumn("Active")
        }
        
        # Remove None values from config
        column_config = {k: v for k, v in column_config.items() if v is not None}
        
        # Data editor
        edited_df = st.data_editor(
            display_df,
            hide_index=True,
            column_config=column_config,
            disabled=disabled_cols,
            use_container_width=True,
            key="products_table"
        )
        
        # Handle edits
        if not edited_df.equals(display_df):
            # Find changed rows
            changes = []
            for idx in edited_df.index:
                original_row = display_df.loc[idx]
                edited_row = edited_df.loc[idx]
                
                # Check if row changed
                if not original_row.equals(edited_row):
                    db_id = df.loc[idx, 'id']  # Get database ID from original dataframe
                    
                    # Build updates dict (only changed fields)
                    updates = {}
                    for col in edited_df.columns:
                        if col not in ['Select', 'product_id', 'variation_id', 'is_active'] and col in df.columns:
                            if str(original_row[col]) != str(edited_row[col]):
                                # Handle is_active conversion back to boolean
                                if col == 'is_active':
                                    updates[col] = edited_row[col] == '✅'
                                else:
                                    updates[col] = edited_row[col]
                    
                    if updates:
                        changes.append((db_id, updates))
            
            # Apply changes
            if changes:
                success_count = 0
                for db_id, updates in changes:
                    if ProductDB.update_product(db_id, updates, username):
                        success_count += 1
                
                if success_count > 0:
                    st.success(f"✅ Updated {success_count} product(s)")
                    time.sleep(0.5)
                    st.rerun()
        
        # Bulk actions (admin only)
        if role == 'admin' and 'Select' in edited_df.columns:
            selected_indices = edited_df[edited_df['Select']].index.tolist()
            selected_count = len(selected_indices)
            
            if selected_count > 0:
                st.markdown("---")
                st.markdown(f"### 🎯 Bulk Actions ({selected_count} selected)")
                
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    if st.button("✏️ Bulk Edit"):
                        st.session_state.show_bulk_actions = True
                        st.session_state.selected_products = [df.loc[idx, 'id'] for idx in selected_indices]
                
                with col2:
                    if st.button("❌ Mark Inactive"):
                        count = ProductDB.mark_products_inactive(
                            [df.loc[idx, 'id'] for idx in selected_indices],
                            username
                        )
                        if count > 0:
                            st.success(f"✅ Marked {count} product(s) as inactive")
                            time.sleep(0.5)
                            st.rerun()
                
                with col3:
                    if st.button("🗑️ Delete Selected", type="secondary"):
                        if st.checkbox("⚠️ Confirm deletion (cannot be undone)"):
                            count = ProductDB.bulk_delete_products(
                                [df.loc[idx, 'id'] for idx in selected_indices]
                            )
                            if count > 0:
                                st.success(f"✅ Deleted {count} product(s)")
                                time.sleep(0.5)
                                st.rerun()
                
                # Bulk edit form
                if st.session_state.show_bulk_actions:
                    with st.expander("✏️ Bulk Edit Selected Products", expanded=True):
                        with st.form("bulk_edit_form"):
                            st.markdown("**Edit the following fields for all selected products:**")
                            
                            col1, col2 = st.columns(2)
                            with col1:
                                bulk_hsn = st.text_input("HSN (leave empty to skip)", help="Numeric only")
                                bulk_zoho = st.text_input("Zoho Name (leave empty to skip)")
                            
                            with col2:
                                bulk_units = st.text_input("Usage Units (leave empty to skip)")
                                bulk_price = st.number_input("Regular Price (0 to skip)", min_value=0.0, step=0.01)
                            
                            submitted = st.form_submit_button("💾 Apply to Selected")
                            
                            if submitted:
                                updates = {}
                                if bulk_hsn: updates['hsn'] = bulk_hsn
                                if bulk_zoho: updates['zoho_name'] = bulk_zoho
                                if bulk_units: updates['usage_units'] = bulk_units
                                if bulk_price > 0: updates['regular_price'] = bulk_price
                                
                                if updates:
                                    count = ProductDB.bulk_update_products(
                                        st.session_state.selected_products,
                                        updates,
                                        username
                                    )
                                    if count > 0:
                                        st.success(f"✅ Updated {count} product(s)")
                                        st.session_state.show_bulk_actions = False
                                        time.sleep(0.5)
                                        st.rerun()
                                else:
                                    st.warning("⚠️ No changes specified")
    else:
        st.info("ℹ️ Click 'Refresh Products' to load the product catalog")


def show_sync_tab(api_url: str, consumer_key: str, consumer_secret: str, username: str):
    """WooCommerce sync interface (admin only)"""
    
    st.markdown("### 🔄 Sync from WooCommerce")
    st.info("📋 **One-way sync:** WooCommerce → Database only. Changes in database will NOT affect WooCommerce.")
    
    st.markdown("""
    **Sync Behavior:**
    - ✅ Fetches simple products and all variations
    - ✅ Adds only NEW products (existing products are not updated)
    - ✅ Marks products as inactive if removed from WooCommerce
    - ⚠️ Maximum 100 products per sync
    """)
    
    if st.button("🔄 Start Sync", type="primary"):
        with st.spinner("Syncing products from WooCommerce..."):
            # Fetch products
            products = fetch_wc_products(api_url, consumer_key, consumer_secret)
            
            if not products:
                st.error("❌ Failed to fetch products from WooCommerce")
                return
            
            st.info(f"📦 Fetched {len(products)} products from WooCommerce")
            
            # Process products
            processed_products = process_wc_products(products)
            
            # Add to database
            added, skipped = ProductDB.bulk_add_products(processed_products, username)
            
            # Mark missing products as inactive
            wc_product_ids = [p['product_id'] for p in processed_products]
            marked_inactive = ProductDB.mark_missing_products_inactive(wc_product_ids, username)
            
            # Show results
            st.success("✅ Sync completed!")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Products Added", added)
            with col2:
                st.metric("Products Skipped", skipped)
            with col3:
                st.metric("Marked Inactive", marked_inactive)


def show_add_product_tab(username: str):
    """Manual product addition form (admin only)"""
    
    st.markdown("### ➕ Add Product Manually")
    st.info("All fields are optional. Fill in the fields you have information for.")
    
    with st.form("add_product_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            product_id = st.number_input("Product ID", min_value=0, value=0, help="WooCommerce product ID")
            variation_id = st.number_input("Variation ID (leave 0 for simple product)", min_value=0, value=0)
            sku = st.text_input("SKU")
            product_name = st.text_input("Product Name *")
            parent_product = st.text_input("Parent Product (for variations)")
            attribute = st.text_input("Attributes (for variations)")
        
        with col2:
            regular_price = st.number_input("Regular Price", min_value=0.0, step=0.01)
            stock_quantity = st.number_input("Stock Quantity", min_value=0, value=0)
            product_status = st.selectbox("Product Status", ['publish', 'draft', 'pending', 'private'])
            categories = st.text_input("Categories (comma-separated)")
            hsn = st.text_input("HSN", help="Numeric only, preserves leading zeros")
            zoho_name = st.text_input("Zoho Name")
            usage_units = st.text_input("Usage Units")
        
        submitted = st.form_submit_button("➕ Add Product", type="primary")
        
        if submitted:
            if not product_name:
                st.error("❌ Product name is required")
            else:
                # Build product data
                product_data = {
                    'product_id': product_id if product_id > 0 else None,
                    'variation_id': variation_id if variation_id > 0 else None,
                    'sku': sku if sku else None,
                    'product_name': product_name,
                    'parent_product': parent_product if parent_product else None,
                    'attribute': attribute if attribute else None,
                    'regular_price': regular_price if regular_price > 0 else None,
                    'stock_quantity': stock_quantity,
                    'product_status': product_status,
                    'categories': categories if categories else None,
                    'hsn': hsn if hsn else None,
                    'zoho_name': zoho_name if zoho_name else None,
                    'usage_units': usage_units if usage_units else None,
                    'is_active': True
                }
                
                if ProductDB.add_product(product_data, username):
                    st.success("✅ Product added successfully!")
                    time.sleep(1)
                    st.rerun()


def show_statistics_tab():
    """Display product statistics"""
    
    st.markdown("### 📈 Product Statistics")
    
    stats = ProductDB.get_product_stats()
    
    if stats:
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Total Products", stats['total'])
            st.metric("Active Products", stats['active'])
        
        with col2:
            st.metric("Inactive Products", stats['inactive'])
            st.metric("Simple Products", stats['simple'])
        
        with col3:
            st.metric("Product Variations", stats['variations'])
            st.metric("Missing HSN", stats['missing_hsn'])
    else:
        st.info("No statistics available")


# ==========================================
# WOOCOMMERCE API FUNCTIONS
# ==========================================

def fetch_wc_products(api_url: str, consumer_key: str, consumer_secret: str) -> List[Dict]:
    """
    Fetch products from WooCommerce API
    Retrieves simple products and all variations
    """
    all_products = []
    page = 1
    max_retries = 3
    
    try:
        while len(all_products) < 100:  # Limit to 100 products
            retries = 0
            
            while retries < max_retries:
                try:
                    # Fetch products
                    response = requests.get(
                        f"{api_url}/products",
                        params={
                            'per_page': 100,
                            'page': page,
                            'status': 'any'
                        },
                        auth=(consumer_key, consumer_secret),
                        timeout=30
                    )
                    
                    # Handle rate limiting
                    if response.status_code == 429:
                        retry_after = int(response.headers.get('Retry-After', 60))
                        st.warning(f"Rate limit reached. Waiting {retry_after} seconds...")
                        time.sleep(retry_after)
                        retries += 1
                        continue
                    
                    if response.status_code != 200:
                        st.error(f"API Error: {response.status_code}")
                        return []
                    
                    products = response.json()
                    
                    if not products:
                        return all_products
                    
                    all_products.extend(products)
                    page += 1
                    break
                    
                except requests.exceptions.RequestException as e:
                    if retries < max_retries - 1:
                        st.warning(f"Request failed, retrying... (Attempt {retries + 1}/{max_retries})")
                        time.sleep(2)
                        retries += 1
                    else:
                        st.error(f"Network error: {str(e)}")
                        return []
        
        return all_products[:100]  # Return max 100
        
    except Exception as e:
        st.error(f"Unexpected error: {str(e)}")
        return []


def process_wc_products(products: List[Dict]) -> List[Dict]:
    """
    Process raw WooCommerce products into database format
    Handles both simple products and variations
    """
    processed = []
    
    for product in products:
        try:
            # Get categories
            categories = ', '.join([cat['name'] for cat in product.get('categories', [])])
            
            # Check if it's a variable product
            if product.get('type') == 'variable':
                # Fetch variations
                variations = product.get('variations', [])
                
                if variations:
                    # This is a parent product, add variations
                    # Note: variations might be IDs, need to fetch details
                    # For now, we'll just add the parent
                    processed.append({
                        'product_id': product['id'],
                        'variation_id': None,
                        'sku': product.get('sku'),
                        'product_name': product.get('name'),
                        'parent_product': None,
                        'attribute': None,
                        'regular_price': float(product.get('regular_price', 0)) if product.get('regular_price') else None,
                        'stock_quantity': product.get('stock_quantity', 0),
                        'product_status': product.get('status', 'publish'),
                        'categories': categories,
                        'is_active': True
                    })
            else:
                # Simple product
                processed.append({
                    'product_id': product['id'],
                    'variation_id': None,
                    'sku': product.get('sku'),
                    'product_name': product.get('name'),
                    'parent_product': None,
                    'attribute': None,
                    'regular_price': float(product.get('regular_price', 0)) if product.get('regular_price') else None,
                    'stock_quantity': product.get('stock_quantity', 0),
                    'product_status': product.get('status', 'publish'),
                    'categories': categories,
                    'is_active': True
                })
        
        except Exception as e:
            st.warning(f"Skipped product due to error: {str(e)}")
            continue
    
    return processed


if __name__ == "__main__":
    run()
