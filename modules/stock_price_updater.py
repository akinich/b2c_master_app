"""
Stock & Price Updater Module
Update WooCommerce product prices and stock with list management

Access Control:
- Admin: Full access (manage lists, update products, sync)
- Manager/User: Update products in updatable list only
"""

import streamlit as st
import pandas as pd
import requests
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import uuid
from io import BytesIO
import time

# Import from your app structure
from auth.session import SessionManager
from config.database import ActivityLogger, Database

# Import product database helper
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from db_products import ProductDB
except ImportError:
    try:
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from db_products import ProductDB
    except ImportError:
        st.error("⚠️ Cannot import ProductDB. Make sure db_products.py is in root folder")
        st.stop()


def show():
    """Main entry point for Stock & Price Updater module"""
    
    # Authentication
    SessionManager.require_module_access('stock_price_updater')
    
    # Get user info
    user = SessionManager.get_user()
    profile = SessionManager.get_user_profile()
    is_admin = SessionManager.is_admin()
    username = profile.get('full_name', user.get('email', 'Unknown'))
    role_name = profile.get('role_name', 'User')
    
    # Module header
    st.title("💰 Stock & Price Updater")
    st.caption(f"👤 {username} | Role: {role_name}")
    st.markdown("---")
    
    # Initialize session state
    init_session_state()
    
    # Create tabs based on user role
    if is_admin:
        tabs = st.tabs(["📊 Update Products", "⚙️ Manage Lists", "📈 Statistics"])
        
        with tabs[0]:
            show_update_tab(username, is_admin)
        
        with tabs[1]:
            show_manage_lists_tab(username)
        
        with tabs[2]:
            show_statistics_tab()
    else:
        # Regular users only see update tab
        st.info("ℹ️ You can update prices and stock for products in the updatable list.")
        show_update_tab(username, is_admin)


def init_session_state():
    """Initialize session state variables"""
    if 'spu_updatable_df' not in st.session_state:
        st.session_state.spu_updatable_df = None
    if 'spu_non_updatable_df' not in st.session_state:
        st.session_state.spu_non_updatable_df = None
    if 'spu_deleted_df' not in st.session_state:
        st.session_state.spu_deleted_df = None
    if 'spu_preview_changes' not in st.session_state:
        st.session_state.spu_preview_changes = None
    if 'spu_refresh_trigger' not in st.session_state:
        st.session_state.spu_refresh_trigger = 0


# ==========================================
# TAB 1: UPDATE PRODUCTS
# ==========================================

