"""
Streamlit Dashboard for Spend Tracker
"""

import streamlit as st
import pandas as pd
try:
    import plotly.express as px
    import plotly.graph_objects as go
    PLOTLY_AVAILABLE = True
except Exception:
    PLOTLY_AVAILABLE = False
from datetime import datetime, timedelta
import sys
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent))

from src.database import SpendDatabase
from src.analyzer import SpendAnalyzer
from src.reminder_system import ReminderSystem
from src.cost_analyzer import CostAnalyzer
from src.config_loader import load_config as load_app_config


# Page configuration
st.set_page_config(
    page_title="Prat Spend Analyzer",
    page_icon="💰",
    layout="wide"
)

# Load configuration (supports Streamlit Secrets overlay)
@st.cache_resource
def load_config():
    return load_app_config()

@st.cache_resource
def get_database():
    config = load_config()
    db_path = config.get('database', {}).get('path', 'data/spend_tracker.db')
    return SpendDatabase(db_path)

@st.cache_resource
def get_analyzer():
    return SpendAnalyzer(get_database())

@st.cache_resource
def get_reminder_system():
    return ReminderSystem(get_database())


def main():
    st.title("💰 Prat Spend Analyzer")
    
    db = get_database()
    analyzer = get_analyzer()
    reminder_system = get_reminder_system()
    
    # Sidebar
    st.sidebar.header("Navigation")
    page = st.sidebar.selectbox(
        "Choose a page",
        ["Fetch Emails", "Overview", "Enhanced Analysis", "Cost Analyzer", "Monthly Analysis", "Spending Breakdown", "Bill Reminders", "Transactions"]
    )
    
    if page == "Fetch Emails":
        show_fetch_emails()
    elif page == "Overview":
        show_overview(analyzer, reminder_system)
    elif page == "Enhanced Analysis":
        show_enhanced_analysis(analyzer, db)
    elif page == "Cost Analyzer":
        show_cost_analyzer(db)
    elif page == "Monthly Analysis":
        show_monthly_analysis(analyzer)
    elif page == "Spending Breakdown":
        show_spending_breakdown(analyzer)
    elif page == "Bill Reminders":
        show_bill_reminders(reminder_system)
    elif page == "Transactions":
        show_transactions(db)


def show_fetch_emails():
    """Page for fetching and processing emails."""
    st.header("📧 Fetch Credit Card Emails")
    st.write("Enter your email credentials to automatically fetch and process credit card statements.")
    
    # Email input form
    with st.form("email_fetch_form"):
        email_address = st.text_input("Email Address", placeholder="your.email@gmail.com")
        email_password = st.text_input("Email Password / App Password", type="password", 
                                      help="Use your Gmail App Password (not your regular password)")
        
        col1, col2 = st.columns(2)
        with col1:
            fetch_from_2024 = st.checkbox("Fetch From 2024 Onwards", value=True,
                                         help="Fetches all emails from January 1, 2024. Uncheck to use custom days.")
        with col2:
            days_back = st.number_input("Days to Look Back", min_value=1, max_value=3650, 
                                       value=30, disabled=fetch_from_2024)
        
        submitted = st.form_submit_button("🚀 Fetch & Process Emails", use_container_width=True)
    
    if submitted:
        if not email_address or not email_password:
            st.error("Please enter both email address and password.")
        else:
            with st.spinner("Connecting to email and processing statements..."):
                try:
                    from main import fetch_and_process_emails
                    
                    days = None if fetch_from_2024 else days_back
                    result = fetch_and_process_emails(email_address, email_password, days_back=days)
                    
                    if result and result.get('success'):
                        st.success(f"✅ Successfully processed {result.get('emails_processed', 0)} emails!")
                        st.success(f"✅ Added {result.get('transactions_added', 0)} transactions to database!")
                        st.balloons()
                        
                        # Refresh data
                        st.cache_resource.clear()
                        st.rerun()
                    else:
                        st.error(f"❌ Error: {result.get('error', 'Unknown error occurred')}")
                        
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")
                    import traceback
                    st.code(traceback.format_exc())
    
    # Show processed emails info
    st.divider()
    st.subheader("📊 Processing Status")
    
    try:
        db = get_database()
        processed_emails = db.get_transactions()
        if not processed_emails.empty:
            st.info(f"Total transactions in database: {len(processed_emails)}")
            
            # Show by card
            card_counts = processed_emails['card_name'].value_counts()
            st.write("**Transactions by Card:**")
            st.dataframe(card_counts.reset_index().rename(columns={'index': 'Card', 'card_name': 'Count'}), 
                        use_container_width=True, hide_index=True)
        else:
            st.info("No transactions found. Fetch emails to get started!")
    except Exception as e:
        st.info("No transactions found yet. Fetch emails to get started!")


