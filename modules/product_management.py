"""
Product Management Module
Manage WooCommerce products with sync, search, filter, and edit operations

Access Control:
- Admin: Full access (sync, add, edit all fields, delete)
- User: View + edit HSN/Zoho/Units only (Manager treated as User)
"""

import streamlit as st
import pandas as pd
import requests
from datetime import datetime
from typing import List, Dict, Optional
import time

# Import from your app structure
from auth.session import SessionManager
from config.database import ActivityLogger

# Import product database helper
# Place db_products.py in the root directory with app.py
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from db_products import ProductDB
except ImportError:
    try:
        # Try alternate path
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from db_products import ProductDB
    except ImportError:
        st.error("⚠️ Cannot import ProductDB. Make sure db_products.py is in root folder or same folder as app.py")
        st.stop()


def show():
    """Main entry point for the Product Management module"""
    
    # Check module access using require_module_access
    SessionManager.require_module_access('product_management')
    
    # Get user info
    user = SessionManager.get_user()
    profile = SessionManager.get_user_profile()
    is_admin = SessionManager.is_admin()
    username = profile.get('full_name', user.get('email', 'Unknown'))
    role_name = profile.get('role_name', 'User')
    
    # Module header
    st.title("📦 Product Management")
    st.caption(f"👤 {username} | Role: {role_name}")
    st.markdown("---")
    
    # Initialize session state
    if 'pm_products_df' not in st.session_state:
        st.session_state.pm_products_df = None
    if 'pm_refresh_trigger' not in st.session_state:
        st.session_state.pm_refresh_trigger = 0
    
    # Create tabs based on user role
    if is_admin:
        tabs = st.tabs(["📊 Products", "🔄 Sync from WooCommerce", "➕ Add Product", "📈 Statistics"])
        
        with tabs[0]:
            show_products_tab(username, is_admin)
        
        with tabs[1]:
            show_sync_tab(username)
        
        with tabs[2]:
            show_add_product_tab(username)
        
        with tabs[3]:
            show_statistics_tab()
    else:
        # Regular users only see products tab
        st.info("ℹ️ You have view and limited edit access. Contact admin for full access.")
        show_products_tab(username, is_admin)


