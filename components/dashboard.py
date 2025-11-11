"""
Enhanced Dashboard with WooCommerce Order Statistics
Displays processing, pending, cancelled, refunded, completed, and on-hold orders with counts and values

VERSION HISTORY:
1.0.0 - WooCommerce order dashboard with multi-status tracking - 11/11/25
KEY FUNCTIONS:
- Date range selector (Today, Yesterday, MTD, Custom)
- Six order status metrics with counts and values
- Admin sync interface for order cache updates
- Filterable summary with toggle checkboxes
- Quick comparison view (Today vs Yesterday vs MTD)
- Detailed orders view with filters and export
- Order statistics (avg value, orders per day)
"""
import streamlit as st
from datetime import datetime, date, timedelta
import pandas as pd
from auth.session import SessionManager
from db.db_orders import OrderDB, WooCommerceOrderSync


def show_dashboard():
    """Display enhanced dashboard with WooCommerce order statistics"""
    
    profile = SessionManager.get_user_profile()
    user = SessionManager.get_user()
    
    # Welcome message
    st.markdown(f"### Welcome back, {profile.get('full_name', user.get('email'))}! 👋")
    st.markdown("---")
    
    # Dashboard Title
    st.markdown("## 📊 WooCommerce Order Dashboard")
    
    # Sync Section (for Admins only)
    if SessionManager.is_admin():
        with st.expander("🔄 Sync Orders from WooCommerce"):
            col1, col2, col3 = st.columns([2, 2, 1])
            
            with col1:
                sync_start = st.date_input(
                    "Sync Start Date",
                    value=date.today() - timedelta(days=30),
                    key="sync_start"
                )
            
            with col2:
                sync_end = st.date_input(
                    "Sync End Date",
                    value=date.today(),
                    key="sync_end"
                )
            
            with col3:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("🔄 Sync Now", type="primary", width='stretch'):
                    with st.spinner("Syncing orders..."):
                        result = WooCommerceOrderSync.sync_orders(sync_start, sync_end)
                        
                        if result.get('success'):
                            st.success(f"✅ Synced {result['synced']} orders successfully!")
                            if result.get('errors', 0) > 0:
                                st.warning(f"⚠️ {result['errors']} orders had errors")
                            st.rerun()
                        else:
                            st.error(f"❌ Sync failed: {result.get('error', 'Unknown error')}")
            
            # Show last sync time
            last_sync = OrderDB.get_last_sync_time()
            if last_sync:
                st.caption(f"Last synced: {last_sync.strftime('%Y-%m-%d %H:%M:%S')}")
    
    st.markdown("---")
    
    # Date Selector Section
    st.markdown("### 📅 Select Date Range")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        # Quick select options
        date_option = st.radio(
            "Quick Select:",
            options=["Today", "Yesterday", "Month to Date", "Custom Range"],
            horizontal=False
        )
    
    with col2:
        # Calculate date range based on selection
        if date_option == "Today":
            start_date = date.today()
            end_date = date.today()
            st.info(f"📆 Showing data for: **{start_date.strftime('%B %d, %Y')}**")
        
        elif date_option == "Yesterday":
            start_date = date.today() - timedelta(days=1)
            end_date = date.today() - timedelta(days=1)
            st.info(f"📆 Showing data for: **{start_date.strftime('%B %d, %Y')}**")
        
        elif date_option == "Month to Date":
            start_date = date.today().replace(day=1)
            end_date = date.today()
            st.info(f"📆 Showing data from: **{start_date.strftime('%B %d')} to {end_date.strftime('%B %d, %Y')}**")
        
        else:  # Custom Range
            col_start, col_end = st.columns(2)
            with col_start:
                start_date = st.date_input(
                    "Start Date",
                    value=date.today() - timedelta(days=7),
                    max_value=date.today()
                )
            with col_end:
                end_date = st.date_input(
                    "End Date",
                    value=date.today(),
                    max_value=date.today()
                )
            
            if start_date > end_date:
                st.error("⚠️ Start date must be before end date!")
                return
            
            days_diff = (end_date - start_date).days
            st.info(f"📆 Showing data for: **{days_diff + 1} days** ({start_date.strftime('%b %d')} - {end_date.strftime('%b %d, %Y')})")
    
    st.markdown("---")
    
    # Fetch order statistics
    with st.spinner("Loading order statistics..."):
        statuses = ['processing', 'pending', 'cancelled', 'refunded', 'completed', 'on-hold']
        metrics = OrderDB.get_status_metrics(start_date, end_date, statuses)
    
    # Display Order Statistics
    st.markdown("### 📈 Order Statistics")
    
    # Row 1: Processing & Pending
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 🟢 Processing Orders")
        proc_count = metrics['processing']['count']
        proc_value = metrics['processing']['value']
        
        metric_col1, metric_col2 = st.columns(2)
        with metric_col1:
            st.metric(
                label="Count",
                value=f"{proc_count:,}",
                delta=None
            )
        with metric_col2:
            st.metric(
                label="Value",
                value=f"₹{proc_value:,.2f}",
                delta=None
            )
        
        if proc_count > 0:
            avg_value = proc_value / proc_count
            st.caption(f"Avg Order Value: ₹{avg_value:,.2f}")
    
    with col2:
        st.markdown("#### 🟡 Pending Payment Orders")
        pend_count = metrics['pending']['count']
        pend_value = metrics['pending']['value']
        
        metric_col1, metric_col2 = st.columns(2)
        with metric_col1:
            st.metric(
                label="Count",
                value=f"{pend_count:,}",
                delta=None
            )
        with metric_col2:
            st.metric(
                label="Value",
                value=f"₹{pend_value:,.2f}",
                delta=None
            )
        
        if pend_count > 0:
            avg_value = pend_value / pend_count
            st.caption(f"Avg Order Value: ₹{avg_value:,.2f}")
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Row 2: Cancelled & Refunded
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 🔴 Cancelled Orders")
        canc_count = metrics['cancelled']['count']
        canc_value = metrics['cancelled']['value']
        
        metric_col1, metric_col2 = st.columns(2)
        with metric_col1:
            st.metric(
                label="Count",
                value=f"{canc_count:,}",
                delta=None
            )
        with metric_col2:
            st.metric(
                label="Value",
                value=f"₹{canc_value:,.2f}",
                delta=None
            )
        
        if canc_count > 0:
            avg_value = canc_value / canc_count
            st.caption(f"Avg Order Value: ₹{avg_value:,.2f}")
    
    with col2:
        st.markdown("#### 🟣 Refunded Orders")
        ref_count = metrics['refunded']['count']
        ref_value = metrics['refunded']['value']
        
        metric_col1, metric_col2 = st.columns(2)
        with metric_col1:
            st.metric(
                label="Count",
                value=f"{ref_count:,}",
                delta=None
            )
        with metric_col2:
            st.metric(
                label="Value",
                value=f"₹{ref_value:,.2f}",
                delta=None
            )
        
        if ref_count > 0:
            avg_value = ref_value / ref_count
            st.caption(f"Avg Order Value: ₹{avg_value:,.2f}")
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Row 3: Completed & On-Hold
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### ✅ Completed Orders")
        comp_count = metrics['completed']['count']
        comp_value = metrics['completed']['value']
        
        metric_col1, metric_col2 = st.columns(2)
        with metric_col1:
            st.metric(
                label="Count",
                value=f"{comp_count:,}",
                delta=None
            )
        with metric_col2:
            st.metric(
                label="Value",
                value=f"₹{comp_value:,.2f}",
                delta=None
            )
        
        if comp_count > 0:
            avg_value = comp_value / comp_count
            st.caption(f"Avg Order Value: ₹{avg_value:,.2f}")
    
    with col2:
        st.markdown("#### 🟠 On-Hold Orders")
        hold_count = metrics['on-hold']['count']
        hold_value = metrics['on-hold']['value']
        
        metric_col1, metric_col2 = st.columns(2)
        with metric_col1:
            st.metric(
                label="Count",
                value=f"{hold_count:,}",
                delta=None
            )
        with metric_col2:
            st.metric(
                label="Value",
                value=f"₹{hold_value:,.2f}",
                delta=None
            )
        
        if hold_count > 0:
            avg_value = hold_value / hold_count
            st.caption(f"Avg Order Value: ₹{avg_value:,.2f}")
    
    st.markdown("---")

    # Overall Summary Section with Toggles
    st.markdown("### 📊 Overall Summary")

    # Checkboxes for each status
    st.markdown("**Include in Summary:**")
    toggle_cols = st.columns(6)

    include_status = {}
    status_labels = {
        'processing': '🟢 Processing',
        'pending': '🟡 Pending',
        'cancelled': '🔴 Cancelled',
        'refunded': '🟣 Refunded',
        'completed': '✅ Completed',
        'on-hold': '🟠 On-Hold'
    }

    for idx, (status, label) in enumerate(status_labels.items()):
        with toggle_cols[idx]:
            include_status[status] = st.checkbox(
                label,
                value=True,
                key=f"toggle_{status}"
            )

    st.markdown("<br>", unsafe_allow_html=True)

    # Calculate filtered totals based on toggles
    filtered_metrics = {k: v for k, v in metrics.items() if include_status.get(k, True)}
    total_count = sum(m['count'] for m in filtered_metrics.values())
    total_value = sum(m['value'] for m in filtered_metrics.values())

    sum_col1, sum_col2, sum_col3, sum_col4 = st.columns(4)

    with sum_col1:
        st.metric(
            label="Total Orders",
            value=f"{total_count:,}"
        )

    with sum_col2:
        st.metric(
            label="Total Value",
            value=f"₹{total_value:,.2f}"
        )

    with sum_col3:
        if total_count > 0:
            avg_order = total_value / total_count
            st.metric(
                label="Avg Order Value",
                value=f"₹{avg_order:,.2f}"
            )
        else:
            st.metric(label="Avg Order Value", value="₹0.00")

    with sum_col4:
        # Calculate date range in days
        days_in_range = (end_date - start_date).days + 1
        if days_in_range > 0:
            orders_per_day = total_count / days_in_range
            st.metric(
                label="Orders/Day",
                value=f"{orders_per_day:.1f}"
            )
        else:
            st.metric(label="Orders/Day", value="0")

    
    st.markdown("---")
    
    # Comparison Table (if more than one time period shown)
    if date_option != "Custom Range":
        st.markdown("### 📊 Quick Comparison View")
        
        # Get metrics for all three periods
        today_metrics = OrderDB.get_status_metrics(date.today(), date.today(), statuses)
        yesterday_metrics = OrderDB.get_status_metrics(
            date.today() - timedelta(days=1),
            date.today() - timedelta(days=1),
            statuses
        )
        mtd_start = date.today().replace(day=1)
        mtd_metrics = OrderDB.get_status_metrics(mtd_start, date.today(), statuses)
        
        # Create comparison DataFrame
        comparison_data = []
        for status in statuses:
            comparison_data.append({
                'Status': status.title(),
                'Today Count': today_metrics[status]['count'],
                'Today Value': f"₹{today_metrics[status]['value']:,.2f}",
                'Yesterday Count': yesterday_metrics[status]['count'],
                'Yesterday Value': f"₹{yesterday_metrics[status]['value']:,.2f}",
                'MTD Count': mtd_metrics[status]['count'],
                'MTD Value': f"₹{mtd_metrics[status]['value']:,.2f}"
            })
        
        comparison_df = pd.DataFrame(comparison_data)
        st.dataframe(comparison_df, width='stretch', hide_index=True)
    
    st.markdown("---")
    
    # Detailed Orders View (Optional - Expandable)
    with st.expander("📋 View Detailed Orders"):
        orders_df = OrderDB.get_orders_by_date_range(start_date, end_date)
        
        if not orders_df.empty:
            # Filter options
            filter_col1, filter_col2 = st.columns(2)
            
            with filter_col1:
                available_statuses = orders_df['order_status'].unique().tolist()
                default_statuses = [s for s in statuses if s in available_statuses]
                status_filter = st.multiselect(
                    "Filter by Status",
                    options=available_statuses,
                    default=default_statuses
                )
            
            with filter_col2:
                sort_by = st.selectbox(
                    "Sort by",
                    options=['Order Date (Newest)', 'Order Date (Oldest)', 'Value (High to Low)', 'Value (Low to High)']
                )
            
            # Apply filters
            filtered_df = orders_df[orders_df['order_status'].isin(status_filter)]
            
            # Apply sorting
            if sort_by == 'Order Date (Newest)':
                filtered_df = filtered_df.sort_values('order_date', ascending=False)
            elif sort_by == 'Order Date (Oldest)':
                filtered_df = filtered_df.sort_values('order_date', ascending=True)
            elif sort_by == 'Value (High to Low)':
                filtered_df = filtered_df.sort_values('order_total', ascending=False)
            else:
                filtered_df = filtered_df.sort_values('order_total', ascending=True)
            
            # Display selected columns
            display_cols = ['order_id', 'order_number', 'order_date', 'order_status', 'order_total', 
                          'customer_name', 'customer_email', 'total_items']
            
            if all(col in filtered_df.columns for col in display_cols):
                display_df = filtered_df[display_cols].copy()
                display_df['order_date'] = pd.to_datetime(display_df['order_date']).dt.strftime('%Y-%m-%d %H:%M')
                display_df.columns = ['ID', 'Order #', 'Date', 'Status', 'Total', 'Customer', 'Email', 'Items']
                
                st.dataframe(
                    display_df,
                    width='stretch',
                    hide_index=True,
                    height=400
                )
                
                # Export option
                if st.button("📥 Export to CSV"):
                    csv = display_df.to_csv(index=False)
                    st.download_button(
                        label="Download CSV",
                        data=csv,
                        file_name=f"orders_{start_date}_{end_date}.csv",
                        mime="text/csv"
                    )
            else:
                st.info("Some columns are missing from the data.")
        else:
            st.info("No orders found for the selected date range.")
    
    # Footer with refresh button
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        if st.button("🔄 Refresh Data", width='stretch'):
            st.rerun()
