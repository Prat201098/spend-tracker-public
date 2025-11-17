"""
Email parser module for extracting spend data from credit card statement emails.
Handles both email body text and PDF attachments.
"""

import re
from datetime import datetime
from typing import List, Dict, Optional
import pdfplumber
import io
from src.pdf_table_parser import PDFTableParser


class EmailParser:
    """Parses credit card statement emails to extract transaction data."""
    
    def __init__(self, card_name: str, pdf_password: str = None):
        """Initialize parser for a specific card."""
        self.card_name = card_name
        self.pdf_password = pdf_password
    
    def parse_email(self, email_data: Dict) -> Dict:
        """Parse email to extract spend information."""
        result = {
            'card_name': self.card_name,
            'transactions': [],
            'monthly_summary': None,
            'due_date': None,
            'statement_period': None
        }
        
        # Try parsing from email body first
        body_text = email_data.get('body', '')
        if body_text:
            transactions = self._parse_from_body(body_text)
            if transactions:
                result['transactions'] = transactions
            
            # Extract monthly summary
            summary = self._extract_monthly_summary(body_text)
            if summary:
                result['monthly_summary'] = summary
            
            # Extract due date
            due_date = self._extract_due_date(body_text)
            if due_date:
                result['due_date'] = due_date
            
            # Extract statement period
            period = self._extract_statement_period(body_text)
            if period:
                result['statement_period'] = period
        
        # Try parsing from PDF attachments
        attachments = email_data.get('attachments', [])
        for attachment in attachments:
            if attachment['filename'].lower().endswith('.pdf'):
                pdf_data = self._parse_pdf(attachment['payload'])
                if pdf_data:
                    if pdf_data.get('transactions'):
                        result['transactions'].extend(pdf_data['transactions'])
                    if pdf_data.get('monthly_summary') and not result['monthly_summary']:
                        result['monthly_summary'] = pdf_data['monthly_summary']
                    if pdf_data.get('due_date') and not result['due_date']:
                        result['due_date'] = pdf_data['due_date']
        
        return result
    
    def _parse_from_body(self, body_text: str) -> List[Dict]:
        """Parse transactions from email body text."""
        transactions = []
        
        # Common patterns for transaction extraction
        # Pattern 1: Date, Description, Amount (supports negatives and parentheses for credits)
        pattern1 = r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\s+(.+?)\s+(-?[\d,]+\.?\d*|\([\d,]+\.?\d*\))'
        
        # Pattern 2 (unused for now): Amount, Date, Description
        pattern2 = r'(-?[\d,]+\.?\d*|\([\d,]+\.?\d*\))\s+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\s+(.+?)'
        
        lines = body_text.split('\n')
        for line in lines:
            line = line.strip()
            if not line or len(line) < 10:
                continue
            
            # Try pattern 1
            match = re.search(pattern1, line)
            if match:
                date_str, desc, amount_str = match.groups()
                try:
                    date = self._parse_date(date_str)
                    amount = self._parse_amount(amount_str)
                    transactions.append({
                        'transaction_date': date.strftime('%Y-%m-%d'),
                        'description': desc.strip(),
                        'amount': amount,
                        'merchant': desc.strip()[:50]  # First 50 chars as merchant
                    })
                except:
                    pass
        
        return transactions
    
    def _extract_monthly_summary(self, body_text: str) -> Optional[Dict]:
        """Extract monthly total spend from email body."""
        # Look for patterns like "Total: Rs. 12,345.67" or "Amount Due: $1,234.56"
        patterns = [
            r'(?:total|amount due|outstanding|balance)[:\s]+(?:rs\.?|inr|usd|\$)?\s*([\d,]+\.?\d*)',
            r'([\d,]+\.?\d*)\s*(?:total|amount due|outstanding)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, body_text, re.IGNORECASE)
            if match:
                try:
                    amount_str = match.group(1).replace(',', '')
                    return {'total_spend': float(amount_str)}
                except:
                    pass
        
        return None
    
    def _extract_due_date(self, body_text: str) -> Optional[str]:
        """Extract payment due date from email body."""
        patterns = [
            r'due date[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
            r'pay by[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
            r'payment due[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, body_text, re.IGNORECASE)
            if match:
                try:
                    date = self._parse_date(match.group(1))
                    return date.strftime('%Y-%m-%d')
                except:
                    pass
        
        return None
    
    def _extract_statement_period(self, body_text: str) -> Optional[Dict]:
        """Extract statement period (month/year) from email."""
        # Look for month names or date ranges
        month_patterns = {
            'january': 1, 'february': 2, 'march': 3, 'april': 4,
            'may': 5, 'june': 6, 'july': 7, 'august': 8,
            'september': 9, 'october': 10, 'november': 11, 'december': 12
        }
        
        current_year = datetime.now().year
        
        for month_name, month_num in month_patterns.items():
            if month_name in body_text.lower():
                return {'month': month_num, 'year': current_year}
        
        # Try date range pattern
        date_range_pattern = r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\s*to\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})'
        match = re.search(date_range_pattern, body_text, re.IGNORECASE)
        if match:
            try:
                end_date = self._parse_date(match.group(2))
                return {'month': end_date.month, 'year': end_date.year}
            except:
                pass
        
        return None
    
    def _parse_pdf(self, pdf_bytes: bytes) -> Optional[Dict]:
        """Parse PDF attachment to extract transaction data."""
        result = {
            'transactions': [],
            'monthly_summary': None,
            'due_date': None
        }
        
        try:
            pdf_file = io.BytesIO(pdf_bytes)
            
            # Try to open PDF with password if provided
            try:
                if self.pdf_password:
                    pdf = pdfplumber.open(pdf_file, password=self.pdf_password)
                else:
                    pdf = pdfplumber.open(pdf_file)
            except Exception as e:
                # If password fails, try without password
                try:
                    pdf_file.seek(0)  # Reset file pointer
                    pdf = pdfplumber.open(pdf_file)
                except:
                    print(f"Error opening PDF (may be password protected): {e}")
                    return result
            
            # Try advanced table parsing first
            table_parser = PDFTableParser()
            transactions = table_parser.parse_pdf_tables(pdf)
            
            # If table parsing didn't work, fall back to text parsing
            if not transactions:
                text = ""
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"

                # Expose raw text for debugging in the dashboard (truncated)
                if text:
                    result["raw_text"] = text[:8000]

                if text.strip():
                    # Parse transactions from PDF text
                    transactions = self._parse_from_body(text)

                    # Also try table parser on text
                    if not transactions:
                        transactions = table_parser._parse_text_table(text)
            
            if transactions:
                result['transactions'] = transactions
            
            # Extract summary and due date from text
            text = ""
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
            
            pdf.close()
            
            if text.strip():
                # Extract summary
                summary = self._extract_monthly_summary(text)
                if summary:
                    result['monthly_summary'] = summary
                
                # Extract due date
                due_date = self._extract_due_date(text)
                if due_date:
                    result['due_date'] = due_date
                
        except Exception as e:
            print(f"Error parsing PDF: {e}")
            import traceback
            traceback.print_exc()
        
        return result
    
    def _parse_date(self, date_str: str) -> datetime:
        """Parse various date formats."""
        date_formats = [
            '%d/%m/%Y', '%d-%m-%Y', '%d/%m/%y', '%d-%m-%y',
            '%m/%d/%Y', '%m-%d-%Y', '%Y-%m-%d', '%d %b %Y',
            '%d %B %Y'
        ]
        
        for fmt in date_formats:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except:
                continue
        
        # If no format matches, return today
        return datetime.now()

    def _parse_amount(self, amount_str: str) -> Optional[float]:
        """Parse amount string (supports negatives and parentheses)."""
        if not amount_str:
            return None
        s = str(amount_str)
        s = re.sub(r'[₹$€£,\s]', '', s)
        is_negative = s.startswith('-') or s.startswith('(')
        s = s.replace('(', '').replace(')', '').replace('-', '')
        try:
            val = float(s)
            return -val if is_negative else val
        except:
            return None