def show_overview(analyzer, reminder_system):
    st.header("📊 Overview")
    
    # Get insights
    insights = analyzer.get_spending_insights()
    reminder_summary = reminder_system.get_reminder_summary()
    
    # Key Metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Spend", f"₹{insights['total_spend']:,.2f}")
    
    with col2:
        st.metric("Avg Daily Spend", f"₹{insights['avg_daily_spend']:,.2f}")
    
    with col3:
        st.metric("Total Transactions", f"{insights['total_transactions']:,}")
    
    with col4:
        st.metric("Bills Due (7 days)", f"{reminder_summary['bills_due_7d']}", 
                 delta=f"₹{reminder_summary['total_due_7d']:,.2f}")
    
    st.divider()
    
    # Monthly Trends Chart
    st.subheader("📈 Monthly Spending Trends")
    trends = analyzer.get_monthly_trends(months=12)
    
    if not trends.empty:
        if PLOTLY_AVAILABLE:
            fig = px.line(
                trends, 
                x='period', 
                y='total_spend',
                markers=True,
                title="Spending Over Time"
            )
            fig.update_layout(xaxis_title="Month", yaxis_title="Total Spend (₹)")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Plotly charts are disabled (package not available). Showing table instead.")
            st.dataframe(trends, use_container_width=True)
    else:
        st.info("No spending data available yet. Fetch emails to get started!")
    
    # Spending by Card
    st.subheader("💳 Spending by Card")
    card_spend = analyzer.get_spending_by_card()
    
    if not card_spend.empty:
        col1, col2 = st.columns(2)
        
        with col1:
            if PLOTLY_AVAILABLE:
                fig = px.bar(
                    card_spend,
                    x='card_name',
                    y='total_amount',
                    title="Total Spend by Card"
                )
                fig.update_layout(xaxis_title="Card", yaxis_title="Amount (₹)")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Plotly not available; showing table instead.")
                st.dataframe(card_spend, use_container_width=True)
        
        with col2:
            st.dataframe(card_spend, use_container_width=True)
    else:
        st.info("No card data available.")


def show_monthly_analysis(analyzer):
    st.header("📅 Monthly Analysis")
    
    # Month selector
    col1, col2 = st.columns(2)
    with col1:
        selected_month = st.selectbox("Select Month", range(1, 13), 
                                     index=datetime.now().month - 1)
    with col2:
        selected_year = st.selectbox("Select Year", 
                                    range(datetime.now().year - 2, datetime.now().year + 1),
                                    index=2)
    
    summary = analyzer.get_monthly_summary(month=selected_month, year=selected_year)
    
    if summary.get('total_spend', 0) > 0:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Spend", f"₹{summary['total_spend']:,.2f}")
        with col2:
            st.metric("Transactions", f"{summary.get('transaction_count', 0)}")
        with col3:
            cards = summary.get('cards', {})
            st.metric("Active Cards", f"{len(cards)}")
        
        # Spending by card for selected month
        if cards:
            st.subheader("Spending by Card")
            cards_df = pd.DataFrame(list(cards.items()), columns=['Card', 'Amount'])
            if PLOTLY_AVAILABLE:
                fig = px.pie(cards_df, values='Amount', names='Card', 
                            title=f"Spending Distribution - {selected_month}/{selected_year}")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.dataframe(cards_df, use_container_width=True)
    else:
        st.info(f"No data available for {selected_month}/{selected_year}")