def show_products_tab(username: str, is_admin: bool):
    """Display products with search, filter, and edit capabilities"""
    
    st.markdown("### 📊 Product Database")
    
    # Controls row
    col1, col2, col3, col4 = st.columns([2, 2, 1, 1])
    
    with col1:
        search_term = st.text_input("🔍 Search products", placeholder="Search by name...", key="pm_search")
    
    with col2:
        filter_active = st.selectbox(
            "Filter",
            ["Active only", "Inactive only", "All products"],
            key="pm_filter"
        )
    
    with col3:
        filter_type = st.selectbox(
            "Type",
            ["All", "Simple", "Variations"],
            key="pm_type"
        )
    
    with col4:
        if st.button("🔄 Refresh", use_container_width=True):
            st.session_state.pm_refresh_trigger += 1
            st.rerun()
    
    # Load products
    with st.spinner("Loading products..."):
        if search_term:
            products = ProductDB.search_products(search_term, active_only=(filter_active == "Active only"))
        else:
            active_only = filter_active == "Active only"
            products = ProductDB.get_all_products(active_only=active_only)
        
        # Apply inactive filter if needed
        if filter_active == "Inactive only":
            products = [p for p in products if not p.get('is_active', True)]
        
        # Apply type filter
        if filter_type == "Simple":
            products = [p for p in products if p.get('variation_id') is None]
        elif filter_type == "Variations":
            products = [p for p in products if p.get('variation_id') is not None]
    
    if not products:
        st.info("No products found. Try adjusting your search or filters.")
        return
    
    st.success(f"✅ Found {len(products)} products")
    
    # Convert to DataFrame for display
    df = pd.DataFrame(products)
    
    # Select and reorder columns for display
    display_cols = [
        'id', 'product_id', 'variation_id', 'product_name', 
        'parent_product', 'sku', 'stock_quantity', 'regular_price', 'sale_price',
        'hsn', 'zoho_name', 'categories', 'attribute', 'is_active', 'notes'
    ]
    
    # Only include columns that exist
    display_cols = [col for col in display_cols if col in df.columns]
    display_df = df[display_cols].copy()
    
    # Configure editable columns based on role
    if is_admin:
        # Admin can edit all fields except id, product_id, variation_id
        column_config = {
            "id": st.column_config.NumberColumn("DB ID", disabled=True),
            "product_id": st.column_config.NumberColumn("Product ID", disabled=True),
            "variation_id": st.column_config.NumberColumn("Variation ID", disabled=True),
            "product_name": st.column_config.TextColumn("Product Name", width="large"),
            "parent_product": st.column_config.TextColumn("Parent Name"),
            "sku": st.column_config.TextColumn("SKU"),
            "stock_quantity": st.column_config.NumberColumn("Stock"),
            "regular_price": st.column_config.NumberColumn("Regular Price", format="$%.2f"),
            "sale_price": st.column_config.NumberColumn("Sale Price", format="$%.2f"),
            "hsn": st.column_config.TextColumn("HSN", help="Numeric only"),
            "zoho_name": st.column_config.TextColumn("Zoho Name"),
            "categories": st.column_config.TextColumn("Categories"),
            "attribute": st.column_config.TextColumn("Attributes"),
            "is_active": st.column_config.CheckboxColumn("Active"),
            "notes": st.column_config.TextColumn("Notes", width="medium")
        }
    else:
        # Regular users can only edit HSN, Zoho Name, Usage Units, Notes
        column_config = {
            "id": st.column_config.NumberColumn("DB ID", disabled=True),
            "product_id": st.column_config.NumberColumn("Product ID", disabled=True),
            "variation_id": st.column_config.NumberColumn("Variation ID", disabled=True),
            "product_name": st.column_config.TextColumn("Product Name", width="large", disabled=True),
            "parent_product": st.column_config.TextColumn("Parent Name", disabled=True),
            "sku": st.column_config.TextColumn("SKU", disabled=True),
            "stock_quantity": st.column_config.NumberColumn("Stock", disabled=True),
            "regular_price": st.column_config.NumberColumn("Regular Price", format="$%.2f", disabled=True),
            "sale_price": st.column_config.NumberColumn("Sale Price", format="$%.2f", disabled=True),
            "hsn": st.column_config.TextColumn("HSN", help="Numeric only"),
            "zoho_name": st.column_config.TextColumn("Zoho Name"),
            "categories": st.column_config.TextColumn("Categories", disabled=True),
            "attribute": st.column_config.TextColumn("Attributes", disabled=True),
            "is_active": st.column_config.CheckboxColumn("Active", disabled=True),
            "notes": st.column_config.TextColumn("Notes", width="medium")
        }
    
    # Display editable data table
    edited_df = st.data_editor(
        display_df,
        column_config=column_config,
        use_container_width=True,
        num_rows="fixed",
        hide_index=True,
        key=f"pm_editor_{st.session_state.pm_refresh_trigger}"
    )
    
    # Save changes button
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        if st.button("💾 Save Changes", type="primary", use_container_width=True):
            save_product_changes(display_df, edited_df, username, is_admin)
    
    with col2:
        # Export to Excel
        if st.button("📥 Export to Excel", use_container_width=True):
            export_to_excel(display_df)
    
    with col3:
        # Delete selected (admin only)
        if is_admin:
            if st.button("🗑️ Delete Selected", use_container_width=True):
                st.warning("⚠️ Delete functionality: Select rows and implement delete logic here")


def save_product_changes(original_df: pd.DataFrame, edited_df: pd.DataFrame, username: str, is_admin: bool):
    """Save changes made to the products"""
    
    # Find changed rows
    changes = []
    
    for idx in range(len(original_df)):
        original_row = original_df.iloc[idx]
        edited_row = edited_df.iloc[idx]
        
        # Check if any fields changed
        row_changes = {}
        
        if is_admin:
            # Admin can edit most fields
            editable_fields = ['sku', 'product_name', 'parent_product', 'attribute', 
                             'regular_price', 'sale_price', 'stock_quantity', 'product_status',
                             'hsn', 'zoho_name', 'usage_units', 'categories', 'is_active', 'notes']
        else:
            # Regular users can only edit these fields
            editable_fields = ['hsn', 'zoho_name', 'usage_units', 'notes']
        
        for field in editable_fields:
            if field in original_row and field in edited_row:
                if original_row[field] != edited_row[field]:
                    row_changes[field] = edited_row[field]
        
        if row_changes:
            db_id = int(edited_row['id'])
            changes.append((db_id, row_changes))
    
    if not changes:
        st.info("ℹ️ No changes detected")
        return
    
    # Save changes
    with st.spinner(f"Saving {len(changes)} changes..."):
        success_count, failure_count = ProductDB.bulk_update_products(changes, username)
    
    if success_count > 0:
        st.success(f"✅ Successfully updated {success_count} products")
        
        # Log activity
        ActivityLogger.log(
            user_id=st.session_state.user['id'],
            action_type='bulk_update',
            module_key='product_management',
            description=f"Updated {success_count} products",
            metadata={'count': success_count}
        )
        
        # Refresh the display
        time.sleep(0.5)
        st.session_state.pm_refresh_trigger += 1
        st.rerun()
    
    if failure_count > 0:
        st.error(f"❌ Failed to update {failure_count} products")