def show_update_tab(username: str, is_admin: bool):
    """Display the update products interface with 3 tables"""
    
    st.markdown("### 📊 Update Products")
    
    # Action buttons row
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("🔄 Refresh Data", use_container_width=True):
            load_all_product_data()
            st.success("✅ Data refreshed!")
    
    with col2:
        if st.button("🔄 Sync from WooCommerce", use_container_width=True):
            sync_from_woocommerce(username)
    
    with col3:
        # Download Excel template
        if st.download_button(
            label="📥 Download Template",
            data=generate_excel_template(),
            file_name=f"stock_price_template_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        ):
            st.success("✅ Template downloaded!")
    
    with col4:
        # Upload Excel file
        uploaded_file = st.file_uploader(
            "📤 Upload Excel",
            type=['xlsx'],
            key='spu_excel_upload',
            label_visibility="collapsed"
        )
    
    # Handle Excel upload
    if uploaded_file:
        handle_excel_upload(uploaded_file, username)
    
    st.markdown("---")
    
    # Load data if not already loaded
    if st.session_state.spu_updatable_df is None:
        load_all_product_data()
    
    # TABLE 1: UPDATABLE LIST (Always Expanded)
    st.markdown("#### ✅ Updatable Products")
    show_updatable_table(username, is_admin)
    
    st.markdown("---")
    
    # TABLE 2: NON-UPDATABLE LIST (Collapsible)
    with st.expander("🔒 Non-Updatable Products (View Only)", expanded=False):
        show_non_updatable_table()
    
    # TABLE 3: DELETED ITEMS LIST (Collapsible)
    with st.expander("🗑️ Deleted Items (Removed from WooCommerce)", expanded=False):
        show_deleted_table()


def load_all_product_data():
    """Load products from database and categorize into 3 lists"""
    
    with st.spinner("Loading products..."):
        # Get all products from woocommerce_products
        all_products = ProductDB.get_all_products(active_only=False)
        
        if not all_products:
            st.warning("No products found. Please sync from WooCommerce first.")
            return
        
        # Get update settings
        settings = StockPriceDB.get_all_settings()
        
        # Create a mapping for quick lookup
        settings_map = {}
        for setting in settings:
            key = (setting['product_id'], setting.get('variation_id'))
            settings_map[key] = setting
        
        # Categorize products
        updatable = []
        non_updatable = []
        deleted = []
        
        for product in all_products:
            key = (product['product_id'], product.get('variation_id'))
            setting = settings_map.get(key, {'is_updatable': True, 'is_deleted': False})
            
            # Add setting flags to product
            product['is_updatable'] = setting.get('is_updatable', True)
            product['is_deleted'] = setting.get('is_deleted', False)
            product['setting_notes'] = setting.get('notes', '')
            
            # Categorize
            if product['is_deleted']:
                deleted.append(product)
            elif product['is_updatable']:
                updatable.append(product)
            else:
                non_updatable.append(product)
        
        # Convert to DataFrames
        st.session_state.spu_updatable_df = prepare_display_df(updatable, editable=True)
        st.session_state.spu_non_updatable_df = prepare_display_df(non_updatable, editable=False)
        st.session_state.spu_deleted_df = prepare_display_df(deleted, editable=False)


def prepare_display_df(products: List[Dict], editable: bool) -> pd.DataFrame:
    """Prepare DataFrame for display"""
    
    if not products:
        return pd.DataFrame()
    
    df = pd.DataFrame(products)
    
    # Select and order columns
    display_cols = [
        'id', 'product_id', 'variation_id', 'product_name', 'parent_product',
        'sku', 'stock_quantity', 'regular_price', 'sale_price'
    ]
    
    # Add editable columns if applicable
    if editable:
        display_cols.extend(['updated_stock', 'updated_regular_price', 'updated_sale_price'])
        df['updated_stock'] = None
        df['updated_regular_price'] = None
        df['updated_sale_price'] = None
    
    # Only include columns that exist
    display_cols = [col for col in display_cols if col in df.columns]
    result_df = df[display_cols].copy()
    
    # Format columns
    result_df['stock_quantity'] = result_df['stock_quantity'].fillna(0).astype(int)
    result_df['regular_price'] = result_df['regular_price'].fillna(0.0)
    result_df['sale_price'] = result_df['sale_price'].fillna(0.0)
    
    return result_df


def show_updatable_table(username: str, is_admin: bool):
    """Display updatable products table with edit capabilities"""
    
    df = st.session_state.spu_updatable_df
    
    if df is None or df.empty:
        st.info("No updatable products found.")
        return
    
    st.success(f"✅ {len(df)} products available for updates")
    
    # Configure columns
    column_config = {
        "id": st.column_config.NumberColumn("DB ID", disabled=True, width="small"),
        "product_id": st.column_config.NumberColumn("Product ID", disabled=True, width="small"),
        "variation_id": st.column_config.NumberColumn("Variation ID", disabled=True, width="small"),
        "product_name": st.column_config.TextColumn("Product Name", disabled=True, width="large"),
        "parent_product": st.column_config.TextColumn("Parent", disabled=True, width="medium"),
        "sku": st.column_config.TextColumn("SKU", disabled=True, width="small"),
        "stock_quantity": st.column_config.NumberColumn("Current Stock", disabled=True, width="small"),
        "regular_price": st.column_config.NumberColumn("Current Regular Price", disabled=True, format="Rs. %.2f", width="small"),
        "sale_price": st.column_config.NumberColumn("Current Sale Price", disabled=True, format="Rs. %.2f", width="small"),
        "updated_stock": st.column_config.NumberColumn("New Stock", help="Leave blank to skip", width="small"),
        "updated_regular_price": st.column_config.NumberColumn("New Regular Price", help="Leave blank to skip", format="Rs. %.2f", width="small"),
        "updated_sale_price": st.column_config.NumberColumn("New Sale Price", help="Leave blank to skip", format="Rs. %.2f", width="small"),
    }
    
    # Display editable table
    edited_df = st.data_editor(
        df,
        column_config=column_config,
        use_container_width=True,
        num_rows="fixed",
        hide_index=True,
        key=f"spu_updatable_editor_{st.session_state.spu_refresh_trigger}"
    )
    
    # Action buttons
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("👁️ Preview Changes", type="secondary", use_container_width=True):
            preview_changes(edited_df, username)
    
    with col2:
        if st.button("💾 Update Products", type="primary", use_container_width=True, disabled=(st.session_state.spu_preview_changes is None)):
            apply_updates(username)
    
    with col3:
        if st.button("🔄 Clear Changes", use_container_width=True):
            st.session_state.spu_preview_changes = None
            st.rerun()
    
    # Show preview if available
    if st.session_state.spu_preview_changes:
        show_preview_table()


def show_non_updatable_table():
    """Display non-updatable products (read-only)"""
    
    df = st.session_state.spu_non_updatable_df
    
    if df is None or df.empty:
        st.info("No non-updatable products.")
        return
    
    st.info(f"📋 {len(df)} products in non-updatable list")
    
    # Display read-only table
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True
    )