def show_enhanced_analysis(analyzer, db):
    """Enhanced analysis page with advanced charts and time filters."""
    st.header("📊 Enhanced Analysis")
    st.write("Advanced spending analysis with interactive charts and time filters.")
    if not PLOTLY_AVAILABLE:
        st.warning("Plotly is not available in this environment. Charts are disabled.")
        st.info("You can still use Fetch Emails and other non-chart features.")
        return
    
    # Time filter
    st.subheader("⏱ Time Period")
    time_filter = st.radio(
        "Select time period",
        ["Last 1 Month", "Last 3 Months", "Last 6 Months", "Last 12 Months", "All Time (2024+)"],
        horizontal=True
    )
    
    # Calculate date range
    today = datetime.now().date()
    if time_filter == "Last 1 Month":
        start_date = today - timedelta(days=30)
        months = 1
    elif time_filter == "Last 3 Months":
        start_date = today - timedelta(days=90)
        months = 3
    elif time_filter == "Last 6 Months":
        start_date = today - timedelta(days=180)
        months = 6
    elif time_filter == "Last 12 Months":
        start_date = today - timedelta(days=365)
        months = 12
    else:  # All Time
        start_date = datetime(2024, 1, 1).date()
        months = None
    
    # Get transactions for the period
    transactions = db.get_transactions(
        start_date=start_date.strftime('%Y-%m-%d'),
        end_date=today.strftime('%Y-%m-%d')
    )
    
    if transactions.empty:
        st.info("No transactions found for the selected period.")
        return
    
    # Add year-month column for grouping
    transactions['date'] = pd.to_datetime(transactions['transaction_date'])
    transactions['year_month'] = transactions['date'].dt.to_period('M').astype(str)
    
    st.divider()
    
    # 1. Bar Chart by Category (Monthly)
    st.subheader("📊 Spending by Category (Monthly)")
    
    # Group by category and month
    category_monthly = transactions.groupby(['category', 'year_month'])['amount'].sum().reset_index()
    category_monthly = category_monthly.sort_values('amount', ascending=True)  # Lowest first
    
    if not category_monthly.empty:
        # Pivot for stacked bar chart
        category_pivot = category_monthly.pivot(index='category', columns='year_month', values='amount').fillna(0)
        
        # Sort categories by total (highest at bottom)
        category_totals = category_pivot.sum(axis=1).sort_values(ascending=True)
        category_pivot = category_pivot.reindex(category_totals.index)
        
        fig = go.Figure()
        for month in category_pivot.columns:
            fig.add_trace(go.Bar(
                name=month,
                x=category_pivot.index,
                y=category_pivot[month],
                orientation='h'
            ))
        
        fig.update_layout(
            title="Monthly Spending by Category (Highest at Bottom)",
            xaxis_title="Amount (₹)",
            yaxis_title="Category",
            barmode='stack',
            height=600,
            yaxis={'categoryorder': 'total ascending'}
        )
        st.plotly_chart(fig, use_container_width=True)
    
    st.divider()
    
    # 2. Pie Chart by Segments
    st.subheader("🥧 Spending Distribution by Category")
    
    category_totals = transactions.groupby('category')['amount'].sum().reset_index()
    category_totals = category_totals.sort_values('amount', ascending=False)
    
    if not category_totals.empty:
        col1, col2 = st.columns([2, 1])
        
        with col1:
            fig = px.pie(
                category_totals,
                values='amount',
                names='category',
                title=f"Spending by Category - {time_filter}"
            )
            fig.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            display_df = category_totals.copy()
            display_df['amount'] = display_df['amount'].apply(lambda x: f"₹{x:,.2f}")
            display_df.columns = ['Category', 'Total']
            st.dataframe(display_df, use_container_width=True, hide_index=True)
    
    st.divider()
    
    # 3. Bar Chart by Credit Card
    st.subheader("💳 Spending by Credit Card")
    
    card_totals = transactions.groupby('card_name')['amount'].agg(['sum', 'count']).reset_index()
    card_totals.columns = ['Card', 'Total Amount', 'Transaction Count']
    card_totals = card_totals.sort_values('Total Amount', ascending=False)
    
    if not card_totals.empty:
        col1, col2 = st.columns([2, 1])
        
        with col1:
            fig = px.bar(
                card_totals,
                x='Card',
                y='Total Amount',
                title=f"Total Spending by Card - {time_filter}",
                text='Total Amount'
            )
            fig.update_traces(texttemplate='₹%{text:,.0f}', textposition='outside')
            fig.update_layout(
                xaxis_title="Credit Card",
                yaxis_title="Total Amount (₹)",
                height=400
            )
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # Format amounts for display
            display_df = card_totals.copy()
            display_df['Total Amount'] = display_df['Total Amount'].apply(lambda x: f"₹{x:,.2f}")
            display_df.columns = ['Card', 'Total', 'Count']
            st.dataframe(display_df, use_container_width=True, hide_index=True)
    
    st.divider()
    
    # 4. Additional Insights
    st.subheader("💡 Additional Insights")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        top_category = category_totals.iloc[0]['category'] if not category_totals.empty else "N/A"
        top_amount = category_totals.iloc[0]['amount'] if not category_totals.empty else 0
        st.metric("Top Category", top_category, delta=f"₹{top_amount:,.2f}")
    
    with col2:
        top_card = card_totals.iloc[0]['Card'] if not card_totals.empty else "N/A"
        top_card_amount = card_totals.iloc[0]['Total Amount'] if not card_totals.empty else 0
        st.metric("Top Card", top_card, delta=f"₹{top_card_amount:,.2f}")
    
    with col3:
        avg_transaction = transactions['amount'].mean()
        st.metric("Avg Transaction", f"₹{avg_transaction:,.2f}")
    
    with col4:
        total_transactions = len(transactions)
        st.metric("Total Transactions", f"{total_transactions:,}")