def export_to_excel(df: pd.DataFrame):
    """Export dataframe to Excel"""
    from io import BytesIO
    
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Products')
    
    output.seek(0)
    
    st.download_button(
        label="📥 Download Excel",
        data=output,
        file_name=f"products_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


def show_sync_tab(username: str):
    """WooCommerce sync functionality (Admin only)"""
    
    st.markdown("### 🔄 Sync Products from WooCommerce")
    
    st.info("""
    **How Sync Works:**
    - Fetches products from WooCommerce API
    - Only ADDS new products (doesn't update existing ones)
    - Maximum 100 products per sync
    - Includes simple products and variations
    """)
    
    # Check for WooCommerce credentials
    try:
        wc_api_url = st.secrets["woocommerce"]["api_url"]
        wc_consumer_key = st.secrets["woocommerce"]["consumer_key"]
        wc_consumer_secret = st.secrets["woocommerce"]["consumer_secret"]
    except KeyError:
        st.error("⚠️ WooCommerce API credentials not configured in secrets!")
        st.code("""
[woocommerce]
api_url = "https://your-site.com/wp-json/wc/v3"
consumer_key = "ck_xxxxx"
consumer_secret = "cs_xxxxx"
        """)
        return
    
    col1, col2 = st.columns(2)
    
    with col1:
        sync_limit = st.number_input("Products to fetch", min_value=1, max_value=100, value=100)
    
    with col2:
        st.metric("Max per sync", "100", help="WooCommerce API limit")
    
    if st.button("🚀 Start Sync", type="primary", use_container_width=True):
        sync_from_woocommerce(wc_api_url, wc_consumer_key, wc_consumer_secret, sync_limit, username)


def sync_from_woocommerce(api_url: str, consumer_key: str, consumer_secret: str, limit: int, username: str):
    """Fetch and sync products from WooCommerce"""
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    try:
        status_text.text("🔄 Fetching products from WooCommerce...")
        progress_bar.progress(20)
        
        # Fetch simple products
        simple_products = fetch_wc_products(api_url, consumer_key, consumer_secret, limit)
        
        progress_bar.progress(50)
        status_text.text(f"✅ Fetched {len(simple_products)} products")
        
        # Fetch variations for variable products
        all_products = []
        variation_count = 0
        
        for product in simple_products:
            all_products.append(product)
            
            # If it's a variable product, fetch its variations
            if product.get('type') == 'variable':
                variations = fetch_wc_variations(
                    api_url, consumer_key, consumer_secret, product['id']
                )
                
                for variation in variations:
                    variation['parent_name'] = product['name']
                    variation['variation_id'] = variation['id']
                    variation['id'] = product['id']  # Keep parent ID
                    all_products.append(variation)
                    variation_count += 1
        
        progress_bar.progress(70)
        status_text.text(f"✅ Found {variation_count} variations")
        
        # Sync to database
        status_text.text("💾 Saving to database...")
        added, skipped, errors = ProductDB.sync_from_woocommerce(all_products, username)
        
        progress_bar.progress(100)
        
        # Show results
        col1, col2, col3 = st.columns(3)
        col1.metric("✅ Added", added)
        col2.metric("⏭️ Skipped", skipped, help="Already in database")
        col3.metric("❌ Errors", errors)
        
        if added > 0:
            st.success(f"🎉 Successfully synced {added} new products!")
            
            # Log activity
            ActivityLogger.log(
                user_id=st.session_state.user['id'],
                action_type='sync',
                module_key='product_management',
                description=f"Synced {added} products from WooCommerce",
                metadata={'added': added, 'skipped': skipped, 'errors': errors}
            )
        else:
            st.info("ℹ️ No new products to add. All products already in database.")
        
    except Exception as e:
        st.error(f"❌ Sync failed: {str(e)}")
    finally:
        progress_bar.empty()
        status_text.empty()


def fetch_wc_products(api_url: str, consumer_key: str, consumer_secret: str, limit: int) -> List[Dict]:
    """Fetch products from WooCommerce API"""
    
    try:
        response = requests.get(
            f"{api_url}/products",
            auth=(consumer_key, consumer_secret),
            params={'per_page': limit, 'status': 'publish'},
            timeout=30
        )
        
        response.raise_for_status()
        products = response.json()
        
        # Parse products
        parsed_products = []
        for product in products:
            parsed = {
                'id': product['id'],
                'name': product['name'],
                'sku': product.get('sku', ''),
                'type': product.get('type', 'simple'),
                'regular_price': float(product.get('regular_price', 0) or 0),
                'sale_price': float(product.get('sale_price', 0) or 0),
                'stock_quantity': product.get('stock_quantity', 0),
                'status': product.get('status', 'publish'),
                'categories': ', '.join([cat['name'] for cat in product.get('categories', [])]),
                'variation_id': None
            }
            parsed_products.append(parsed)
        
        return parsed_products
        
    except Exception as e:
        st.error(f"Error fetching products: {str(e)}")
        return []


def fetch_wc_variations(api_url: str, consumer_key: str, consumer_secret: str, product_id: int) -> List[Dict]:
    """Fetch variations for a variable product"""
    
    try:
        response = requests.get(
            f"{api_url}/products/{product_id}/variations",
            auth=(consumer_key, consumer_secret),
            params={'per_page': 100},
            timeout=30
        )
        
        response.raise_for_status()
        variations = response.json()
        
        # Parse variations
        parsed_variations = []
        for variation in variations:
            # Format attributes
            attrs = ', '.join([f"{attr['name']}: {attr['option']}" for attr in variation.get('attributes', [])])
            
            parsed = {
                'id': variation['id'],
                'name': variation.get('name', ''),
                'sku': variation.get('sku', ''),
                'type': 'variation',
                'regular_price': float(variation.get('regular_price', 0) or 0),
                'sale_price': float(variation.get('sale_price', 0) or 0),
                'stock_quantity': variation.get('stock_quantity', 0),
                'status': variation.get('status', 'publish'),
                'attributes': attrs,
                'categories': ''
            }
            parsed_variations.append(parsed)
        
        return parsed_variations
        
    except Exception as e:
        st.warning(f"Error fetching variations for product {product_id}: {str(e)}")
        return []


def show_add_product_tab(username: str):
    """Manual product addition (Admin only)"""
    
    st.markdown("### ➕ Add Product Manually")
    
    st.info("Add a product that's not synced from WooCommerce, or create a custom entry.")
    
    with st.form("add_product_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            product_id = st.number_input("Product ID", min_value=0, help="WooCommerce product ID or 0 for custom")
            variation_id = st.number_input("Variation ID", min_value=0, help="0 for simple products")
            sku = st.text_input("SKU")
            product_name = st.text_input("Product Name *", help="Required")
            parent_product = st.text_input("Parent Product")
            attribute = st.text_input("Attributes")
            regular_price = st.number_input("Regular Price", min_value=0.0, step=0.01)
            sale_price = st.number_input("Sale Price", min_value=0.0, step=0.01)
        
        with col2:
            stock_quantity = st.number_input("Stock Quantity", min_value=0)
            product_status = st.selectbox("Status", ["publish", "draft", "private"])
            hsn = st.text_input("HSN", help="Numeric only")
            zoho_name = st.text_input("Zoho Name")
            usage_units = st.text_input("Usage Units")
            categories = st.text_input("Categories", help="Comma-separated")
        
        notes = st.text_area("Notes")
        
        submitted = st.form_submit_button("➕ Add Product", type="primary", use_container_width=True)
        
        if submitted:
            if not product_name:
                st.error("❌ Product name is required")
            else:
                product_data = {
                    'product_id': int(product_id) if product_id else 0,
                    'variation_id': int(variation_id) if variation_id else None,
                    'sku': sku,
                    'product_name': product_name,
                    'parent_product': parent_product,
                    'attribute': attribute,
                    'regular_price': float(regular_price),
                    'sale_price': float(sale_price),
                    'stock_quantity': int(stock_quantity),
                    'product_status': product_status,
                    'hsn': hsn,
                    'zoho_name': zoho_name,
                    'usage_units': usage_units,
                    'categories': categories,
                    'notes': notes,
                    'is_active': True
                }
                
                if ProductDB.add_product(product_data, username):
                    st.success("✅ Product added successfully!")
                    
                    # Log activity
                    ActivityLogger.log(
                        user_id=st.session_state.user['id'],
                        action_type='add_product',
                        module_key='product_management',
                        description=f"Added product: {product_name}",
                        metadata={'product_name': product_name}
                    )
                    
                    time.sleep(1)
                    st.rerun()


def show_statistics_tab():
    """Show product statistics (Admin only)"""
    
    st.markdown("### 📈 Product Statistics")
    
    stats = ProductDB.get_product_stats()
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    col1.metric("📦 Total Products", stats['total'])
    col2.metric("✅ Active", stats['active'])
    col3.metric("❌ Inactive", stats['inactive'])
    col4.metric("📝 Simple Products", stats['simple'])
    col5.metric("🔀 Variations", stats['variations'])
    
    st.markdown("---")
    
    # Additional stats can be added here
    st.info("💡 More detailed analytics coming soon...")
