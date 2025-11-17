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
from src.email_fetcher import EmailFetcher
from src.email_parser import EmailParser
from src.transaction_classifier import TransactionClassifier


APP_DEBUG_TAG = "debug-verify-2025-11-18-0355"

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
    st.caption(f"Debug code tag: {APP_DEBUG_TAG}")
    
    db = get_database()
    analyzer = get_analyzer()
    reminder_system = get_reminder_system()
    
    # Sidebar
    st.sidebar.header("Navigation")
    page = st.sidebar.selectbox(
        "Choose a page",
        ["Fetch Emails", "Verify & Backfill", "Overview", "Enhanced Analysis", "Cost Analyzer", "Monthly Analysis", "Spending Breakdown", "Bill Reminders", "Transactions"]
    )
    
    if page == "Fetch Emails":
        show_fetch_emails()
    elif page == "Verify & Backfill":
        show_verify_backfill()
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
            fetch_from_2024 = st.checkbox("Fetch From 2024 Onwards", value=False,
                                         help="For the very first backfill only. Leave unchecked for faster runs.")
        with col2:
            days_back = st.number_input("Days to Look Back", min_value=1, max_value=3650, 
                                       value=45, disabled=fetch_from_2024)

        st.write("")
        col3, col4 = st.columns(2)
        with col3:
            enable_quick = st.checkbox("Quick Mode (limit statements per card)", value=True)
        with col4:
            max_per_card = st.number_input("Limit per card", min_value=1, max_value=24, value=12, step=1,
                                           disabled=not enable_quick)
        
        submitted = st.form_submit_button("🚀 Fetch & Process Emails", use_container_width=True)
    
    if submitted:
        if not email_address or not email_password:
            st.error("Please enter both email address and password.")
        else:
            with st.spinner("Connecting to email and processing statements..."):
                try:
                    from main import fetch_and_process_emails
                    
                    days = None if fetch_from_2024 else days_back
                    result = fetch_and_process_emails(
                        email_address,
                        email_password,
                        days_back=days,
                        max_emails_per_card=(max_per_card if enable_quick else None)
                    )
                    
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

    st.divider()
    st.subheader("🧰 History & Speed Tools")
    with st.expander("Mark history verified (skips old months on future runs)"):
        db = get_database()
        colA, colB = st.columns(2)
        with colA:
            hist_month = st.selectbox("Month", list(range(1, 13)), index=datetime.now().month - 1)
        with colB:
            hist_year = st.number_input("Year", min_value=2024, max_value=datetime.now().year, value=datetime.now().year)
        if st.button("✅ Mark history up to selected month verified", use_container_width=True):
            try:
                ms = db.get_monthly_summaries()
                if ms.empty:
                    st.info("No monthly summaries yet. Run a fetch first.")
                else:
                    updated = 0
                    for _, row in ms.iterrows():
                        y = int(row.get('year'))
                        m = int(row.get('month'))
                        if (y < hist_year) or (y == hist_year and m <= hist_month):
                            comp = float(row.get('computed_total') or row.get('total_spend') or 0.0)
                            db.set_monthly_verification(
                                card_name=row.get('card_name'),
                                month=m,
                                year=y,
                                computed_total=comp,
                                verified=True,
                                verification_diff=0.0
                            )
                            updated += 1
                    st.success(f"Marked {updated} month records as verified. Future runs will skip these months.")
            except Exception as ex:
                st.error(f"Failed to mark history verified: {ex}")