def show_spending_breakdown(analyzer):
    st.header("💸 Spending Breakdown")
    if not PLOTLY_AVAILABLE:
        st.warning("Plotly is not available in this environment. Charts are disabled.")
        st.info("You can still filter and view tables in other pages.")
        # Continue to allow table views below without charts
    
    # Date range selector
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Start Date", 
                                   value=datetime.now() - timedelta(days=90))
    with col2:
        end_date = st.date_input("End Date", value=datetime.now())
    
    # By Category
    st.subheader("By Category")
    category_spend = analyzer.get_spending_by_category(
        start_date=start_date.strftime('%Y-%m-%d'),
        end_date=end_date.strftime('%Y-%m-%d')
    )
    
    if not category_spend.empty:
        col1, col2 = st.columns(2)
        with col1:
            if PLOTLY_AVAILABLE:
                fig = px.pie(category_spend, values='total_amount', names='category',
                            title="Spending by Category")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.dataframe(category_spend, use_container_width=True)
        with col2:
            st.dataframe(category_spend, use_container_width=True)
    else:
        st.info("No category data available.")
    
    st.divider()
    
    # Top Merchants
    st.subheader("Top Merchants")
    top_merchants = analyzer.get_top_merchants(
        limit=10,
        start_date=start_date.strftime('%Y-%m-%d'),
        end_date=end_date.strftime('%Y-%m-%d')
    )
    
    if not top_merchants.empty:
        if PLOTLY_AVAILABLE:
            fig = px.bar(top_merchants, x='merchant', y='total_amount',
                        title="Top 10 Merchants by Spending")
            fig.update_layout(xaxis_title="Merchant", yaxis_title="Amount (₹)")
            fig.update_xaxes(tickangle=-45)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.dataframe(top_merchants, use_container_width=True)
        st.dataframe(top_merchants, use_container_width=True)
    else:
        st.info("No merchant data available.")


