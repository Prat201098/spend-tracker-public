"""
Main automation script for Spend Tracker.
Fetches emails, parses statements, and updates database.
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
import time

# Add src to path
sys.path.append(str(Path(__file__).parent))

from src.database import SpendDatabase
from src.email_fetcher import EmailFetcher
from src.email_parser import EmailParser
from src.reminder_system import ReminderSystem
from src.transaction_classifier import TransactionClassifier
from src.config_loader import load_config




def fetch_and_process_emails(email_address: str, email_password: str, days_back: int = None):
    """Main function to fetch and process credit card emails.
    
    Args:
        email_address: Email address to connect
        email_password: Email password/app password
        days_back: Number of days to look back (None = all time)
    """
    print("=" * 60)
    print("Prat Spend Analyzer - Email Processing")
    print("=" * 60)
    
    # Load configuration
    config = load_config()
    db = SpendDatabase(config['database']['path'])
    
    # Initialize email fetcher
    email_config = config['email']
    fetcher = EmailFetcher(
        imap_server=email_config['imap_server'],
        imap_port=email_config['imap_port'],
        use_ssl=email_config['use_ssl']
    )
    
    # Connect to email
    print(f"\nConnecting to {email_config['imap_server']}...")
    if not fetcher.connect(email_address, email_password):
        print("Failed to connect to email server. Please check your credentials.")
        return {'success': False, 'error': 'Connection failed'}
    
    print("Connected successfully!\n")
    
    start_time = time.time()
    
    # Use date from 2024-01-01 if days_back is None
    if days_back is None:
        from datetime import date
        start_date = date(2024, 1, 1)
        today = date.today()
        days_back = (today - start_date).days + 1  # From Jan 1, 2024 to today
        print(f"Fetching emails from January 1, 2024 onwards ({days_back} days)")
    
    # Process each bank configuration
    total_transactions = 0
    total_emails_processed = 0
    bank_configs = email_config.get('bank_emails', [])
    total_cards = len(bank_configs)
    card_number = 0
    
    print(f"\nTotal cards to process: {total_cards}\n")
    print("=" * 60)
    
    def _month_bounds(y: int, m: int):
        first = datetime(y, m, 1)
        if m == 12:
            next_month = datetime(y + 1, 1, 1)
        else:
            next_month = datetime(y, m + 1, 1)
        last = next_month - timedelta(days=1)
        return first.strftime('%Y-%m-%d'), last.strftime('%Y-%m-%d')

    for bank_config in bank_configs:
        card_number += 1
        card_start_time = time.time()
        card_name = bank_config['card_name']
        sender_pattern = bank_config['sender_pattern']
        subject_keywords = bank_config['subject_keywords']
        subject_exact = bank_config.get('subject_exact_pattern', '')
        pdf_password = bank_config.get('pdf_password', '')
        
        print(f"\n[{card_number}/{total_cards}] Processing: {card_name}")
        print(f"  Sender pattern: {sender_pattern}")
        print(f"  Started at: {datetime.now().strftime('%H:%M:%S')}")
        
        # Search for emails
        search_start = time.time()
        print(f"  Searching emails...", end='', flush=True)
        emails = fetcher.search_emails(
            sender_pattern=sender_pattern,
            subject_keywords=subject_keywords,
            days_back=days_back
        )
        search_time = time.time() - search_start
        print(f" Done ({search_time:.1f}s)")
        
        # Filter by exact subject pattern if provided
        if subject_exact:
            filter_start = time.time()
            print(f"  Filtering by exact pattern...", end='', flush=True)
            filtered_emails = []
            for email_data in emails:
                subject = email_data.get('subject', '')
                # Check if exact pattern matches (case insensitive, partial match)
                if subject_exact.lower() in subject.lower():
                    filtered_emails.append(email_data)
            emails = filtered_emails
            filter_time = time.time() - filter_start
            print(f" Done ({filter_time:.1f}s)")
            print(f"  ✓ Found {len(emails)} emails matching pattern: {subject_exact[:50]}...")
        else:
            print(f"  ✓ Found {len(emails)} emails")
        
        # Parse each email
        parser = EmailParser(card_name, pdf_password=pdf_password)
        transactions_added = 0
        emails_processed = 0
        total_emails = len(emails)
        
        if total_emails > 0:
            print(f"  Processing {total_emails} emails...")
        
        for idx, email_data in enumerate(emails, 1):
            email_id = email_data.get('id', '')
            email_start_time = time.time()
            
            # Skip if already processed
            if db.is_email_processed(email_id, card_name):
                print(f"  [{idx}/{total_emails}] ⏭ Skipping (already processed): {email_data['subject'][:50]}...")
                continue
            
            print(f"  [{idx}/{total_emails}] 📧 Parsing: {email_data['subject'][:50]}...", end='', flush=True)
            
            try:
                parsed_data = parser.parse_email(email_data)

                # Determine statement period (fallback to transactions if missing)
                period = parsed_data.get('statement_period') or {}
                if not period:
                    txns = parsed_data.get('transactions', [])
                    if txns:
                        try:
                            last_txn_date = max([
                                datetime.strptime(t.get('transaction_date'), '%Y-%m-%d')
                                for t in txns if t.get('transaction_date')
                            ])
                            period = {'month': last_txn_date.month, 'year': last_txn_date.year}
                        except Exception:
                            period = {}

                # If this month is already verified, skip adding data but mark email processed
                if period and db.monthly_verified(card_name, period['month'], period['year']):
                    print(f"  [{idx}/{total_emails}] ✅ Month verified {period['month']}/{period['year']}. Skipping (marking email processed).", end='')
                    email_date = email_data.get('date')
                    email_date_str = email_date.strftime('%Y-%m-%d') if email_date else None
                    db.mark_email_processed(email_id, card_name, email_data.get('subject'), email_date_str)
                    emails_processed += 1
                    email_time = time.time() - email_start_time
                    print(f" ({email_time:.1f}s)")
                    continue
                
                # Auto-classify transactions
                if parsed_data['transactions']:
                    classifier = TransactionClassifier()
                    classified_transactions = classifier.classify_batch(parsed_data['transactions'])
                    parsed_data['transactions'] = classified_transactions
                
                # Add transactions
                if parsed_data['transactions']:
                    db.add_transactions_batch(parsed_data['transactions'])
                    transactions_added += len(parsed_data['transactions'])
                    auto_classified = sum(1 for t in parsed_data['transactions'] if t.get('auto_classified'))
                    if auto_classified > 0:
                        print(f" ✓ {len(parsed_data['transactions'])} transactions ({auto_classified} auto-classified)", end='')
                    else:
                        print(f" ✓ {len(parsed_data['transactions'])} transactions", end='')
                else:
                    print(f" ⚠ No transactions found", end='')
                
                # Update monthly summary
                if parsed_data['monthly_summary']:
                    summary = parsed_data['monthly_summary']
                    # period may have been determined earlier
                    if period:
                        db.update_monthly_summary(
                            card_name=card_name,
                            month=period.get('month', datetime.now().month),
                            year=period.get('year', datetime.now().year),
                            total_spend=summary.get('total_spend', 0),
                            transaction_count=len(parsed_data['transactions']),
                            due_date=parsed_data.get('due_date')
                        )

                        # Verification: compare DB computed total vs statement total
                        start_str, end_str = _month_bounds(period['year'], period['month'])
                        month_df = db.get_transactions(
                            card_name=card_name,
                            start_date=start_str,
                            end_date=end_str
                        )
                        computed_total = float(month_df['amount'].sum()) if not month_df.empty else 0.0
                        reported_total = float(summary.get('total_spend') or 0.0)
                        diff = round(computed_total - reported_total, 2)
                        verified = abs(diff) <= 1.0
                        db.set_monthly_verification(
                            card_name=card_name,
                            month=period['month'],
                            year=period['year'],
                            computed_total=computed_total,
                            verified=verified,
                            verification_diff=diff
                        )
                        if verified:
                            print(f" ✓ Verified {period['month']}/{period['year']} (db={computed_total:.2f}, stmt={reported_total:.2f})", end='')
                        else:
                            print(f" ⚠ Mismatch {period['month']}/{period['year']} (db={computed_total:.2f}, stmt={reported_total:.2f}, diff={diff:.2f})", end='')
                
                # Mark email as processed
                email_date = email_data.get('date')
                email_date_str = email_date.strftime('%Y-%m-%d') if email_date else None
                db.mark_email_processed(
                    email_id, 
                    card_name, 
                    email_data.get('subject'),
                    email_date_str
                )
                emails_processed += 1
                
                email_time = time.time() - email_start_time
                print(f" ({email_time:.1f}s)")
                
            except Exception as e:
                email_time = time.time() - email_start_time
                print(f" ✗ ERROR after {email_time:.1f}s: {e}")
                import traceback
                print(f"    Details: {traceback.format_exc()[:200]}...")
                continue
        
        total_transactions += transactions_added
        total_emails_processed += emails_processed
        card_time = time.time() - card_start_time
        minutes = int(card_time // 60)
        seconds = int(card_time % 60)
        print(f"  ✅ Completed: {transactions_added} transactions from {emails_processed} emails")
        print(f"  ⏱ Time taken: {minutes}m {seconds}s")
        print("-" * 60)
    
    # Disconnect
    fetcher.disconnect()
    
    total_time = time.time() - start_time
    total_minutes = int(total_time // 60)
    total_seconds = int(total_time % 60)
    
    print("\n" + "=" * 60)
    print("🎉 PROCESSING COMPLETE!")
    print("=" * 60)
    print(f"  Total transactions added: {total_transactions}")
    print(f"  Total emails processed: {total_emails_processed}")
    print(f"  Total time: {total_minutes}m {total_seconds}s")
    print(f"  Average per card: {total_time/total_cards:.1f}s")
    print("=" * 60)
    
    # Check and send reminders
    print("\nChecking bill reminders...")
    reminder_system = ReminderSystem(db)
    reminder_system.send_reminders()
    
    return {
        'success': True,
        'transactions_added': total_transactions,
        'emails_processed': total_emails_processed
    }


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Spend Tracker Automation')
    parser.add_argument('--email', type=str, help='Email address')
    parser.add_argument('--password', type=str, help='Email password')
    parser.add_argument('--days', type=int, default=None, 
                       help='Number of days to look back for emails (default: None = all time)')
    
    args = parser.parse_args()
    
    # Get credentials
    email_address = args.email
    email_password = args.password
    
    if not email_address:
        email_address = input("Enter your email address: ")
    
    if not email_password:
        import getpass
        email_password = getpass.getpass("Enter your email password: ")
    
    # Run automation
    fetch_and_process_emails(email_address, email_password, days_back=args.days)


if __name__ == "__main__":
    main()

