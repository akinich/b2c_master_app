# Stock & Price Updater - Deployment Guide

## 📋 Overview

Complete module for updating WooCommerce product stock and prices with:
- 3-tier list management (Updatable / Non-Updatable / Deleted)
- Inline editing with preview
- Excel bulk upload/download
- WooCommerce sync
- Full audit trail
- Role-based access control

---

## 🗄️ Database Setup

### Step 1: Create Tables

Run these SQL files in Supabase SQL Editor:

#### 1. Product Update Settings Table
```sql
-- File: product_update_settings_schema.sql
-- Run this first
```
See `product_update_settings_schema.sql` in outputs folder.

#### 2. Stock & Price History Table
```sql
-- File: stock_price_history_schema.sql
-- Run this second
```
See `stock_price_history_schema.sql` in outputs folder.

### Step 2: Register Module

```sql
-- Add module to modules table
INSERT INTO modules (module_name, module_key, description, icon, display_order, is_active)
VALUES (
    'Stock & Price Updater',
    'stock_price_updater',
    'Update product stock and prices with list management',
    '💰',
    40,
    TRUE
)
ON CONFLICT (module_key) DO NOTHING;

-- Set permissions (Admin full access, Manager/User can update only)
INSERT INTO role_permissions (role_id, module_id, can_access)
SELECT 
    r.id,
    (SELECT id FROM modules WHERE module_key = 'stock_price_updater'),
    TRUE
FROM roles r
WHERE r.role_name IN ('Admin', 'Manager', 'User')
ON CONFLICT (role_id, module_id) DO UPDATE SET can_access = TRUE;
```

---

## 📦 File Deployment

### Step 1: Add Module File

1. Copy `stock_price_updater.py` to your `/modules` directory
2. Ensure `db_products.py` is in your root directory (already exists from Product Management)

### Step 2: Verify Dependencies

All required packages should already be installed:
- streamlit
- pandas
- requests
- openpyxl (for Excel handling)

If missing, add to `requirements.txt`:
```txt
openpyxl>=3.1.0
```

---

## ⚙️ Configuration

### WooCommerce API Credentials

Ensure these are in your `.streamlit/secrets.toml`:

```toml
[woocommerce]
api_url = "https://your-site.com/wp-json/wc/v3"
consumer_key = "ck_xxxxxxxxxxxxx"
consumer_secret = "cs_xxxxxxxxxxxxx"
```

---

## 🎯 Features Breakdown

### Tab 1: Update Products

**Three Tables:**

1. **Updatable List** (Expanded)
   - Shows all products available for editing
   - Columns: Product ID, Name, SKU, Current Stock/Prices, Update fields
   - Users can edit: New Stock, New Regular Price, New Sale Price
   - Preview button validates and shows changes
   - Update button applies changes to WooCommerce

2. **Non-Updatable List** (Collapsed)
   - View-only display
   - Products locked from updates (Admin can move to updatable)
   
3. **Deleted Items List** (Collapsed)
   - Products removed from WooCommerce
   - Auto-detected during sync
   - Admin can restore

**Actions:**
- ✅ Refresh Data
- 🔄 Sync from WooCommerce
- 📥 Download Excel Template
- 📤 Upload Excel File
- 👁️ Preview Changes
- 💾 Update Products

### Tab 2: Manage Lists (Admin Only)

- Search products by name or SKU
- Filter by list (Updatable/Non-Updatable/Deleted)
- Lock/Unlock products (move between lists)
- Restore deleted products
- Bulk operations

### Tab 3: Statistics

Quick metrics:
- Total products
- Updatable count
- Non-updatable count
- Deleted count

---

## 🔒 Access Control

| Role | Can View | Can Update Stock/Price | Can Manage Lists | Can Sync |
|------|----------|------------------------|------------------|----------|
| Admin | ✅ | ✅ | ✅ | ✅ |
| Manager | ✅ | ✅ | ❌ | ❌ |
| User | ✅ | ✅ | ❌ | ❌ |

---

## 📊 Data Flow

### Manual Update Flow:
```
1. User edits product in table
2. Click "Preview Changes"
3. System validates (sale price < regular price, stock >= 0)
4. Show preview of all changes
5. Click "Update Products"
6. Update local database
7. Log to stock_price_history
8. Push to WooCommerce API
9. Mark sync status (success/failed)
10. Show results summary
```

### Excel Upload Flow:
```
1. Download template with current data
2. User fills in new_stock, new_regular_price, new_sale_price columns
3. Upload Excel file
4. Validate all rows
5. Apply updates in batch
6. Show success/failure summary
```

### Sync Flow:
```
1. Get all products from local database
2. For each product:
   - Fetch from WooCommerce API
   - If 404 → Mark as deleted
   - If 200 → Update stock & prices
   - If error → Log error
3. Show summary (updated/deleted/errors)
```

---

## ✅ Validation Rules

**Stock:**
- Must be >= 0
- Cannot be negative from user input
- Negative allowed from WooCommerce sync only

**Regular Price:**
- Must be >= 0
- Cannot be blank if updating

**Sale Price:**
- Must be >= 0
- Cannot be higher than regular price (locked/warned)
- Can be 0 (no sale)

---

## 📝 Audit Trail

All changes logged to `stock_price_history` table:

```sql
{
  "product_id": 12345,
  "variation_id": 67890,
  "field_changed": "stock_quantity",
  "old_value": "100",
  "new_value": "150",
  "changed_by": "john.doe",
  "changed_at": "2025-10-30T10:30:00",
  "sync_status": "success",
  "batch_id": "uuid-here",
  "change_source": "manual"
}
```

---

## 🧪 Testing Checklist

### Initial Setup:
- [ ] Database tables created successfully
- [ ] Module registered in modules table
- [ ] Permissions set for all roles
- [ ] WooCommerce credentials configured
- [ ] Module appears in navigation

### Functionality:
- [ ] Can view updatable products
- [ ] Can edit stock/prices inline
- [ ] Preview validates correctly
- [ ] Sale price > regular price is blocked
- [ ] Negative stock is blocked
- [ ] Update pushes to WooCommerce
- [ ] Audit logs created
- [ ] Excel template downloads with data
- [ ] Excel upload works correctly
- [ ] Sync from WooCommerce updates data
- [ ] Deleted products move to deleted list
- [ ] Admin can lock/unlock products

---

## 📞 Support

If issues persist:
1. Check Supabase logs for database errors
2. Check Streamlit console for Python errors
3. Verify WooCommerce API logs
4. Review stock_price_history table for sync failures
5. Contact system administrator