def show_deleted_table():
    """Display deleted items (read-only)"""
    
    df = st.session_state.spu_deleted_df
    
    if df is None or df.empty:
        st.info("No deleted items.")
        return
    
    st.warning(f"⚠️ {len(df)} products deleted from WooCommerce")
    
    # Display read-only table
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True
    )


def preview_changes(edited_df: pd.DataFrame, username: str):
    """Preview changes before applying"""
    
    changes = []
    validation_errors = []
    
    for idx, row in edited_df.iterrows():
        change_item = {
            'db_id': int(row['id']),
            'product_id': int(row['product_id']),
            'variation_id': int(row['variation_id']) if pd.notna(row['variation_id']) else None,
            'product_name': row['product_name'],
            'sku': row['sku'],
            'changes': {}
        }
        
        # Check stock change
        if pd.notna(row['updated_stock']):
            new_stock = int(row['updated_stock'])
            
            # Validation: No negative stock
            if new_stock < 0:
                validation_errors.append(f"❌ {row['product_name']}: Stock cannot be negative")
                continue
            
            if new_stock != row['stock_quantity']:
                change_item['changes']['stock_quantity'] = {
                    'old': int(row['stock_quantity']),
                    'new': new_stock
                }
        
        # Check regular price change
        if pd.notna(row['updated_regular_price']):
            new_regular = float(row['updated_regular_price'])
            
            # Validation: Price must be positive
            if new_regular < 0:
                validation_errors.append(f"❌ {row['product_name']}: Price cannot be negative")
                continue
            
            if new_regular != row['regular_price']:
                change_item['changes']['regular_price'] = {
                    'old': float(row['regular_price']),
                    'new': new_regular
                }
        
        # Check sale price change
        if pd.notna(row['updated_sale_price']):
            new_sale = float(row['updated_sale_price'])
            
            # Validation: Sale price cannot be negative
            if new_sale < 0:
                validation_errors.append(f"❌ {row['product_name']}: Sale price cannot be negative")
                continue
            
            # Validation: Sale price cannot be higher than regular price
            regular_price = row['updated_regular_price'] if pd.notna(row['updated_regular_price']) else row['regular_price']
            if new_sale > regular_price:
                validation_errors.append(f"⚠️ {row['product_name']}: Sale price (Rs. {new_sale:.2f}) is higher than regular price (Rs. {regular_price:.2f})")
                continue
            
            if new_sale != row['sale_price']:
                change_item['changes']['sale_price'] = {
                    'old': float(row['sale_price']),
                    'new': new_sale
                }
        
        # Only add if there are actual changes
        if change_item['changes']:
            changes.append(change_item)
    
    # Show validation errors
    if validation_errors:
        st.error("**Validation Errors:**")
        for error in validation_errors:
            st.error(error)
    
    # Store changes in session state
    if changes:
        st.session_state.spu_preview_changes = changes
        st.success(f"✅ Found {len(changes)} products with valid changes")
    else:
        st.info("ℹ️ No changes detected")
        st.session_state.spu_preview_changes = None


def show_preview_table():
    """Display preview of changes"""
    
    changes = st.session_state.spu_preview_changes
    
    if not changes:
        return
    
    st.markdown("---")
    st.markdown("#### 👁️ Preview Changes")
    st.info(f"📋 {len(changes)} products will be updated")
    
    # Prepare preview DataFrame
    preview_data = []
    
    for item in changes:
        changes_dict = item['changes']
        change_summary = []
        
        if 'stock_quantity' in changes_dict:
            change_summary.append(f"Stock: {changes_dict['stock_quantity']['old']} → {changes_dict['stock_quantity']['new']}")
        
        if 'regular_price' in changes_dict:
            change_summary.append(f"Regular: Rs. {changes_dict['regular_price']['old']:.2f} → Rs. {changes_dict['regular_price']['new']:.2f}")
        
        if 'sale_price' in changes_dict:
            change_summary.append(f"Sale: Rs. {changes_dict['sale_price']['old']:.2f} → Rs. {changes_dict['sale_price']['new']:.2f}")
        
        preview_data.append({
            'Product Name': item['product_name'],
            'SKU': item['sku'],
            'Changes': ' | '.join(change_summary)
        })
    
    preview_df = pd.DataFrame(preview_data)
    st.dataframe(preview_df, use_container_width=True, hide_index=True)


