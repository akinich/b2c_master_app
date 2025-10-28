"""
Database Helper Functions for WooCommerce Products
Handles all database operations for the product management module
"""

from supabase import Client
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import streamlit as st


class ProductDB:
    """Database operations for WooCommerce products"""
    
    @staticmethod
    def get_supabase() -> Client:
        """Get Supabase client from session state"""
        if 'supabase' not in st.session_state:
            raise Exception("Supabase client not initialized")
        return st.session_state.supabase
    
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
            supabase = ProductDB.get_supabase()
            
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
            product_data['last_synced'] = datetime.now().isoformat()
            
            supabase.table('woocommerce_products').insert(product_data).execute()
            return True
            
        except Exception as e:
            st.error(f"Error adding product: {str(e)}")
            return False
    
    @staticmethod
    def bulk_add_products(products: List[Dict], username: str) -> Tuple[int, int]:
        """
        Bulk add products (used for WooCommerce sync)
        
        Args:
            products: List of product dictionaries
            username: User performing the sync
            
        Returns:
            Tuple[int, int]: (products_added, products_skipped)
        """
        try:
            supabase = ProductDB.get_supabase()
            added = 0
            skipped = 0
            
            for product in products:
                # Check if product already exists
                existing = supabase.table('woocommerce_products').select('id').eq(
                    'product_id', product['product_id']
                )
                
                if product.get('variation_id'):
                    existing = existing.eq('variation_id', product['variation_id'])
                else:
                    existing = existing.is_('variation_id', 'null')
                
                result = existing.execute()
                
                if result.data:
                    # Product exists, skip
                    skipped += 1
                else:
                    # Add new product
                    product['created_by'] = username
                    product['updated_by'] = username
                    product['last_synced'] = datetime.now().isoformat()
                    
                    supabase.table('woocommerce_products').insert(product).execute()
                    added += 1
            
            return added, skipped
            
        except Exception as e:
            st.error(f"Error in bulk add: {str(e)}")
            return 0, 0
    
    # ==========================================
    # READ OPERATIONS
    # ==========================================
    
    @staticmethod
    def get_all_products(
        active_only: bool = True,
        search: Optional[str] = None,
        status_filter: Optional[str] = None,
        category_filter: Optional[str] = None
    ) -> List[Dict]:
        """
        Get all products with optional filters
        
        Args:
            active_only: Only return active products
            search: Search term for product name
            status_filter: Filter by product status
            category_filter: Filter by category
            
        Returns:
            List[Dict]: List of products
        """
        try:
            supabase = ProductDB.get_supabase()
            query = supabase.table('woocommerce_products').select('*')
            
            # Apply filters
            if active_only:
                query = query.eq('is_active', True)
            
            if search:
                query = query.ilike('product_name', f'%{search}%')
            
            if status_filter and status_filter != 'All':
                query = query.eq('product_status', status_filter)
            
            if category_filter and category_filter != 'All':
                query = query.ilike('categories', f'%{category_filter}%')
            
            # Order by product_id and variation_id
            query = query.order('product_id').order('variation_id', desc=False, nullsfirst=True)
            
            result = query.execute()
            return result.data if result.data else []
            
        except Exception as e:
            st.error(f"Error fetching products: {str(e)}")
            return []
    
    @staticmethod
    def get_product_by_id(product_id: int, variation_id: Optional[int] = None) -> Optional[Dict]:
        """Get a specific product by ID"""
        try:
            supabase = ProductDB.get_supabase()
            query = supabase.table('woocommerce_products').select('*').eq('product_id', product_id)
            
            if variation_id:
                query = query.eq('variation_id', variation_id)
            else:
                query = query.is_('variation_id', 'null')
            
            result = query.execute()
            return result.data[0] if result.data else None
            
        except Exception as e:
            st.error(f"Error fetching product: {str(e)}")
            return None
    
    @staticmethod
    def get_unique_statuses() -> List[str]:
        """Get list of unique product statuses"""
        try:
            supabase = ProductDB.get_supabase()
            result = supabase.table('woocommerce_products').select('product_status').execute()
            
            if result.data:
                statuses = list(set([p['product_status'] for p in result.data if p.get('product_status')]))
                return sorted(statuses)
            return []
            
        except Exception as e:
            st.error(f"Error fetching statuses: {str(e)}")
            return []
    
    @staticmethod
    def get_unique_categories() -> List[str]:
        """Get list of unique categories"""
        try:
            supabase = ProductDB.get_supabase()
            result = supabase.table('woocommerce_products').select('categories').execute()
            
            if result.data:
                all_categories = set()
                for p in result.data:
                    if p.get('categories'):
                        # Split comma-separated categories
                        cats = [c.strip() for c in p['categories'].split(',')]
                        all_categories.update(cats)
                return sorted(list(all_categories))
            return []
            
        except Exception as e:
            st.error(f"Error fetching categories: {str(e)}")
            return []
    
    @staticmethod
    def get_product_stats() -> Dict:
        """Get product statistics"""
        try:
            supabase = ProductDB.get_supabase()
            result = supabase.table('woocommerce_products').select('*').execute()
            
            if not result.data:
                return {
                    'total': 0,
                    'active': 0,
                    'inactive': 0,
                    'simple': 0,
                    'variations': 0,
                    'missing_hsn': 0
                }
            
            products = result.data
            total = len(products)
            active = sum(1 for p in products if p.get('is_active'))
            inactive = total - active
            simple = sum(1 for p in products if not p.get('variation_id'))
            variations = total - simple
            missing_hsn = sum(1 for p in products if not p.get('hsn'))
            
            return {
                'total': total,
                'active': active,
                'inactive': inactive,
                'simple': simple,
                'variations': variations,
                'missing_hsn': missing_hsn
            }
            
        except Exception as e:
            st.error(f"Error fetching stats: {str(e)}")
            return {}
    
    # ==========================================
    # UPDATE OPERATIONS
    # ==========================================
    
    @staticmethod
    def update_product(db_id: int, updates: Dict, username: str) -> bool:
        """
        Update a product
        
        Args:
            db_id: Database ID of the product
            updates: Dictionary with fields to update
            username: User performing the update
            
        Returns:
            bool: Success status
        """
        try:
            supabase = ProductDB.get_supabase()
            
            # Validate HSN if being updated
            if 'hsn' in updates and updates['hsn']:
                hsn = str(updates['hsn']).strip()
                if not hsn.isdigit():
                    st.error("❌ HSN must contain only numbers")
                    return False
                updates['hsn'] = hsn
            
            # Add audit field
            updates['updated_by'] = username
            
            supabase.table('woocommerce_products').update(updates).eq('id', db_id).execute()
            return True
            
        except Exception as e:
            st.error(f"Error updating product: {str(e)}")
            return False
    
    @staticmethod
    def bulk_update_products(product_ids: List[int], updates: Dict, username: str) -> int:
        """
        Bulk update multiple products
        
        Args:
            product_ids: List of database IDs
            updates: Dictionary with fields to update
            username: User performing the update
            
        Returns:
            int: Number of products updated
        """
        try:
            supabase = ProductDB.get_supabase()
            
            # Validate HSN if being updated
            if 'hsn' in updates and updates['hsn']:
                hsn = str(updates['hsn']).strip()
                if not hsn.isdigit():
                    st.error("❌ HSN must contain only numbers")
                    return 0
                updates['hsn'] = hsn
            
            # Add audit field
            updates['updated_by'] = username
            
            count = 0
            for db_id in product_ids:
                supabase.table('woocommerce_products').update(updates).eq('id', db_id).execute()
                count += 1
            
            return count
            
        except Exception as e:
            st.error(f"Error in bulk update: {str(e)}")
            return 0
    
    @staticmethod
    def mark_products_inactive(product_ids: List[int], username: str) -> int:
        """Mark products as inactive (soft delete)"""
        return ProductDB.bulk_update_products(
            product_ids, 
            {'is_active': False}, 
            username
        )
    
    # ==========================================
    # DELETE OPERATIONS
    # ==========================================
    
    @staticmethod
    def delete_product(db_id: int) -> bool:
        """
        Hard delete a product
        
        Args:
            db_id: Database ID of the product
            
        Returns:
            bool: Success status
        """
        try:
            supabase = ProductDB.get_supabase()
            supabase.table('woocommerce_products').delete().eq('id', db_id).execute()
            return True
            
        except Exception as e:
            st.error(f"Error deleting product: {str(e)}")
            return False
    
    @staticmethod
    def bulk_delete_products(product_ids: List[int]) -> int:
        """
        Bulk delete multiple products (hard delete)
        
        Args:
            product_ids: List of database IDs
            
        Returns:
            int: Number of products deleted
        """
        try:
            supabase = ProductDB.get_supabase()
            count = 0
            
            for db_id in product_ids:
                supabase.table('woocommerce_products').delete().eq('id', db_id).execute()
                count += 1
            
            return count
            
        except Exception as e:
            st.error(f"Error in bulk delete: {str(e)}")
            return 0
    
    # ==========================================
    # SYNC OPERATIONS
    # ==========================================
    
    @staticmethod
    def mark_missing_products_inactive(wc_product_ids: List[int], username: str) -> int:
        """
        Mark products as inactive if they're not in the WooCommerce product list
        
        Args:
            wc_product_ids: List of product IDs from WooCommerce
            username: User performing the sync
            
        Returns:
            int: Number of products marked inactive
        """
        try:
            supabase = ProductDB.get_supabase()
            
            # Get all active products from database
            result = supabase.table('woocommerce_products').select('id, product_id').eq('is_active', True).execute()
            
            if not result.data:
                return 0
            
            # Find products not in WooCommerce list
            missing_ids = [
                p['id'] for p in result.data 
                if p['product_id'] not in wc_product_ids
            ]
            
            if missing_ids:
                return ProductDB.mark_products_inactive(missing_ids, username)
            
            return 0
            
        except Exception as e:
            st.error(f"Error marking missing products: {str(e)}")
          return 0