def show_bill_reminders(reminder_system):
    st.header("🔔 Bill Reminders")
    
    reminder_summary = reminder_system.get_reminder_summary()
    
    # Summary cards
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Bills Due (7 days)", reminder_summary['bills_due_7d'],
                 delta=f"₹{reminder_summary['total_due_7d']:,.2f}")
    with col2:
        st.metric("Bills Due (30 days)", reminder_summary['bills_due_30d'],
                 delta=f"₹{reminder_summary['total_due_30d']:,.2f}")
    
    st.divider()
    
    # Upcoming bills
    st.subheader("Upcoming Bills (Next 7 Days)")
    upcoming_bills = reminder_summary['upcoming_bills']
    
    if upcoming_bills:
        bills_df = pd.DataFrame(upcoming_bills)
        bills_df = bills_df[['card_name', 'due_date', 'total_spend', 'payment_status']]
        bills_df.columns = ['Card', 'Due Date', 'Amount', 'Status']
        st.dataframe(bills_df, use_container_width=True)
        
        # Send reminders button
        if st.button("Send Reminders Now"):
            reminder_system.send_reminders()
            st.success("Reminders sent!")
    else:
        st.success("No bills due in the next 7 days! 🎉")


def show_transactions(db):
    st.header("📋 Transaction Review & Management")
    st.write("Review, search, and edit your parsed transactions here.")
    
    # Get all transactions first to get unique cards
    all_transactions = db.get_transactions()
    
    if all_transactions.empty:
        st.info("No transactions found. Fetch emails to get started!")
        return
    
    # Filters Section
    st.subheader("🔍 Filters")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        cards = ["All"] + sorted(all_transactions['card_name'].unique().tolist())
        selected_card = st.selectbox("Card", cards)
    
    with col2:
        # Get date range from data
        min_date = pd.to_datetime(all_transactions['transaction_date']).min().date()
        max_date = pd.to_datetime(all_transactions['transaction_date']).max().date()
        start_date = st.date_input("Start Date", value=max(min_date, datetime.now().date() - timedelta(days=30)), 
                                   min_value=min_date, max_value=max_date)
    
    with col3:
        end_date = st.date_input("End Date", value=max_date, min_value=min_date, max_value=max_date)
    
    with col4:
        categories = ["All"] + sorted([c for c in all_transactions['category'].dropna().unique().tolist() if c])
        selected_category = st.selectbox("Category", categories)
    
    # Search box
    search_term = st.text_input("🔎 Search in descriptions", placeholder="e.g., Swiggy, Amazon, etc.")
    
    # Get filtered transactions
    transactions = db.get_transactions(
        card_name=selected_card if selected_card != "All" else None,
        start_date=start_date.strftime('%Y-%m-%d'),
        end_date=end_date.strftime('%Y-%m-%d')
    )
    
    # Filter by category
    if selected_category != "All":
        transactions = transactions[transactions['category'] == selected_category]
    
    # Filter by search term
    if search_term:
        transactions = transactions[
            transactions['description'].str.contains(search_term, case=False, na=False) |
            transactions['merchant'].str.contains(search_term, case=False, na=False)
        ]
    
    # Summary stats
    if not transactions.empty:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Transactions", len(transactions))
        with col2:
            st.metric("Total Amount", f"₹{transactions['amount'].sum():,.2f}")
        with col3:
            st.metric("Avg Transaction", f"₹{transactions['amount'].mean():,.2f}")
        with col4:
            uncategorized = len(transactions[transactions['category'].isna() | (transactions['category'] == '')])
            st.metric("Uncategorized", uncategorized, delta=f"{uncategorized/len(transactions)*100:.1f}%" if len(transactions) > 0 else "0%")
    
    st.divider()
    
    # Display transactions table
    if not transactions.empty:
        st.subheader("📊 Transaction Table")
        
        # Prepare display dataframe - keep original for editing
        display_df = transactions.copy()
        
        # Select columns to show (all important ones by default)
        available_cols = display_df.columns.tolist()
        important_cols = ['id', 'transaction_date', 'card_name', 'amount', 'description', 'merchant', 'category']
        default_cols = [c for c in important_cols if c in available_cols]
        
        # Show all columns option
        show_all_cols = st.checkbox("Show all columns", value=False)
        
        if show_all_cols:
            display_cols = available_cols
        else:
            display_cols = st.multiselect(
                "Select columns to display",
                options=available_cols,
                default=default_cols
            )
        
        if display_cols:
            # Format for display (but keep original for editing)
            display_formatted = display_df[display_cols].copy()
            if 'transaction_date' in display_formatted.columns:
                display_formatted['transaction_date'] = pd.to_datetime(display_formatted['transaction_date']).dt.strftime('%Y-%m-%d')
            if 'amount' in display_formatted.columns:
                display_formatted['amount'] = display_formatted['amount'].apply(lambda x: f"₹{x:,.2f}")
            
            # Display with better formatting
            st.dataframe(
                display_formatted,
                use_container_width=True,
                height=400
            )
            
            # Edit category section
            st.divider()
            st.subheader("✏️ Edit Categories")
            
            # Get unique uncategorized transactions for quick edit
            uncategorized = transactions[
                (transactions['category'].isna()) | (transactions['category'] == '')
            ]
            
            if not uncategorized.empty:
                st.write(f"**Found {len(uncategorized)} uncategorized transactions**")
                
                # Quick category assignment
                col1, col2 = st.columns([2, 1])
                with col1:
                    config = load_config()
                    available_categories = config.get('categories', [])
                    selected_ids = st.multiselect(
                        "Select transaction IDs to update (showing uncategorized only)",
                        options=uncategorized['id'].tolist(),
                        format_func=lambda x: f"ID {x}: ₹{uncategorized[uncategorized['id']==x]['amount'].iloc[0]:,.2f} - {uncategorized[uncategorized['id']==x]['description'].iloc[0][:60]}"
                    )
                
                with col2:
                    new_category = st.selectbox("New Category", ["Select..."] + available_categories)
                    
                    if st.button("✅ Update Category", type="primary", use_container_width=True):
                        if selected_ids and new_category != "Select...":
                            # Update in database
                            updated = db.update_transactions_category_batch(selected_ids, new_category)
                            if updated > 0:
                                st.success(f"✅ Updated {updated} transactions!")
                                st.rerun()
                            else:
                                st.error("Failed to update transactions")
            
            # Manual edit for any transaction
            st.write("**Or edit individual transaction:**")
            edit_id = st.number_input("Transaction ID", min_value=1, value=1, step=1)
            if edit_id in transactions['id'].values:
                edit_txn = transactions[transactions['id'] == edit_id].iloc[0]
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**Description:** {edit_txn['description']}")
                    st.write(f"**Amount:** ₹{edit_txn['amount']:,.2f}")
                with col2:
                    config = load_config()
                    available_categories = config.get('categories', [])
                    current_cat = edit_txn.get('category', '')
                    new_cat = st.selectbox("Category", ["Select..."] + available_categories, 
                                          index=0 if pd.isna(current_cat) or current_cat == '' else available_categories.index(current_cat) + 1 if current_cat in available_categories else 0)
                    if st.button("Update", type="primary"):
                        if new_cat != "Select...":
                            if db.update_transaction_category(edit_id, new_cat):
                                st.success("✅ Updated!")
                                st.rerun()
        
        # Download button
        st.divider()
        csv = transactions.to_csv(index=False)
        st.download_button(
            label="📥 Download as CSV",
            data=csv,
            file_name=f"transactions_{start_date}_{end_date}.csv",
            mime="text/csv",
            use_container_width=True
        )
    else:
        st.info("No transactions found for the selected filters.")