def apply_updates(username: str):
    """Apply the previewed changes to database and WooCommerce"""
    
    changes = st.session_state.spu_preview_changes
    
    if not changes:
        st.error("No changes to apply. Please preview changes first.")
        return
    
    # Generate batch ID for grouping
    batch_id = str(uuid.uuid4())
    
    # Get WooCommerce credentials
    try:
        wc_api_url = st.secrets["woocommerce"]["api_url"]
        wc_consumer_key = st.secrets["woocommerce"]["consumer_key"]
        wc_consumer_secret = st.secrets["woocommerce"]["consumer_secret"]
    except KeyError:
        st.error("⚠️ WooCommerce API credentials not configured!")
        return
    
    # Progress tracking
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    success_count = 0
    failure_count = 0
    failed_items = []
    
    total = len(changes)
    
    for idx, item in enumerate(changes):
        try:
            status_text.text(f"Updating {idx + 1}/{total}: {item['product_name']}")
            
            # Update database first
            db_updates = {}
            for field, change in item['changes'].items():
                db_updates[field] = change['new']
            
            if ProductDB.update_product(item['db_id'], db_updates, username):
                # Log each change in history
                for field, change in item['changes'].items():
                    StockPriceDB.log_change(
                        product_id=item['product_id'],
                        variation_id=item['variation_id'],
                        field=field,
                        old_value=str(change['old']),
                        new_value=str(change['new']),
                        changed_by=username,
                        batch_id=batch_id,
                        source='manual'
                    )
                
                # Update WooCommerce
                wc_success, wc_error = update_woocommerce_product(
                    wc_api_url, wc_consumer_key, wc_consumer_secret,
                    item['product_id'], item['variation_id'], db_updates
                )
                
                if wc_success:
                    # Mark as synced
                    StockPriceDB.mark_changes_synced(batch_id, item['product_id'], item['variation_id'], True)
                    success_count += 1
                else:
                    # Mark as failed
                    StockPriceDB.mark_changes_synced(batch_id, item['product_id'], item['variation_id'], False, wc_error)
                    failed_items.append(f"{item['product_name']}: {wc_error}")
                    failure_count += 1
            else:
                failed_items.append(f"{item['product_name']}: Database update failed")
                failure_count += 1
        
        except Exception as e:
            failed_items.append(f"{item['product_name']}: {str(e)}")
            failure_count += 1
        
        # Update progress
        progress_bar.progress((idx + 1) / total)
    
    # Clear progress indicators
    progress_bar.empty()
    status_text.empty()
    
    # Show results
    st.markdown("---")
    st.markdown("#### 📊 Update Results")
    
    col1, col2 = st.columns(2)
    col1.metric("✅ Successfully Updated", success_count)
    col2.metric("❌ Failed", failure_count)
    
    if success_count > 0:
        st.success(f"🎉 Successfully updated {success_count} products!")
        
        # Log activity
        ActivityLogger.log(
            user_id=st.session_state.user['id'],
            action_type='bulk_update',
            module_key='stock_price_updater',
            description=f"Updated {success_count} products",
            metadata={'batch_id': batch_id, 'success': success_count, 'failed': failure_count}
        )
    
    if failed_items:
        with st.expander("❌ Failed Updates", expanded=True):
            for item in failed_items:
                st.error(item)
    
    # Clear preview and reload data
    st.session_state.spu_preview_changes = None
    time.sleep(1)
    load_all_product_data()
    st.rerun()


def update_woocommerce_product(api_url: str, consumer_key: str, consumer_secret: str,
                                product_id: int, variation_id: Optional[int], updates: Dict) -> Tuple[bool, str]:
    """Update a product on WooCommerce"""
    
    try:
        # Determine endpoint
        if variation_id:
            endpoint = f"{api_url}/products/{product_id}/variations/{variation_id}"
        else:
            endpoint = f"{api_url}/products/{product_id}"
        
        # Send update request
        response = requests.put(
            endpoint,
            auth=(consumer_key, consumer_secret),
            json=updates,
            timeout=30
        )
        
        if response.status_code in (200, 201):
            return True, None
        else:
            return False, f"HTTP {response.status_code}: {response.text[:200]}"
    
    except Exception as e:
        return False, str(e)


