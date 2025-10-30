"""
Database Helper Functions for WooCommerce Products
Handles all database operations for the product management module
"""

from typing import List, Dict, Optional, Tuple
from datetime import datetime
import streamlit as st
from config.database import Database


class ProductDB:
    """Database operations for WooCommerce products"""
    
    # ==========================================
    # CREATE OPERATIONS
    # ==========================================
    
    @staticmethod
    def add_product(product_data: Dict, username: str) -> bool:
        """
        Add a new product to the database
        
        Args:
            product_data: Dictionary with product fields
            username: User who is adding the product
            
        Returns:
            bool: Success status
        """
        try:
            supabase = Database.get_client()
            
            # Validate HSN if provided (must be numeric only)
            if product_data.get('hsn'):
                hsn = str(product_data['hsn']).strip()
                if not hsn.isdigit():
                    st.error("❌ HSN must contain only numbers")
                    return False
                product_data['hsn'] = hsn
            
            # Add audit fields
            product_data['created_by'] = username
            product_data['updated_by'] = username
            product_data['created_at'] = datetime.now().isoformat()
            product_data['last_synced'] = datetime.now().isoformat()
            
            # Insert into database
            supabase.table('woocommerce_products').insert(product_data).execute()
            
            return True
            
        except Exception as e:
            st.error(f"Error adding product: {str(e)}")
            return False
    
    # ==========================================
    # READ OPERATIONS
    # ==========================================
    
    @staticmethod
    def get_all_products(active_only: bool = True) -> List[Dict]:
        """
        Get all products from database
        
        Args:
            active_only: If True, only return active products
            
        Returns:
            List of product dictionaries
        """
        try:
            supabase = Database.get_client()
            
            query = supabase.table('woocommerce_products').select('*')
            
            if active_only:
                query = query.eq('is_active', True)
            
            response = query.order('product_name').execute()
            
            return response.data if response.data else []
            
        except Exception as e:
            st.error(f"Error fetching products: {str(e)}")
            return []
    
    @staticmethod
    def search_products(search_term: str, active_only: bool = True) -> List[Dict]:
        """
        Search products by name
        
        Args:
            search_term: Search string
            active_only: If True, only search active products
            
        Returns:
            List of matching product dictionaries
        """
        try:
            supabase = Database.get_client()
            
            query = supabase.table('woocommerce_products').select('*')
            
            if active_only:
                query = query.eq('is_active', True)
            
            query = query.ilike('product_name', f'%{search_term}%')
            
            response = query.order('product_name').execute()
            
            return response.data if response.data else []
            
        except Exception as e:
            st.error(f"Error searching products: {str(e)}")
            return []
    
    @staticmethod
    def get_product_by_id(db_id: int) -> Optional[Dict]:
        """Get a single product by database ID"""
        try:
            supabase = Database.get_client()
            response = supabase.table('woocommerce_products').select('*').eq('id', db_id).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            st.error(f"Error fetching product: {str(e)}")
            return None
    
    @staticmethod
    def check_product_exists(product_id: int, variation_id: Optional[int] = None) -> bool:
        """
        Check if a product/variation already exists in database
        
        Args:
            product_id: WooCommerce product ID
            variation_id: WooCommerce variation ID (None for simple products)
            
        Returns:
            bool: True if exists, False otherwise
        """
        try:
            supabase = Database.get_client()
            
            query = supabase.table('woocommerce_products').select('id').eq('product_id', product_id)
            
            if variation_id is not None:
                query = query.eq('variation_id', variation_id)
            else:
                query = query.is_('variation_id', 'null')
            
            response = query.execute()
            
            return len(response.data) > 0
            
        except Exception as e:
            st.error(f"Error checking product existence: {str(e)}")
            return False
    
    # ==========================================
    # UPDATE OPERATIONS
    # ==========================================
    
    @staticmethod
    def update_product(db_id: int, updates: Dict, username: str) -> bool:
        """
        Update a product in the database
        
        Args:
            db_id: Database ID of the product
            updates: Dictionary with fields to update
            username: User making the update
            
        Returns:
            bool: Success status
        """
        try:
            supabase = Database.get_client()
            
            # Validate HSN if being updated
            if 'hsn' in updates and updates['hsn']:
                hsn = str(updates['hsn']).strip()
                if not hsn.isdigit():
                    st.error("❌ HSN must contain only numbers")
                    return False
                updates['hsn'] = hsn
            
            # Add audit field
            updates['updated_by'] = username
            
            # Update in database
            supabase.table('woocommerce_products').update(updates).eq('id', db_id).execute()
            
            return True
            
        except Exception as e:
            st.error(f"Error updating product: {str(e)}")
            return False
    
    @staticmethod
    def bulk_update_products(updates: List[Tuple[int, Dict]], username: str) -> Tuple[int, int]:
        """
        Bulk update multiple products
        
        Args:
            updates: List of tuples (db_id, update_dict)
            username: User making the updates
            
        Returns:
            Tuple of (success_count, failure_count)
        """
        success_count = 0
        failure_count = 0
        
        for db_id, update_dict in updates:
            if ProductDB.update_product(db_id, update_dict, username):
                success_count += 1
            else:
                failure_count += 1
        
        return success_count, failure_count
    
    # ==========================================
    # DELETE OPERATIONS
    # ==========================================
    
    @staticmethod
    def delete_product(db_id: int) -> bool:
        """
        Hard delete a product from database
        
        Args:
            db_id: Database ID of the product
            
        Returns:
            bool: Success status
        """
        try:
            supabase = Database.get_client()
            supabase.table('woocommerce_products').delete().eq('id', db_id).execute()
            return True
            
        except Exception as e:
            st.error(f"Error deleting product: {str(e)}")
            return False
    
    @staticmethod
    def mark_inactive(product_id: int, variation_id: Optional[int] = None) -> bool:
        """
        Mark a product as inactive (soft delete)
        
        Args:
            product_id: WooCommerce product ID
            variation_id: WooCommerce variation ID
            
        Returns:
            bool: Success status
        """
        try:
            supabase = Database.get_client()
            
            query = supabase.table('woocommerce_products').update({'is_active': False}).eq('product_id', product_id)
            
            if variation_id is not None:
                query = query.eq('variation_id', variation_id)
            else:
                query = query.is_('variation_id', 'null')
            
            query.execute()
            
            return True
            
        except Exception as e:
            st.error(f"Error marking product inactive: {str(e)}")
            return False
    
    # ==========================================
    # SYNC OPERATIONS
    # ==========================================
    
    @staticmethod
    def sync_from_woocommerce(products: List[Dict], username: str) -> Tuple[int, int, int]:
        """
        Sync products from WooCommerce to database
        Only adds NEW products, doesn't update existing ones
        
        Args:
            products: List of product dictionaries from WooCommerce API
            username: User performing the sync
            
        Returns:
            Tuple of (added_count, skipped_count, error_count)
        """
        added_count = 0
        skipped_count = 0
        error_count = 0
        
        for product in products:
            try:
                # Check if product already exists
                product_id = product.get('id')
                variation_id = product.get('variation_id')
                
                if ProductDB.check_product_exists(product_id, variation_id):
                    skipped_count += 1
                    continue
                
                # Prepare product data
                product_data = {
                    'product_id': product_id,
                    'variation_id': variation_id,
                    'sku': product.get('sku', ''),
                    'product_name': product.get('name', ''),
                    'parent_product': product.get('parent_name', ''),
                    'attribute': product.get('attributes', ''),
                    'regular_price': product.get('regular_price', 0),
                    'sale_price': product.get('sale_price', 0),
                    'stock_quantity': product.get('stock_quantity', 0),
                    'product_status': product.get('status', 'publish'),
                    'categories': product.get('categories', ''),
                    'is_active': True,
                    'last_synced': datetime.now().isoformat()
                }
                
                # Add the product
                if ProductDB.add_product(product_data, username):
                    added_count += 1
                else:
                    error_count += 1
                    
            except Exception as e:
                st.warning(f"Error syncing product {product.get('id')}: {str(e)}")
                error_count += 1
        
        return added_count, skipped_count, error_count
    
    # ==========================================
    # STATISTICS
    # ==========================================
    
    @staticmethod
    def get_product_stats() -> Dict:
        """Get product statistics"""
        try:
            supabase = Database.get_client()
            
            # Total products
            total_response = supabase.table('woocommerce_products').select('id', count='exact').execute()
            total = total_response.count if total_response.count else 0
            
            # Active products
            active_response = supabase.table('woocommerce_products').select('id', count='exact').eq('is_active', True).execute()
            active = active_response.count if active_response.count else 0
            
            # Simple products (variation_id is NULL)
            simple_response = supabase.table('woocommerce_products').select('id', count='exact').is_('variation_id', 'null').eq('is_active', True).execute()
            simple = simple_response.count if simple_response.count else 0
            
            # Variations (variation_id is NOT NULL)
            variations = active - simple
            
            return {
                'total': total,
                'active': active,
                'inactive': total - active,
                'simple': simple,
                'variations': variations
            }
            
        except Exception as e:
            st.error(f"Error fetching stats: {str(e)}")
            return {
                'total': 0,
                'active': 0,
                'inactive': 0,
                'simple': 0,
                'variations': 0
            }