def show_cost_analyzer(db):
    """Cost Analyzer page showing total expenses including fixed costs."""
    st.header("💰 Cost Analyzer")
    st.write("Track your total monthly expenses including credit card spending and fixed costs.")
    
    cost_analyzer = CostAnalyzer(db)
    
    # Month selector
    col1, col2 = st.columns(2)
    with col1:
        selected_month = st.selectbox("Select Month", range(1, 13), 
                                     index=datetime.now().month - 1)
    with col2:
        selected_year = st.selectbox("Select Year", 
                                    range(2024, datetime.now().year + 2),
                                    index=datetime.now().year - 2024)
    
    # Get monthly total
    monthly_total = cost_analyzer.get_monthly_total(month=selected_month, year=selected_year)
    
    # Summary cards
    st.subheader("📊 Monthly Summary")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Credit Card Spend", f"₹{monthly_total['credit_card_spend']:,.2f}",
                 delta=f"{monthly_total['credit_card_count']} transactions")
    with col2:
        st.metric("Fixed Expenses", f"₹{monthly_total['fixed_expenses']:,.2f}",
                 delta=f"{monthly_total['fixed_expenses_count']} items")
    with col3:
        st.metric("Total Monthly Spend", f"₹{monthly_total['total_spend']:,.2f}",
                 delta=f"₹{monthly_total['total_spend'] - monthly_total['fixed_expenses']:,.2f} variable")
    with col4:
        daily_avg = monthly_total['total_spend'] / 30
        st.metric("Daily Average", f"₹{daily_avg:,.2f}")
    
    st.divider()
    
    # Expense breakdown
    st.subheader("📈 Expense Breakdown")
    breakdown = cost_analyzer.get_expense_breakdown(month=selected_month, year=selected_year)
    
    if not breakdown.empty:
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # Pie chart
            category_totals = breakdown.groupby('Category')['Amount'].sum().reset_index()
            if PLOTLY_AVAILABLE:
                fig = px.pie(
                    category_totals,
                    values='Amount',
                    names='Category',
                    title=f"Total Expenses by Category - {selected_month}/{selected_year}"
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.dataframe(category_totals, use_container_width=True)
        
        with col2:
            # Breakdown table
            display_df = breakdown.copy()
            display_df['Amount'] = display_df['Amount'].apply(lambda x: f"₹{x:,.2f}")
            st.dataframe(display_df, use_container_width=True, hide_index=True)
    
    st.divider()
    
    # Fixed expenses management
    st.subheader("⚙️ Fixed Expenses Management")
    
    fixed_expenses = cost_analyzer.get_fixed_expenses()
    
    if not fixed_expenses.empty:
        st.write("**Current Fixed Expenses:**")
        display_fixed = fixed_expenses[['expense_name', 'amount', 'category']].copy()
        display_fixed.columns = ['Expense', 'Monthly Amount', 'Category']
        display_fixed['Monthly Amount'] = display_fixed['Monthly Amount'].apply(lambda x: f"₹{x:,.2f}")
        st.dataframe(display_fixed, use_container_width=True, hide_index=True)
    
    # Add/Edit fixed expense
    with st.expander("➕ Add/Edit Fixed Expense"):
        col1, col2, col3 = st.columns(3)
        with col1:
            expense_name = st.text_input("Expense Name", placeholder="e.g., Netflix")
        with col2:
            expense_amount = st.number_input("Monthly Amount (₹)", min_value=0.0, value=0.0, step=100.0)
        with col3:
            config = load_config()
            categories = config.get('categories', [])
            expense_category = st.selectbox("Category", categories)
        
        if st.button("Save Fixed Expense", type="primary"):
            if expense_name and expense_amount > 0:
                cost_analyzer.add_fixed_expense(expense_name, expense_amount, expense_category)
                st.success(f"✅ Added {expense_name}: ₹{expense_amount:,.2f}/month")
                st.rerun()
            else:
                st.error("Please fill in all fields")


if __name__ == "__main__":
    main()