# ==========================================
# EXCEL UPLOAD/DOWNLOAD
# ==========================================

def generate_excel_template() -> bytes:
    """Generate Excel template for bulk updates"""
    
    df = st.session_state.spu_updatable_df
    
    if df is None or df.empty:
        # Create empty template
        template_df = pd.DataFrame(columns=[
            'product_id', 'variation_id', 'product_name', 'sku',
            'current_stock', 'current_regular_price', 'current_sale_price',
            'new_stock', 'new_regular_price', 'new_sale_price'
        ])
    else:
        # Use current data
        template_df = df[[
            'product_id', 'variation_id', 'product_name', 'sku',
            'stock_quantity', 'regular_price', 'sale_price'
        ]].copy()
        
        template_df.columns = [
            'product_id', 'variation_id', 'product_name', 'sku',
            'current_stock', 'current_regular_price', 'current_sale_price'
        ]
        
        # Add empty update columns
        template_df['new_stock'] = None
        template_df['new_regular_price'] = None
        template_df['new_sale_price'] = None
    
    # Write to Excel
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        template_df.to_excel(writer, index=False, sheet_name='Products')
        
        # Add instructions sheet
        instructions = pd.DataFrame({
            'Instructions': [
                '1. Fill in the "new_stock", "new_regular_price", or "new_sale_price" columns',
                '2. Leave blank if you do not want to update that field',
                '3. Do NOT modify the product_id, variation_id, product_name, or sku columns',
                '4. Stock must be >= 0',
                '5. Sale price cannot be higher than regular price',
                '6. Save and upload the file back to the module'
            ]
        })
        instructions.to_excel(writer, index=False, sheet_name='Instructions')
    
    return output.getvalue()


def handle_excel_upload(uploaded_file, username: str):
    """Process uploaded Excel file"""
    
    try:
        # Read Excel file
        df = pd.read_excel(uploaded_file, sheet_name='Products')
        
        # Validate required columns
        required_cols = ['product_id', 'variation_id', 'new_stock', 'new_regular_price', 'new_sale_price']
        missing_cols = [col for col in required_cols if col not in df.columns]
        
        if missing_cols:
            st.error(f"❌ Missing columns in Excel file: {', '.join(missing_cols)}")
            return
        
        # Process changes
        changes = []
        errors = []
        
        for idx, row in df.iterrows():
            product_id = int(row['product_id'])
            variation_id = int(row['variation_id']) if pd.notna(row['variation_id']) else None
            
            change_item = {
                'product_id': product_id,
                'variation_id': variation_id,
                'changes': {}
            }
            
            # Check new stock
            if pd.notna(row['new_stock']):
                new_stock = int(row['new_stock'])
                if new_stock < 0:
                    errors.append(f"Row {idx + 2}: Stock cannot be negative")
                else:
                    change_item['changes']['stock_quantity'] = new_stock
            
            # Check new regular price
            if pd.notna(row['new_regular_price']):
                new_regular = float(row['new_regular_price'])
                if new_regular < 0:
                    errors.append(f"Row {idx + 2}: Regular price cannot be negative")
                else:
                    change_item['changes']['regular_price'] = new_regular
            
            # Check new sale price
            if pd.notna(row['new_sale_price']):
                new_sale = float(row['new_sale_price'])
                if new_sale < 0:
                    errors.append(f"Row {idx + 2}: Sale price cannot be negative")
                elif 'regular_price' in change_item['changes'] and new_sale > change_item['changes']['regular_price']:
                    errors.append(f"Row {idx + 2}: Sale price cannot be higher than regular price")
                else:
                    change_item['changes']['sale_price'] = new_sale
            
            if change_item['changes']:
                changes.append(change_item)
        
        # Show errors
        if errors:
            st.error("**Validation Errors in Excel:**")
            for error in errors:
                st.error(error)
        
        # Show summary
        if changes:
            st.success(f"✅ Found {len(changes)} valid updates in Excel file")
            
            # Apply updates directly (or you can integrate with preview)
            apply_excel_updates(changes, username)
        else:
            st.info("ℹ️ No changes found in Excel file")
    
    except Exception as e:
        st.error(f"❌ Error processing Excel file: {str(e)}")