def show_verify_backfill():
    """One-month preview and commit flow, then full backfill.
    Lets you validate parsing before writing to DB.
    """
    st.header("🔎 Verify & Backfill")
    st.write("Preview one month for a specific card, confirm, then backfill history.")

    config = load_config()
    db = get_database()

    # Credentials
    with st.expander("Step 1: Email credentials", expanded=True):
        colA, colB = st.columns(2)
        with colA:
            email_address = st.text_input("Email Address", key="vf_email")
        with colB:
            email_password = st.text_input("App Password", type="password", key="vf_pass")

    # Selection
    with st.expander("Step 2: Select card & month", expanded=True):
        bank_configs = config.get('email', {}).get('bank_emails', []) or []
        cards = [b.get('card_name') for b in bank_configs if b.get('card_name')]
        # Fallback: if no cards in config, try from DB
        if not cards:
            try:
                tx = db.get_transactions()
                if not tx.empty and 'card_name' in tx.columns:
                    cards = sorted([c for c in tx['card_name'].dropna().unique().tolist() if c])
            except Exception:
                pass
        if not cards:
            st.info("No cards configured yet. Add 'email.bank_emails' in config.yaml at repo root to enable selection.")
        card = st.selectbox("Card", cards, disabled=(len(cards) == 0))
        col1, col2 = st.columns(2)
        with col1:
            year = st.number_input("Year", min_value=2024, max_value=datetime.now().year, value=datetime.now().year)
        with col2:
            month = st.selectbox("Month", list(range(1, 13)), index=datetime.now().month-1)

        preview_btn = st.button("👁️ Preview this month (no DB write)")

    if preview_btn:
        if not email_address or not email_password:
            st.error("Enter email + app password first.")
            return

        # Find bank config
        bcfg = next((b for b in config['email'].get('bank_emails', []) if b.get('card_name') == card), None)
        if not bcfg:
            st.error("Card configuration not found.")
            return

        # Compute month bounds
        first = datetime(int(year), int(month), 1).date()
        if int(month) == 12:
            next_first = datetime(int(year)+1, 1, 1).date()
        else:
            next_first = datetime(int(year), int(month)+1, 1).date()
        last = next_first - timedelta(days=1)

        # Fetch emails for the month
        ef = EmailFetcher(
            imap_server=config['email']['imap_server'],
            imap_port=config['email']['imap_port'],
            use_ssl=config['email']['use_ssl']
        )
        with st.spinner("Connecting and fetching emails for selected month..."):
            if not ef.connect(email_address, email_password):
                st.error("Failed to connect to email.")
                return

            # Primary search: use configured sender + subject filters
            # For preview, scan the full month (no max_fetch limit)
            emails = ef.search_emails(
                sender_pattern=bcfg.get('sender_pattern'),
                subject_keywords=bcfg.get('subject_keywords'),
                start_date=first,
                end_date=last,
                max_fetch=None
            )

            # Fallback debug search: date-only, no sender/subject filter
            fallback_emails = []
            if not emails:
                fallback_emails = ef.search_emails(
                    sender_pattern=None,
                    subject_keywords=None,
                    start_date=first,
                    end_date=last,
                    max_fetch=None
                )

            ef.disconnect()

        st.info(f"Found {len(emails)} emails for {card} in {month}/{year}.")

        # Debug: show raw emails and attachments for matched emails
        if emails:
            with st.expander("Debug: emails & attachments"):
                for idx, e in enumerate(emails, start=1):
                    st.write(f"{idx}. {e.get('subject')} ({e.get('date')})")
                    atts = e.get('attachments') or []
                    if atts:
                        st.write("   Attachments:", [a.get('filename') for a in atts])
                    else:
                        st.write("   Attachments: none")

        # Debug: show fallback emails when primary search found none
        if not emails and fallback_emails:
            with st.expander("Debug: fallback emails (date-only search)"):
                for e in fallback_emails:
                    st.write(f"{e.get('date')} | {e.get('from')} | {e.get('subject')}")
        st.caption(f"Debug: pdf_password configured = {'yes' if bcfg.get('pdf_password') else 'no'}")

        # Parse emails (no DB write)
        parser = EmailParser(card, pdf_password=bcfg.get('pdf_password'))
        parsed_transactions = []
        monthly_summary = None
        due_date = None

        emails_with_txns = 0
        emails_without_txns = 0
        parse_errors = []
        raw_text_snippets = []

        for e in emails:
            try:
                pdata = parser.parse_email(e)
            except Exception as ex:
                # Capture error details per email so the user can see why parsing failed
                parse_errors.append({
                    "subject": e.get("subject"),
                    "error": str(ex)
                })
                continue

            txns = pdata.get('transactions') or []
            if txns:
                parsed_transactions.extend(txns)
                emails_with_txns += 1
            else:
                emails_without_txns += 1

            # Capture raw PDF text snippet if available for debug
            if pdata.get('raw_text'):
                raw_text_snippets.append({
                    'subject': e.get('subject'),
                    'raw_text': pdata['raw_text']
                })

            if not monthly_summary and pdata.get('monthly_summary'):
                monthly_summary = pdata['monthly_summary']
            if not due_date and pdata.get('due_date'):
                due_date = pdata['due_date']

        st.subheader("Preview Transactions (not saved yet)")
        st.caption(
            f"Debug: emails fetched={len(emails)}, with transactions={emails_with_txns}, "
            f"without transactions={emails_without_txns}, parse errors={len(parse_errors)}"
        )
        if parse_errors:
            with st.expander("Show parsing errors (for debugging)"):
                for err in parse_errors:
                    st.write(f"Subject: {err.get('subject')}")
                    st.code(err.get('error'))

        if not parsed_transactions and raw_text_snippets:
            with st.expander("Debug: raw PDF text (first 8000 chars)"):
                for snip in raw_text_snippets:
                    st.write(f"Subject: {snip['subject']}")
                    st.code(snip['raw_text'])

        if parsed_transactions:
            # Classify for preview display
            clf = TransactionClassifier()
            classified = clf.classify_batch(parsed_transactions)
            df = pd.DataFrame(classified)
            st.dataframe(df, use_container_width=True, height=350)
            st.info(f"Total parsed: {len(df)} | Amount: ₹{df['amount'].sum():,.2f}")
        else:
            st.warning("No transactions parsed from emails in this month.")
            if monthly_summary:
                st.info("Debug: Statement summary was detected but no transaction rows matched current parsing patterns.")

        if monthly_summary:
            st.write("Statement summary:")
            st.json(monthly_summary)

        # Reset/Commit section
        st.divider()
        colr1, colr2 = st.columns(2)
        with colr1:
            if st.button("♻️ Reset this month (delete + clear processed flags)"):
                try:
                    removed = db.delete_transactions_for_month(card, int(year), int(month))
                    cleared = db.clear_processed_emails_for_month(card, int(year), int(month))
                    st.success(f"Reset done. Deleted {removed} transactions, cleared {cleared} processed flags.")
                except Exception as ex:
                    st.error(f"Reset failed: {ex}")
        with colr2:
            if st.button("🧼 Clear processed flags only (reprocess emails)"):
                try:
                    cleared = db.clear_processed_emails_for_month(card, int(year), int(month))
                    st.success(f"Cleared {cleared} processed flags for this month.")
                except Exception as ex:
                    st.error(f"Failed to clear flags: {ex}")

        st.subheader("Commit this month to database")
        verify_after = st.checkbox("Mark this month verified after save (recommended)", value=True)
        if st.button("💾 Save month to DB"):
            if not parsed_transactions:
                st.error("Nothing to save.")
            else:
                # Write to DB
                try:
                    db.add_transactions_batch(classified)
                    # Update monthly summary
                    if monthly_summary:
                        db.update_monthly_summary(
                            card_name=card,
                            month=int(month),
                            year=int(year),
                            total_spend=float(monthly_summary.get('total_spend', 0)),
                            transaction_count=len(classified),
                            due_date=due_date
                        )
                    # Mark verified
                    if verify_after:
                        from datetime import date
                        start_str = datetime(int(year), int(month), 1).strftime('%Y-%m-%d')
                        end_str = next_first.strftime('%Y-%m-%d')
                        month_df = db.get_transactions(card_name=card, start_date=start_str, end_date=end_str)
                        computed_total = float(month_df['amount'].sum()) if not month_df.empty else 0.0
                        db.set_monthly_verification(card, int(month), int(year), computed_total, True, 0.0)
                    st.success("Saved! You can now backfill history or preview another month.")
                except Exception as ex:
                    st.error(f"Failed to save: {ex}")

    st.divider()
    st.subheader("Step 3: Backfill history (2024+)")
    st.write("After verifying one month works, run the full backfill once.")
    colx, coly = st.columns(2)
    with colx:
        quick_mode = st.checkbox("Quick mode (limit 12 per card)", value=True)
    with coly:
        if st.button("🏁 Run backfill now"):
            if not st.session_state.get('vf_email') or not st.session_state.get('vf_pass'):
                st.error("Provide credentials above first.")
            else:
                with st.spinner("Running backfill... this may take time on first run"):
                    from main import fetch_and_process_emails
                    fetch_and_process_emails(
                        st.session_state.get('vf_email'),
                        st.session_state.get('vf_pass'),
                        days_back=None,
                        max_emails_per_card=(12 if quick_mode else None)
                    )


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

