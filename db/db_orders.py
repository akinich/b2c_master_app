"""
Database helper functions for WooCommerce Orders Cache
Handles syncing orders from WooCommerce API and querying cached data
"""
import streamlit as st
from datetime import datetime, date, timedelta
import json
from typing import List, Dict, Optional
import pandas as pd


class OrderDB:
    """Database operations for WooCommerce orders cache"""
    
    @staticmethod
    def get_supabase():
    """Get Supabase client from session state"""
        if 'supabase' not in st.session_state:
            from supabase import create_client
            url = st.secrets["supabase"]["url"]
            key = st.secrets["supabase"]["service_role_key"]
            st.session_state.supabase = create_client(url, key)
        return st.session_state.supabase
    
    @staticmethod
    def upsert_order(order_data: Dict) -> bool:
        """
        Insert or update a single order in cache
        
        Args:
            order_data: Dictionary containing order information
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            supabase = OrderDB.get_supabase()
            
            # Prepare data for upsert
            cache_data = {
                'order_id': order_data.get('id'),
                'order_number': order_data.get('number'),
                'order_status': order_data.get('status'),
                'order_date': order_data.get('date_created'),
                'order_total': float(order_data.get('total', 0)),
                'customer_email': order_data.get('billing', {}).get('email'),
                'customer_name': f"{order_data.get('billing', {}).get('first_name', '')} {order_data.get('billing', {}).get('last_name', '')}".strip(),
                'customer_phone': order_data.get('billing', {}).get('phone'),
                'billing_address_1': order_data.get('billing', {}).get('address_1'),
                'billing_city': order_data.get('billing', {}).get('city'),
                'billing_state': order_data.get('billing', {}).get('state'),
                'billing_postcode': order_data.get('billing', {}).get('postcode'),
                'billing_country': order_data.get('billing', {}).get('country'),
                'shipping_address_1': order_data.get('shipping', {}).get('address_1'),
                'shipping_city': order_data.get('shipping', {}).get('city'),
                'shipping_state': order_data.get('shipping', {}).get('state'),
                'shipping_postcode': order_data.get('shipping', {}).get('postcode'),
                'shipping_country': order_data.get('shipping', {}).get('country'),
                'subtotal': float(order_data.get('subtotal', 0)),
                'shipping_total': float(order_data.get('shipping_total', 0)),
                'tax_total': float(order_data.get('tax_total', 0)),
                'discount_total': float(order_data.get('discount_total', 0)),
                'payment_method': order_data.get('payment_method'),
                'payment_method_title': order_data.get('payment_method_title'),
                'total_items': sum(item.get('quantity', 0) for item in order_data.get('line_items', [])),
                'item_count': len(order_data.get('line_items', [])),
                'items_json': json.dumps(order_data.get('line_items', [])),
                'customer_note': order_data.get('customer_note'),
                'transaction_id': order_data.get('transaction_id'),
                'is_paid': order_data.get('date_paid') is not None,
                'date_paid': order_data.get('date_paid'),
                'date_completed': order_data.get('date_completed'),
                'last_synced': datetime.now().isoformat(),
                'sync_status': 'synced'
            }
            
            # Remove None values
            cache_data = {k: v for k, v in cache_data.items() if v is not None}
            
            # Upsert to database
            result = supabase.table('woocommerce_orders_cache').upsert(
                cache_data,
                on_conflict='order_id'
            ).execute()
            
            return True
            
        except Exception as e:
            st.error(f"Error upserting order {order_data.get('id')}: {str(e)}")
            return False
    
    @staticmethod
    def batch_upsert_orders(orders: List[Dict]) -> Dict[str, int]:
        """
        Batch insert/update multiple orders
        
        Args:
            orders: List of order dictionaries from WooCommerce API
            
        Returns:
            Dict with success and error counts
        """
        success_count = 0
        error_count = 0
        
        for order in orders:
            if OrderDB.upsert_order(order):
                success_count += 1
            else:
                error_count += 1
        
        return {
            'success': success_count,
            'errors': error_count,
            'total': len(orders)
        }
    
    @staticmethod
    def get_orders_summary(start_date: date, end_date: date, status: Optional[str] = None) -> pd.DataFrame:
        """
        Get order summary statistics for a date range
        
        Args:
            start_date: Start date
            end_date: End date
            status: Optional filter by order status
            
        Returns:
            DataFrame with summary statistics by status
        """
        try:
            supabase = OrderDB.get_supabase()
            
            # Build query
            query = supabase.table('woocommerce_orders_cache').select(
                'order_status, order_id, order_total'
            ).gte('order_date', start_date.isoformat()).lte('order_date', end_date.isoformat())
            
            if status:
                query = query.eq('order_status', status)
            
            result = query.execute()
            
            if not result.data:
                return pd.DataFrame(columns=['order_status', 'order_count', 'total_value'])
            
            # Convert to DataFrame and aggregate
            df = pd.DataFrame(result.data)
            summary = df.groupby('order_status').agg({
                'order_id': 'count',
                'order_total': 'sum'
            }).reset_index()
            
            summary.columns = ['order_status', 'order_count', 'total_value']
            summary['total_value'] = summary['total_value'].round(2)
            
            return summary
            
        except Exception as e:
            st.error(f"Error fetching order summary: {str(e)}")
            return pd.DataFrame(columns=['order_status', 'order_count', 'total_value'])
    
    @staticmethod
    def get_status_metrics(start_date: date, end_date: date, statuses: List[str]) -> Dict[str, Dict]:
        """
        Get metrics for specific order statuses
        
        Args:
            start_date: Start date
            end_date: End date
            statuses: List of statuses to get metrics for (e.g., ['processing', 'pending', 'cancelled', 'refunded'])
            
        Returns:
            Dictionary with metrics for each status
        """
        summary = OrderDB.get_orders_summary(start_date, end_date)
        
        metrics = {}
        for status in statuses:
            status_data = summary[summary['order_status'] == status]
            if not status_data.empty:
                metrics[status] = {
                    'count': int(status_data['order_count'].values[0]),
                    'value': float(status_data['total_value'].values[0])
                }
            else:
                metrics[status] = {
                    'count': 0,
                    'value': 0.0
                }
        
        return metrics
    
    @staticmethod
    def get_last_sync_time() -> Optional[datetime]:
        """Get the timestamp of the last successful sync"""
        try:
            supabase = OrderDB.get_supabase()
            result = supabase.table('woocommerce_orders_cache').select('last_synced').order(
                'last_synced', desc=True
            ).limit(1).execute()
            
            if result.data:
                return datetime.fromisoformat(result.data[0]['last_synced'].replace('Z', '+00:00'))
            return None
            
        except Exception as e:
            st.warning(f"Could not get last sync time: {str(e)}")
            return None
    
    @staticmethod
    def get_orders_by_date_range(start_date: date, end_date: date) -> pd.DataFrame:
        """Get all orders for a date range"""
        try:
            supabase = OrderDB.get_supabase()
            
            result = supabase.table('woocommerce_orders_cache').select('*').gte(
                'order_date', start_date.isoformat()
            ).lte('order_date', end_date.isoformat()).order('order_date', desc=True).execute()
            
            if result.data:
                return pd.DataFrame(result.data)
            return pd.DataFrame()
            
        except Exception as e:
            st.error(f"Error fetching orders: {str(e)}")
            return pd.DataFrame()
    
    @staticmethod
    def clear_cache(days_old: int = 90) -> int:
        """
        Clear old cached orders
        
        Args:
            days_old: Delete orders older than this many days
            
        Returns:
            Number of orders deleted
        """
        try:
            supabase = OrderDB.get_supabase()
            cutoff_date = (datetime.now() - timedelta(days=days_old)).isoformat()
            
            result = supabase.table('woocommerce_orders_cache').delete().lt(
                'order_date', cutoff_date
            ).execute()
            
            return len(result.data) if result.data else 0
            
        except Exception as e:
            st.error(f"Error clearing cache: {str(e)}")
            return 0


class WooCommerceOrderSync:
    """Handles syncing orders from WooCommerce API to cache"""
    
    @staticmethod
    def sync_orders(start_date: date, end_date: date, batch_size: int = 100) -> Dict[str, any]:
        """
        Sync orders from WooCommerce API to cache in batches
        
        Args:
            start_date: Start date for orders to sync
            end_date: End date for orders to sync
            batch_size: Number of orders to fetch per API call (max 100)
            
        Returns:
            Dictionary with sync statistics
        """
        import requests
        import time
        
        # Get WooCommerce credentials
        WC_API_URL = st.secrets["woocommerce"]["api_url"]
        WC_CONSUMER_KEY = st.secrets["woocommerce"]["consumer_key"]
        WC_CONSUMER_SECRET = st.secrets["woocommerce"]["consumer_secret"]
        
        if not all([WC_API_URL, WC_CONSUMER_KEY, WC_CONSUMER_SECRET]):
            st.error("WooCommerce API credentials missing!")
            return {'success': False, 'error': 'Missing credentials'}
        
        all_orders = []
        page = 1
        total_pages = 1
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        try:
            while page <= total_pages:
                status_text.text(f"Fetching page {page} of {total_pages if total_pages > 1 else '?'}...")
                
                response = requests.get(
                    f"{WC_API_URL}/orders",
                    params={
                        "after": f"{start_date}T00:00:00",
                        "before": f"{end_date}T23:59:59",
                        "per_page": batch_size,
                        "page": page,
                        "status": "any",
                        "order": "asc",
                        "orderby": "id"
                    },
                    auth=(WC_CONSUMER_KEY, WC_CONSUMER_SECRET),
                    timeout=30
                )
                
                # Handle rate limiting
                if response.status_code == 429:
                    retry_after = int(response.headers.get('Retry-After', 60))
                    st.warning(f"Rate limit hit. Waiting {retry_after} seconds...")
                    time.sleep(retry_after)
                    continue
                
                if response.status_code != 200:
                    st.error(f"API Error: {response.status_code}")
                    break
                
                orders = response.json()
                
                if not orders:
                    break
                
                all_orders.extend(orders)
                
                # Get total pages from header
                total_pages = int(response.headers.get('X-WP-TotalPages', 1))
                
                # Update progress
                progress = min(page / total_pages, 1.0)
                progress_bar.progress(progress)
                
                page += 1
                
                # Small delay to avoid rate limiting
                time.sleep(0.5)
            
            # Batch upsert orders to database
            status_text.text(f"Syncing {len(all_orders)} orders to database...")
            sync_result = OrderDB.batch_upsert_orders(all_orders)
            
            progress_bar.empty()
            status_text.empty()
            
            return {
                'success': True,
                'total_fetched': len(all_orders),
                'synced': sync_result['success'],
                'errors': sync_result['errors']
            }
            
        except Exception as e:
            progress_bar.empty()
            status_text.empty()
            st.error(f"Sync error: {str(e)}")
            return {'success': False, 'error': str(e)}