def apply_excel_updates(changes: List[Dict], username: str):
    """Apply updates from Excel file"""
    
    # Generate batch ID
    batch_id = str(uuid.uuid4())
    
    # Get WooCommerce credentials
    try:
        wc_api_url = st.secrets["woocommerce"]["api_url"]
        wc_consumer_key = st.secrets["woocommerce"]["consumer_key"]
        wc_consumer_secret = st.secrets["woocommerce"]["consumer_secret"]
    except KeyError:
        st.error("⚠️ WooCommerce API credentials not configured!")
        return
    
    success_count = 0
    failure_count = 0
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    total = len(changes)
    
    for idx, item in enumerate(changes):
        status_text.text(f"Processing {idx + 1}/{total}")
        
        try:
            # Find product in database
            products = ProductDB.get_all_products(active_only=True)
            product = next(
                (p for p in products if p['product_id'] == item['product_id'] and p.get('variation_id') == item['variation_id']),
                None
            )
            
            if not product:
                failure_count += 1
                continue
            
            # Update database
            if ProductDB.update_product(product['id'], item['changes'], username):
                # Log changes
                for field, new_value in item['changes'].items():
                    StockPriceDB.log_change(
                        product_id=item['product_id'],
                        variation_id=item['variation_id'],
                        field=field,
                        old_value=str(product.get(field, '')),
                        new_value=str(new_value),
                        changed_by=username,
                        batch_id=batch_id,
                        source='excel_upload'
                    )
                
                # Update WooCommerce
                wc_success, _ = update_woocommerce_product(
                    wc_api_url, wc_consumer_key, wc_consumer_secret,
                    item['product_id'], item['variation_id'], item['changes']
                )
                
                if wc_success:
                    success_count += 1
                else:
                    failure_count += 1
            else:
                failure_count += 1
        
        except Exception:
            failure_count += 1
        
        progress_bar.progress((idx + 1) / total)
    
    progress_bar.empty()
    status_text.empty()
    
    # Show results
    col1, col2 = st.columns(2)
    col1.metric("✅ Success", success_count)
    col2.metric("❌ Failed", failure_count)
    
    if success_count > 0:
        st.success(f"✅ Applied {success_count} updates from Excel!")
        
        # Log activity
        ActivityLogger.log(
            user_id=st.session_state.user['id'],
            action_type='excel_upload',
            module_key='stock_price_updater',
            description=f"Excel upload: {success_count} updates",
            metadata={'batch_id': batch_id, 'filename': 'excel_upload'}
        )
        
        time.sleep(1)
        load_all_product_data()
        st.rerun()


# ==========================================
# SYNC FROM WOOCOMMERCE
# ==========================================

def sync_from_woocommerce(username: str):
    """Sync latest prices and stock from WooCommerce"""
    
    st.markdown("---")
    st.markdown("#### 🔄 Syncing from WooCommerce...")
    
    # Get credentials
    try:
        wc_api_url = st.secrets["woocommerce"]["api_url"]
        wc_consumer_key = st.secrets["woocommerce"]["consumer_key"]
        wc_consumer_secret = st.secrets["woocommerce"]["consumer_secret"]
    except KeyError:
        st.error("⚠️ WooCommerce API credentials not configured!")
        return
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    try:
        # Get all products from our database
        all_products = ProductDB.get_all_products(active_only=False)
        total = len(all_products)
        
        if total == 0:
            st.warning("No products in database to sync")
            return
        
        status_text.text(f"Syncing {total} products...")
        
        updated_count = 0
        deleted_count = 0
        error_count = 0
        
        for idx, product in enumerate(all_products):
            try:
                product_id = product['product_id']
                variation_id = product.get('variation_id')
                
                # Fetch from WooCommerce
                if variation_id:
                    endpoint = f"{wc_api_url}/products/{product_id}/variations/{variation_id}"
                else:
                    endpoint = f"{wc_api_url}/products/{product_id}"
                
                response = requests.get(
                    endpoint,
                    auth=(wc_consumer_key, wc_consumer_secret),
                    timeout=30
                )
                
                if response.status_code == 404:
                    # Product deleted on WooCommerce
                    StockPriceDB.mark_as_deleted(product_id, variation_id, username)
                    deleted_count += 1
                
                elif response.status_code == 200:
                    wc_product = response.json()
                    
                    # Update with latest data
                    updates = {
                        'stock_quantity': wc_product.get('stock_quantity', 0),
                        'regular_price': float(wc_product.get('regular_price', 0) or 0),
                        'sale_price': float(wc_product.get('sale_price', 0) or 0),
                        'last_synced': datetime.now().isoformat()
                    }
                    
                    ProductDB.update_product(product['id'], updates, username)
                    updated_count += 1
                else:
                    error_count += 1
            
            except Exception:
                error_count += 1
            
            # Update progress
            progress_bar.progress((idx + 1) / total)
            status_text.text(f"Syncing {idx + 1}/{total}...")
        
        # Clear progress
        progress_bar.empty()
        status_text.empty()
        
        # Show results
        st.success(f"✅ Sync complete!")
        col1, col2, col3 = st.columns(3)
        col1.metric("Updated", updated_count)
        col2.metric("Deleted", deleted_count)
        col3.metric("Errors", error_count)
        
        # Log activity
        ActivityLogger.log(
            user_id=st.session_state.user['id'],
            action_type='sync',
            module_key='stock_price_updater',
            description=f"Synced from WooCommerce",
            metadata={'updated': updated_count, 'deleted': deleted_count, 'errors': error_count}
        )
        
        time.sleep(1)
        load_all_product_data()
        st.rerun()
    
    except Exception as e:
        st.error(f"❌ Sync failed: {str(e)}")
    finally:
        progress_bar.empty()
        status_text.empty()


