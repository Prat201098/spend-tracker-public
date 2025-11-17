"""
Email fetcher module for retrieving credit card statement emails.
Supports IMAP for most email providers.
"""

import imaplib
import email
from email.header import decode_header
from email.utils import parsedate_to_datetime
from typing import List, Dict, Optional
from datetime import datetime, timedelta, date as date_cls
import re


class EmailFetcher:
    """Fetches emails from IMAP server."""
    
    def __init__(self, imap_server: str, imap_port: int = 993, use_ssl: bool = True):
        """Initialize email fetcher with IMAP settings."""
        self.imap_server = imap_server
        self.imap_port = imap_port
        self.use_ssl = use_ssl
        self.connection = None
    
    def connect(self, email_address: str, password: str):
        """Connect to IMAP server."""
        try:
            if self.use_ssl:
                self.connection = imaplib.IMAP4_SSL(self.imap_server, self.imap_port)
            else:
                self.connection = imaplib.IMAP4(self.imap_server, self.imap_port)
            
            self.connection.login(email_address, password)
            # For Gmail, select 'All Mail' so archived statements are also visible
            try:
                if 'gmail' in self.imap_server.lower():
                    self.connection.select('[Gmail]/All Mail')
                else:
                    self.connection.select('INBOX')
            except Exception:
                # Fallback to INBOX if special folder selection fails
                try:
                    self.connection.select('INBOX')
                except Exception:
                    pass
            return True
        except Exception as e:
            print(f"Error connecting to email: {e}")
            return False
    
    def disconnect(self):
        """Close IMAP connection."""
        if self.connection:
            try:
                self.connection.close()
                self.connection.logout()
            except:
                pass
    
    def _decode_header(self, header_value):
        """Decode email header values."""
        if header_value is None:
            return ""
        
        decoded_parts = decode_header(header_value)
        decoded_string = ""
        for part, encoding in decoded_parts:
            if isinstance(part, bytes):
                decoded_string += part.decode(encoding or 'utf-8', errors='ignore')
            else:
                decoded_string += part
        return decoded_string
    
    def search_emails(self, sender_pattern: str = None, subject_keywords: List[str] = None,
                     days_back: int = 30, max_fetch: int = None,
                     start_date: Optional[date_cls] = None, end_date: Optional[date_cls] = None) -> List[Dict]:
        """Search for emails matching criteria."""
        if not self.connection:
            return []
        
        try:
            # Build search criteria - use simpler IMAP syntax
            def _build_criteria(include_sender: bool = True):
                criteria = []
                # Date filter
                if start_date:
                    since = start_date
                else:
                    since = (datetime.now() - timedelta(days=days_back)).date()
                since_str = since.strftime("%d-%b-%Y")
                criteria.append(f'SINCE {since_str}')

                if end_date:
                    before_str = (end_date + timedelta(days=1)).strftime("%d-%b-%Y")
                    criteria.append(f'BEFORE {before_str}')

                # Sender filter - IMAP FROM expects the domain part
                if include_sender and sender_pattern:
                    domain = sender_pattern.lstrip('@')
                    criteria.append(f'FROM {domain}')
                return criteria

            # First try with sender filter (if provided)
            search_criteria = _build_criteria(include_sender=True)
            search_query = ' '.join(search_criteria)
            status, messages = self.connection.search(None, search_query)
            if status != 'OK':
                print(f"IMAP search failed: {messages}")
                return []

            email_ids = messages[0].split()

            # Fallback: if nothing found and we had a sender_pattern, retry with date-only criteria
            if sender_pattern and not email_ids:
                fb_criteria = _build_criteria(include_sender=False)
                fb_query = ' '.join(fb_criteria)
                status_fb, messages_fb = self.connection.search(None, fb_query)
                if status_fb == 'OK':
                    email_ids = messages_fb[0].split()
            # Limit to the most recent N IDs to speed up processing, if requested
            if max_fetch and len(email_ids) > max_fetch:
                email_ids = email_ids[-max_fetch:]
            emails = []
            
            # Filter by subject keywords in Python (more reliable than IMAP SUBJECT)
            for email_id in email_ids:
                try:
                    status, msg_data = self.connection.fetch(email_id, '(RFC822)')
                    if status == 'OK':
                        raw_email = msg_data[0][1]
                        email_message = email.message_from_bytes(raw_email)
                        
                        subject = self._decode_header(email_message['Subject'])
                        subject_lower = subject.lower()
                        # Normalize whitespace to handle non-breaking spaces / multiple spaces
                        subject_norm = re.sub(r"\s+", " ", subject_lower).strip()
                        from_addr = self._decode_header(email_message['From']).lower()
                        
                        # Check if subject matches configured keywords
                        matches_subject = True
                        if subject_keywords:
                            norm_keywords = [
                                re.sub(r"\s+", " ", kw.lower()).strip()
                                for kw in subject_keywords
                            ]
                            matches_subject = any(
                                kw in subject_norm for kw in norm_keywords
                            )
                        
                        # Check if sender matches pattern
                        matches_sender = True
                        if sender_pattern:
                            domain = sender_pattern.lstrip('@').lower()
                            matches_sender = domain in from_addr
                        
                        # Only include if both match
                        if matches_subject and matches_sender:
                            try:
                                parsed_date = parsedate_to_datetime(email_message['Date']) if email_message['Date'] else None
                            except Exception:
                                parsed_date = None
                            email_data = {
                                'id': email_id.decode(),
                                'subject': self._decode_header(email_message['Subject']),
                                'from': self._decode_header(email_message['From']),
                                'date': parsed_date,
                                'body': self._get_email_body(email_message),
                                'attachments': self._get_attachments(email_message)
                            }
                            emails.append(email_data)
                except Exception as e:
                    print(f"Error processing email {email_id}: {e}")
                    continue
            
            return emails
            
        except Exception as e:
            print(f"Error searching emails: {e}")
            return []
    
    def _get_email_body(self, email_message) -> str:
        """Extract email body text."""
        body = ""
        
        if email_message.is_multipart():
            for part in email_message.walk():
                content_type = part.get_content_type()
                if content_type == "text/plain":
                    try:
                        body += part.get_payload(decode=True).decode('utf-8', errors='ignore')
                    except:
                        pass
        else:
            try:
                body = email_message.get_payload(decode=True).decode('utf-8', errors='ignore')
            except:
                pass
        
        return body
    
    def _get_attachments(self, email_message) -> List[Dict]:
        """Extract email attachments."""
        attachments = []
        
        if email_message.is_multipart():
            for part in email_message.walk():
                if part.get_content_disposition() == 'attachment':
                    filename = part.get_filename()
                    if filename:
                        filename = self._decode_header(filename)
                        attachments.append({
                            'filename': filename,
                            'content_type': part.get_content_type(),
                            'payload': part.get_payload(decode=True)
                        })
        
        return attachments

