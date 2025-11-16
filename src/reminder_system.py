"""
Reminder system for bill payment due dates.
Supports email and phone notifications (SMS/Push).
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from src.config_loader import load_config
import requests


class ReminderSystem:
    """Manages bill payment reminders."""
    
    def __init__(self, db, config_path: str = "config.yaml"):
        """Initialize reminder system."""
        self.db = db
        self.config = load_config(config_path)
        self.reminder_config = self.config.get('reminders', {})
    
    def check_upcoming_bills(self, days_ahead: int = 30) -> List[Dict]:
        """Check for bills due within specified days."""
        bills = self.db.get_upcoming_bills(days_ahead=days_ahead)
        return bills.to_dict('records')
    
    def send_reminders(self):
        """Send reminders for upcoming bills based on configuration."""
        if not self.reminder_config.get('enabled', False):
            return
        
        days_before = self.reminder_config.get('days_before_due', [7, 3, 1])
        reminder_email = self.reminder_config.get('reminder_email', '')
        phone_number = self.reminder_config.get('phone_number', '')
        send_sms = self.reminder_config.get('send_sms', False)
        send_push = self.reminder_config.get('send_push', False)
        
        bills = self.check_upcoming_bills(days_ahead=max(days_before))
        
        if not bills:
            return
        
        for bill in bills:
            due_date = datetime.strptime(bill['due_date'], '%Y-%m-%d')
            days_until_due = (due_date - datetime.now()).days
            
            # Check which reminder to send
            for days in days_before:
                if days_until_due == days:
                    # Send email reminder
                    if reminder_email:
                        self._send_email_reminder(bill, days_until_due, reminder_email)
                    
                    # Send SMS reminder
                    if send_sms and phone_number:
                        self.send_sms_reminder(bill, days_until_due, phone_number)
                    
                    # Send push notification
                    if send_push:
                        self.send_push_notification(bill, days_until_due)
                    
                    break
    
    def _send_email_reminder(self, bill: Dict, days_until_due: int, recipient_email: str):
        """Send email reminder for a bill."""
        try:
            subject = f"🔔 Reminder: {bill['card_name']} Bill Due in {days_until_due} days"
            body = f"""
Bill Payment Reminder

Card: {bill['card_name']}
Amount Due: ₹{bill['total_spend']:,.2f}
Due Date: {bill['due_date']}
Days Remaining: {days_until_due}

Please make the payment before the due date to avoid late fees.
            """
            
            # Print reminder (for now)
            print(f"\n{'='*50}")
            print(f"📧 EMAIL REMINDER: {subject}")
            print(body)
            print(f"{'='*50}\n")
            
            # Send email if SMTP configured
            smtp_config = self.config.get('smtp', {})
            if smtp_config.get('enabled', False) and smtp_config.get('server'):
                try:
                    msg = MIMEMultipart()
                    msg['From'] = smtp_config.get('from_email', '')
                    msg['To'] = recipient_email
                    msg['Subject'] = subject
                    msg.attach(MIMEText(body, 'plain'))
                    
                    server = smtplib.SMTP(smtp_config.get('server', ''), 
                                         smtp_config.get('port', 587))
                    server.starttls()
                    server.login(smtp_config.get('username', ''),
                                smtp_config.get('password', ''))
                    server.send_message(msg)
                    server.quit()
                    print(f"✅ Email sent to {recipient_email}")
                except Exception as e:
                    print(f"⚠️ Failed to send email: {e}")
            
        except Exception as e:
            print(f"Error sending reminder email: {e}")
    
    def send_sms_reminder(self, bill: Dict, days_until_due: int, phone_number: str):
        """Send SMS reminder via Twilio (requires Twilio account).
        
        Args:
            bill: Bill dictionary
            days_until_due: Days until due date
            phone_number: Phone number in E.164 format (e.g., +919876543210)
        """
        twilio_config = self.config.get('twilio', {})
        
        if not twilio_config.get('enabled', False):
            return
        
        try:
            from twilio.rest import Client
            
            account_sid = twilio_config.get('account_sid')
            auth_token = twilio_config.get('auth_token')
            from_number = twilio_config.get('from_number')
            
            if not all([account_sid, auth_token, from_number]):
                print("⚠️ Twilio not fully configured")
                return
            
            client = Client(account_sid, auth_token)
            
            message = f"🔔 Bill Reminder: {bill['card_name']} - ₹{bill['total_spend']:,.2f} due in {days_until_due} days. Due: {bill['due_date']}"
            
            client.messages.create(
                body=message,
                from_=from_number,
                to=phone_number
            )
            
            print(f"✅ SMS sent to {phone_number}")
            
        except ImportError:
            print("⚠️ Twilio not installed. Run: pip install twilio")
        except Exception as e:
            print(f"⚠️ Failed to send SMS: {e}")
    
    def send_push_notification(self, bill: Dict, days_until_due: int):
        """Send push notification via Pushover (requires Pushover account).
        
        Args:
            bill: Bill dictionary
            days_until_due: Days until due date
        """
        pushover_config = self.config.get('pushover', {})
        
        if not pushover_config.get('enabled', False):
            return
        
        try:
            api_token = pushover_config.get('api_token')
            user_key = pushover_config.get('user_key')
            
            if not all([api_token, user_key]):
                print("⚠️ Pushover not fully configured")
                return
            
            message = f"🔔 {bill['card_name']} Bill: ₹{bill['total_spend']:,.2f} due in {days_until_due} days"
            
            response = requests.post(
                "https://api.pushover.net/1/messages.json",
                data={
                    "token": api_token,
                    "user": user_key,
                    "message": message,
                    "title": "Bill Payment Reminder",
                    "priority": 1
                }
            )
            
            if response.status_code == 200:
                print(f"✅ Push notification sent")
            else:
                print(f"⚠️ Failed to send push: {response.text}")
                
        except Exception as e:
            print(f"⚠️ Failed to send push notification: {e}")
    
    def get_reminder_summary(self) -> Dict:
        """Get summary of upcoming bills for dashboard."""
        bills_7d = self.check_upcoming_bills(days_ahead=7)
        bills_30d = self.check_upcoming_bills(days_ahead=30)
        
        total_due_7d = sum(bill['total_spend'] for bill in bills_7d)
        total_due_30d = sum(bill['total_spend'] for bill in bills_30d)
        
        return {
            'bills_due_7d': len(bills_7d),
            'total_due_7d': total_due_7d,
            'bills_due_30d': len(bills_30d),
            'total_due_30d': total_due_30d,
            'upcoming_bills': bills_7d
        }