# ==========================================
# TAB 2: MANAGE LISTS (Admin Only)
# ==========================================

def show_manage_lists_tab(username: str):
    """Admin interface to manage updatable/non-updatable lists"""
    
    st.markdown("### ⚙️ Manage Product Lists")
    st.info("Move products between Updatable and Non-Updatable lists")
    
    # Search and filter
    col1, col2 = st.columns(2)
    
    with col1:
        search_term = st.text_input("🔍 Search products", placeholder="Search by name or SKU")
    
    with col2:
        filter_list = st.selectbox("Filter by list", ["All", "Updatable", "Non-Updatable", "Deleted"])
    
    # Load products
    all_products = ProductDB.get_all_products(active_only=False)
    settings = StockPriceDB.get_all_settings()
    
    # Create settings map
    settings_map = {}
    for setting in settings:
        key = (setting['product_id'], setting.get('variation_id'))
        settings_map[key] = setting
    
    # Add settings to products
    for product in all_products:
        key = (product['product_id'], product.get('variation_id'))
        setting = settings_map.get(key, {'is_updatable': True, 'is_deleted': False})
        product['is_updatable'] = setting.get('is_updatable', True)
        product['is_deleted'] = setting.get('is_deleted', False)
    
    # Filter products
    if search_term:
        all_products = [
            p for p in all_products 
            if search_term.lower() in p['product_name'].lower() or search_term.lower() in str(p.get('sku', '')).lower()
        ]
    
    if filter_list == "Updatable":
        all_products = [p for p in all_products if p['is_updatable'] and not p['is_deleted']]
    elif filter_list == "Non-Updatable":
        all_products = [p for p in all_products if not p['is_updatable'] and not p['is_deleted']]
    elif filter_list == "Deleted":
        all_products = [p for p in all_products if p['is_deleted']]
    
    if not all_products:
        st.info("No products found")
        return
    
    st.success(f"Found {len(all_products)} products")
    
    # Display products with action buttons
    for product in all_products:
        with st.container():
            col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
            
            with col1:
                status_icon = "✅" if product['is_updatable'] else "🔒" if not product['is_deleted'] else "🗑️"
                st.write(f"{status_icon} **{product['product_name']}** (SKU: {product.get('sku', 'N/A')})")
            
            with col2:
                st.text(f"Stock: {product.get('stock_quantity', 0)}")
            
            with col3:
                if not product['is_deleted']:
                    if product['is_updatable']:
                        if st.button("🔒 Lock", key=f"lock_{product['product_id']}_{product.get('variation_id')}"):
                            StockPriceDB.update_setting(product['product_id'], product.get('variation_id'), False, username)
                            st.rerun()
                    else:
                        if st.button("✅ Unlock", key=f"unlock_{product['product_id']}_{product.get('variation_id')}"):
                            StockPriceDB.update_setting(product['product_id'], product.get('variation_id'), True, username)
                            st.rerun()
            
            with col4:
                if product['is_deleted']:
                    if st.button("♻️ Restore", key=f"restore_{product['product_id']}_{product.get('variation_id')}"):
                        StockPriceDB.restore_deleted(product['product_id'], product.get('variation_id'), username)
                        st.rerun()
            
            st.markdown("---")


# ==========================================
# TAB 3: STATISTICS
# ==========================================

def show_statistics_tab():
    """Show statistics"""
    
    st.markdown("### 📈 Statistics")
    
    stats = StockPriceDB.get_statistics()
    
    col1, col2, col3, col4 = st.columns(4)
    
    col1.metric("✅ Updatable", stats['updatable'])
    col2.metric("🔒 Non-Updatable", stats['non_updatable'])
    col3.metric("🗑️ Deleted", stats['deleted'])
    col4.metric("📊 Total", stats['total'])


# ==========================================
# DATABASE HELPER CLASS
# ==========================================

class StockPriceDB:
    """Database operations for stock & price updater"""
    
    @staticmethod
    def get_all_settings() -> List[Dict]:
        """Get all product update settings"""
        try:
            db = Database.get_client()
            response = db.table('product_update_settings').select('*').execute()
            return response.data if response.data else []
        except Exception as e:
            st.error(f"Error fetching settings: {str(e)}")
            return []
    
    @staticmethod
    def update_setting(product_id: int, variation_id: Optional[int], is_updatable: bool, username: str) -> bool:
        """Update or create a setting"""
        try:
            db = Database.get_client()
            
            data = {
                'product_id': product_id,
                'variation_id': variation_id,
                'is_updatable': is_updatable,
                'updated_by': username
            }
            
            # Upsert
            response = db.table('product_update_settings').upsert(data, on_conflict='product_id,variation_id').execute()
            return True
        except Exception as e:
            st.error(f"Error updating setting: {str(e)}")
            return False
    
    @staticmethod
    def mark_as_deleted(product_id: int, variation_id: Optional[int], username: str) -> bool:
        """Mark a product as deleted"""
        try:
            db = Database.get_client()
            
            data = {
                'product_id': product_id,
                'variation_id': variation_id,
                'is_deleted': True,
                'updated_by': username
            }
            
            db.table('product_update_settings').upsert(data, on_conflict='product_id,variation_id').execute()
            return True
        except Exception as e:
            st.error(f"Error marking as deleted: {str(e)}")
            return False
    
    @staticmethod
    def restore_deleted(product_id: int, variation_id: Optional[int], username: str) -> bool:
        """Restore a deleted product"""
        try:
            db = Database.get_client()
            
            data = {
                'product_id': product_id,
                'variation_id': variation_id,
                'is_deleted': False,
                'updated_by': username
            }
            
            db.table('product_update_settings').upsert(data, on_conflict='product_id,variation_id').execute()
            return True
        except Exception as e:
            st.error(f"Error restoring: {str(e)}")
            return False
    
    @staticmethod
    def log_change(product_id: int, variation_id: Optional[int], field: str,
                   old_value: str, new_value: str, changed_by: str,
                   batch_id: str, source: str = 'manual') -> bool:
        """Log a price/stock change"""
        try:
            db = Database.get_client()
            
            data = {
                'product_id': product_id,
                'variation_id': variation_id,
                'field_changed': field,
                'old_value': old_value,
                'new_value': new_value,
                'changed_by': changed_by,
                'batch_id': batch_id,
                'change_source': source,
                'sync_status': 'pending'
            }
            
            db.table('stock_price_history').insert(data).execute()
            return True
        except Exception as e:
            st.error(f"Error logging change: {str(e)}")
            return False
    
    @staticmethod
    def mark_changes_synced(batch_id: str, product_id: int, variation_id: Optional[int],
                            success: bool, error: Optional[str] = None) -> bool:
        """Mark changes as synced to WooCommerce"""
        try:
            db = Database.get_client()
            
            query = db.table('stock_price_history').update({
                'sync_status': 'success' if success else 'failed',
                'sync_error': error,
                'sync_attempted_at': datetime.now().isoformat()
            }).eq('batch_id', batch_id).eq('product_id', product_id)
            
            if variation_id:
                query = query.eq('variation_id', variation_id)
            else:
                query = query.is_('variation_id', 'null')
            
            query.execute()
            return True
        except Exception as e:
            st.error(f"Error marking sync status: {str(e)}")
            return False
    
    @staticmethod
    def get_statistics() -> Dict:
        """Get statistics"""
        try:
            db = Database.get_client()
            
            all_settings = db.table('product_update_settings').select('*').execute()
            
            total = len(all_settings.data) if all_settings.data else 0
            updatable = len([s for s in all_settings.data if s.get('is_updatable') and not s.get('is_deleted')]) if all_settings.data else 0
            non_updatable = len([s for s in all_settings.data if not s.get('is_updatable') and not s.get('is_deleted')]) if all_settings.data else 0
            deleted = len([s for s in all_settings.data if s.get('is_deleted')]) if all_settings.data else 0
            
            return {
                'total': total,
                'updatable': updatable,
                'non_updatable': non_updatable,
                'deleted': deleted
            }
        except Exception as e:
            st.error(f"Error fetching statistics: {str(e)}")
            return {'total': 0, 'updatable': 0, 'non_updatable': 0, 'deleted': 0}
