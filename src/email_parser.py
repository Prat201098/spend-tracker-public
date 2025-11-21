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
        name = (self.card_name or "").upper()

        # Card-specific: HDFC credit cards
        if "HDFC" in name:
            summary = self._extract_hdfc_email_summary(body_text)
            if summary:
                return summary

        # Card-specific: Axis credit cards
        if "AXIS" in name:
            summary = self._extract_axis_email_summary(body_text)
            if summary:
                return summary

        # Card-specific: SBI credit cards
        if "SBI" in name:
            summary = self._extract_sbi_email_summary(body_text)
            if summary:
                return summary

        # Card-specific: YES Bank credit cards
        if "YES" in name:
            summary = self._extract_yes_email_summary(body_text)
            if summary:
                return summary

        # Generic fallback: Look for patterns like
        # "Total: Rs. 12,345.67" or "Amount Due: $1,234.56"
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
        name = (self.card_name or "").upper()

        compact = re.sub(r'\s+', ' ', body_text)

        # HDFC email structure:
        # "Total Amount Due  ... minimum amount due ... payment due date (DD-MM-YYYY)  ₹13.00  ₹13.00  03-12-2025"
        if "HDFC" in name:
            m = re.search(r'Total Amount Due.*?(\d{2}-\d{2}-\d{4})', compact, re.IGNORECASE)
            if m:
                try:
                    date = self._parse_date(m.group(1))
                    return date.strftime('%Y-%m-%d')
                except Exception:
                    pass

        # Axis email structure:
        # "Total Amount Due INR  Minimum Amount Due (INR)  Payment Due Date (DD-MM-YYYY)  3690.15 Cr  0 Cr  08/07/2025"
        if "AXIS" in name:
            m = re.search(r'Total Amount Due\s+INR.*?Payment Due Date\s*\(DD-MM-YYYY\)\s+[\d,\.]+\s+Cr\s+[\d,\.]+\s+Cr\s+(\d{2}/\d{2}/\d{4})', compact, re.IGNORECASE)
            if m:
                try:
                    date = self._parse_date(m.group(1))
                    return date.strftime('%Y-%m-%d')
                except Exception:
                    pass

        # SBI email/PDF structure:
        # e.g. "Total amount due ()  1,16,870.00  Minimum amount due ()  2,391.00  Payment due date  07-Nov-2025"
        # or minor variants. Accept any reasonable date token after the label.
        if "SBI" in name:
            m = re.search(r'Payment\s+Due\s+Date[^0-9A-Za-z]*([0-9A-Za-z/-]+)', compact, re.IGNORECASE)
            if m:
                try:
                    date = self._parse_date(m.group(1))
                    return date.strftime('%Y-%m-%d')
                except Exception:
                    pass

        # YES Bank email structure:
        # "Payment Due Date  04/07/2025"
        if "YES" in name:
            m = re.search(r'Payment Due Date[:\s]+(\d{2}/\d{2}/\d{4})', compact, re.IGNORECASE)
            if m:
                try:
                    date = self._parse_date(m.group(1))
                    return date.strftime('%Y-%m-%d')
                except Exception:
                    pass

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
            'due_date': None,
            'statement_period': None,
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
            
            # Build full text once for card-specific parsing, fallback parsing,
            # and summary/due date extraction.
            text = ""
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"

            # Expose raw text for debugging in the dashboard (truncated)
            if text:
                result["raw_text"] = text[:8000]

            table_parser = PDFTableParser()
            transactions = []

            # Card-specific parsing: HDFC Marriott/Millennia statements often
            # have transactions in a text table under "Domestic Transactions".
            if self._is_hdfc_marriott() and text.strip():
                transactions = self._parse_hdfc_marriott(text, table_parser)

            # Card-specific parsing: Axis Bank credit cards use an "Account
            # Summary" section listing transactions.
            if not transactions and self._is_axis_card() and text.strip():
                transactions = self._parse_axis_statement(text, table_parser)

            # Card-specific parsing: SBI Card (e.g. Vistara) uses a
            # "TRANSACTIONS FOR <NAME>" section for itemized spends.
            if not transactions and self._is_sbi_card() and text.strip():
                transactions = self._parse_sbi_statement(text, table_parser)

            # Card-specific parsing: YES Bank credit cards use a table between
            # "Date Transaction Details Merchant Category Amount (Rs.)" and
            # the "End of the Statement" marker.
            if not transactions and self._is_yes_card() and text.strip():
                transactions = self._parse_yes_statement(text, table_parser)

            # If no card-specific parser matched or returned data, try
            # advanced table parsing on the PDF itself.
            if not transactions:
                transactions = table_parser.parse_pdf_tables(pdf)

            # Generic fallbacks using the extracted text
            if not transactions and text.strip():
                # Parse transactions from PDF text
                transactions = self._parse_from_body(text)

                # Also try table parser on plain text
                if not transactions:
                    transactions = table_parser._parse_text_table(text)

            if transactions:
                result['transactions'] = transactions

            pdf.close()

            if text.strip():
                # Extract summary
                summary = self._extract_monthly_summary(text)
                if summary:
                    result['monthly_summary'] = summary
                    # If the summary itself carries a payment due date
                    # (e.g. from SBI CKYC-based parsing), prefer that
                    # as the PDF-level due date.
                    pdue = summary.get('payment_due_date') if isinstance(summary, dict) else None
                    if pdue:
                        result['due_date'] = pdue

                # Extract due date as a fallback when not already set
                if not result.get('due_date'):
                    due_date = self._extract_due_date(text)
                    if due_date:
                        result['due_date'] = due_date

                # Extract statement period (month/year) from PDF text
                period = self._extract_statement_period(text)
                if period:
                    result['statement_period'] = period
                
        except Exception as e:
            print(f"Error parsing PDF: {e}")
            import traceback
            traceback.print_exc()
        
        return result
    
    def _parse_date(self, date_str: str) -> datetime:
        """Parse various date formats."""
        date_formats = [
            '%d/%m/%Y', '%d-%m-%Y', '%d/%m/%y', '%d-%m-%y',
            '%m/%d/%Y', '%m-%d-%Y', '%Y-%m-%d',
            '%d %b %Y', '%d %B %Y',
            '%d-%b-%Y', '%d-%b-%y',
            '%d %b %y',  # <-- ADD THIS to handle "18 Sep 25"
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

    def _is_hdfc_marriott(self) -> bool:
        """Return True if this parser is for an HDFC statement using the Marriott/Millennia layout."""
        name = (self.card_name or "").upper()
        return "HDFC" in name and ("MARRIOTT" in name or "MILLENNIA" in name)

    def _parse_hdfc_marriott(self, text: str, table_parser: PDFTableParser) -> List[Dict]:
        """Parse HDFC Marriott/Millennia statements from PDF text.

        These statements list transactions in a text table under headings like
        "Domestic Transactions". We isolate that section and then let the
        generic PDFTableParser text parser extract rows. Finally, we drop
        previous-statement payment rows ("BPPY CC PAYMENT ...") and treat
        refunds as credits (negative amounts).
        """
        if not text:
            return []

        lines = [ln.strip() for ln in text.split('\n') if ln.strip()]
        if not lines:
            return []

        # Locate the exact "Domestic Transactions" header
        start_idx = None
        for idx, line in enumerate(lines):
            if line.lower() == 'domestic transactions':
                start_idx = idx
                break

        if start_idx is None:
            return []

        # Advance to the row after the header line that contains "DATE & TIME"
        i = start_idx + 1
        while i < len(lines) and 'date & time' not in lines[i].lower():
            i += 1
        if i < len(lines):
            i += 1  # skip the header row itself

        # Determine the end of the Domestic Transactions section
        end_idx = len(lines)
        for j in range(i, len(lines)):
            lower = lines[j].lower()
            if (
                lower.startswith('note:')
                or 'marriott bonvoy points summary' in lower
                or lower.startswith('gst summary')
                or 'gst summary' in lower
                or lower.startswith('important information')
            ):
                end_idx = j
                break

        region = lines[i:end_idx]
        if not region:
            return []

        rows: List[Dict] = []
        money_re = re.compile(r'[\d,]+\.\d{2}')
        row_re = re.compile(r'^(?P<date>\d{2}/\d{2}/\d{4})\|\s*(?P<time>\d{2}:\d{2})\s+(?P<rest>.+)$')

        for ln in region:
            m = row_re.match(ln)
            if not m:
                continue
            date_str = m.group('date')
            rest = m.group('rest').strip()

            matches = list(re.finditer(money_re, rest))
            if not matches:
                continue
            last = matches[-1]
            amount_str = last.group(0)
            try:
                amount = float(amount_str.replace(',', ''))
            except Exception:
                continue

            merchant = rest[:last.start()].strip()
            if not merchant:
                continue

            desc_upper = merchant.upper()
            # Exclude card bill payment rows entirely
            if 'PAYMENT' in desc_upper:
                continue
            # Keep refunds but make them negative to offset spend
            if 'REFUND' in desc_upper and amount > 0:
                amount = -amount

            try:
                dt = self._parse_date(date_str)
                iso_date = dt.strftime('%Y-%m-%d')
            except Exception:
                # If parsing fails, keep original as best-effort ISO pass-through
                iso_date = date_str

            rows.append({
                'transaction_date': iso_date,
                'description': merchant,
                'merchant': merchant,
                'amount': amount,
            })

        return rows

    def _is_sbi_card(self) -> bool:
        """Return True if this parser is for an SBI credit card."""
        name = (self.card_name or "").upper()
        return "SBI" in name

    def _is_yes_card(self) -> bool:
        """Return True if this parser is for a YES Bank credit card."""
        name = (self.card_name or "").upper()
        return "YES" in name

    def _parse_sbi_statement(self, text: str, table_parser: PDFTableParser) -> List[Dict]:
        """Parse SBI card statements from PDF text.

        SBI statements list spends under a section starting with
        "TRANSACTIONS FOR <NAME>" and ending before the "REWARD SUMMARY" or
        "Important Notes" blocks.

        Each transaction is on a single line, for example:

            18 Sep 25 ZOMATO                  BANGALORE      IND  586.03 D
            18 Sep 25 FARMERS CAFE            MUMBAI         MAH (Pay in EMIs)  3,080.00 D

        where:
          - leading "dd Mon yy" is the transaction date,
          - the middle chunk is the merchant/description,
          - the last numeric is the amount,
          - final "D" or "C" indicates debit/credit.

        We:
          - extract that section,
          - apply a row regex per line,
          - skip "PAYMENT RECEIVED" rows,
          - treat "C" as negative amounts.
        """
        if not text:
            return []

        # Split into non-empty trimmed lines
        lines = [ln.strip() for ln in text.split('\n') if ln.strip()]
        if not lines:
            return []

        # Find the start of the transactions section
        start_idx = None
        for idx, line in enumerate(lines):
            if line.upper().startswith('TRANSACTIONS FOR '):
                start_idx = idx
                break

        if start_idx is None:
            return []

        # Find the end of the transactions section
        end_idx = len(lines)
        for idx in range(start_idx + 1, len(lines)):
            lower = lines[idx].lower()
            if (
                lower.startswith('current stmt period')
                or lower.startswith('reward summary')
                or lower.startswith('important notes')
            ):
                end_idx = idx
                break

        section_lines = lines[start_idx + 1:end_idx]
        if not section_lines:
            return []

        # Drop header row that starts with "Date"
        tx_lines: List[str] = []
        for ln in section_lines:
            if ln.lower().startswith('date'):
                continue
            tx_lines.append(ln)

        # One-line row regex:
        #   <date> <description...> <amount> <D/C>
        row_re = re.compile(
            r'^(?P<date>\d{2}\s+[A-Za-z]{3}\s+\d{2})\s+'
            r'(?P<middle>.+?)\s+'
            r'(?P<amount>[\d,]+\.\d{2})\s+'
            r'(?P<dc>[DC])$'
        )

        rows: List[Dict] = []

        for ln in tx_lines:
            m = row_re.match(ln)
            if not m:
                # Some statements occasionally break a long description onto the next line.
                # If this line does not match the pattern and we already have at least
                # one row, append it as a continuation of the last description.
                if rows:
                    extra = ln.strip()
                    if extra:
                        new_desc = (rows[-1]['description'] + ' ' + extra).strip()
                        rows[-1]['description'] = new_desc
                        rows[-1]['merchant'] = new_desc
                continue

            date_str = m.group('date')
            rest = m.group('middle').strip()
            amount_str = m.group('amount')
            dc_flag = m.group('dc')

            # Normalize spaces in description
            desc = ' '.join(rest.split())
            desc_upper = desc.upper()

            # Skip card bill payment rows
            if desc_upper.startswith('PAYMENT RECEIVED'):
                continue

            # Parse date
            try:
                iso_date = self._parse_date(date_str).strftime('%Y-%m-%d')
            except Exception:
                iso_date = date_str  # fallback: keep original format

            # Parse amount
            try:
                amount = float(amount_str.replace(',', ''))
            except Exception:
                continue

            # Treat credits as negative amounts
            if dc_flag.upper() == 'C':
                amount = -amount

            rows.append({
                'transaction_date': iso_date,
                'description': desc,
                'merchant': desc,
                'amount': amount,
            })

        # If this parser failed to produce any rows, fall back to the generic text-table parser
        if rows:
            return rows

        section_text = '\n'.join(section_lines)
        transactions = table_parser._parse_text_table(section_text)
        cleaned: List[Dict] = []
        for tx in transactions:
            desc = tx.get('description', '') or ''
            if desc.upper().startswith('PAYMENT RECEIVED'):
                continue
            cleaned.append(tx)
        return cleaned

    def _extract_sbi_email_summary(self, body_text: str) -> Optional[Dict]:
        """Extract SBI Total/Minimum Amount Due and payment date.

        Works for both:
        - Email body (usually no summary => returns None)
        - SBI PDF text, where we expect something like:

            Total Amount Due ( ` )
            1,16,870.00
            ...
            Minimum Amount Due( ` )
            ...
            2,391.00
            ...
            Payment Due Date
            ...
            07 Nov 2025

        Preferred approach:
          1. Use a flexible regex over a whitespace-normalized string
             to capture Total, Minimum and Payment Due Date.
          2. Fallback on the CKYC block to at least recover
             Minimum Amount Due and Payment Due Date when labels
             are not easily matched.
        """
        compact = re.sub(r'\s+', ' ', body_text)

        # --- Primary: label-based parsing over the compact text ---
        # Require currency amounts with decimals (e.g. 1,16,870.00), and
        # a "dd Mon yyyy" style date after Payment Due Date.
        m = re.search(
            r'Total\s+Amount\s+Due.*?([\d,]+\.\d{2}).*?'
            r'Minimum\s+Amount\s+Due.*?([\d,]+\.\d{2}).*?'
            r'Payment\s+Due\s+Date.*?(\d{1,2}\s+[A-Za-z]{3}\s+\d{4})',
            compact,
            re.IGNORECASE,
        )
        if m:
            try:
                total_str = m.group(1).replace(',', '')
                min_str = m.group(2).replace(',', '')
                due_raw = m.group(3)

                total_val = float(total_str)
                min_val = float(min_str)
                due_dt = self._parse_date(due_raw)

                return {
                    'total_spend': total_val,
                    'total_due': total_val,
                    'min_due': min_val,
                    'payment_due_date': due_dt.strftime('%Y-%m-%d'),
                }
            except Exception:
                # fall through to CKYC-based parsing
                pass

        # --- Secondary: CKYC-based fallback ---
        #
        # Typical structure near CKYC:
        #   CKYC No. : 20087917895677  2,391.00  ...
        #   Credit Limit( ` )  2,02,000.00 ...
        #   ...
        #   Statement Date 18 Oct 2025 ...
        #   ...
        #   Payment Due Date ... 07 Nov 2025 ...
        #
        # Here:
        #   - first amount after CKYC is Minimum Amount Due (not Total),
        #   - later amounts are credit/cash limits,
        #   - the final "dd Mon yyyy" in this block is Payment Due Date.
        m_ckyc = re.search(r'CKYC\s*No\.\s*:\s*([0-9]{9,})', compact, re.IGNORECASE)
        if not m_ckyc:
            return None

        tail = compact[m_ckyc.end():]

        num_matches = re.findall(r'([\d,]+\.\d{2})', tail)
        date_matches = re.findall(r'(\d{1,2}\s+[A-Za-z]{3}\s+\d{4})', tail)

        min_val: Optional[float] = None
        if num_matches:
            # In practice, first currency amount after CKYC is Minimum Amount Due.
            try:
                min_val = float(num_matches[0].replace(',', ''))
            except Exception:
                min_val = None

        payment_iso: Optional[str] = None
        if date_matches:
            # The last "dd Mon yyyy" in this tail is the Payment Due Date.
            last_date = date_matches[-1]
            try:
                due_dt = self._parse_date(last_date)
                payment_iso = due_dt.strftime('%Y-%m-%d')
            except Exception:
                payment_iso = None

        # If we couldn't identify anything, bail out
        if min_val is None and payment_iso is None:
            return None

        summary: Dict = {
            # We do NOT try to guess total_spend / total_due from CKYC block,
            # as those amounts (credit limits, etc.) are not guaranteed to be
            # the statement due. Leave them None so callers can fall back
            # to computed totals if needed.
            'total_spend': None,
            'total_due': None,
            'min_due': min_val,
        }

        if payment_iso:
            summary['payment_due_date'] = payment_iso

        return summary

    def _extract_yes_email_summary(self, body_text: str) -> Optional[Dict]:
        """Extract YES Bank Total/Minimum Amount Due and payment date.

        Email/PDF summary example:

        Total Amount Due:
        Rs. 400.80
        Minimum Amount Due:
        Rs. 200.00
        Payment Due Date: 04/07/2025
        """
        compact = re.sub(r'\s+', ' ', body_text)

        m = re.search(
            r'Total Amount Due\s*:?\s*Rs\.?\s*([\d,]+\.?\d*)\s*Minimum Amount Due\s*:?\s*Rs\.?\s*([\d,]+\.?\d*)\s*Payment Due Date[:\s]+(NO PYMT REQD|\d{2}/\d{2}/\d{4})',
            compact,
            re.IGNORECASE,
        )
        if not m:
            # Alternative wording used in the long PDF sample: "Total Amount Due"...
            m = re.search(
                r'Total Amount Due\s*:?\s*Rs\.?\s*([\d,]+\.?\d*)\s*Minimum Amount Due\s*:?\s*Rs\.?\s*([\d,]+\.?\d*)\s*Payment Due Date[:\s]+(\d{2}/\d{2}/\d{4})',
                compact,
                re.IGNORECASE,
            )
            if not m:
                return None

        try:
            total_str = m.group(1).replace(',', '')
            min_str = m.group(2).replace(',', '')
            due_raw = m.group(3)

            total_val = float(total_str)
            min_val = float(min_str)

            if due_raw.upper().startswith('NO PYMT REQD'):
                payment_date = None
            else:
                due_dt = self._parse_date(due_raw)
                payment_date = due_dt.strftime('%Y-%m-%d')

            summary: Dict = {
                'total_spend': total_val,
                'total_due': total_val,
                'min_due': min_val,
            }
            if payment_date:
                summary['payment_due_date'] = payment_date

            return summary
        except Exception:
            return None

    def _is_axis_card(self) -> bool:
        """Return True if this parser is for an Axis Bank credit card."""
        name = (self.card_name or "").upper()
        return "AXIS" in name

    def _parse_axis_statement(self, text: str, table_parser: PDFTableParser) -> List[Dict]:
        """Parse Axis Bank credit card statements from PDF text.

        We focus on the "Account Summary" section and extract rows between
        "Account Summary" and "**** End of Statement ****". Payment rows
        like "BBPS PAYMENT RECEIVED" or generic "PAYMENT" rows are treated as
        card-bill payments and excluded.
        """
        if not text:
            return []

        lines = [ln.strip() for ln in text.split('\n') if ln.strip()]
        if not lines:
            return []

        start_idx = None
        for idx, line in enumerate(lines):
            low = line.lower()
            if ('date' in low) and ('amount (rs.)' in low):
                start_idx = idx
                break

        if start_idx is None:
            return []

        end_idx = len(lines)
        for idx in range(start_idx + 1, len(lines)):
            low = lines[idx].lower()
            if 'end of statement' in low or '**** end of statement' in low:
                end_idx = idx
                break

        rows: List[Dict] = []
        row_re = re.compile(r'^(?P<date>\d{2}/\d{2}/\d{4})\s+(?P<middle>.+?)\s+(?P<amount>[\d,]+\.\d{2})\s+(?P<dc>Cr|Dr)\s*$')
        for ln in lines[start_idx + 1:end_idx]:
            if not ln or ln.lower().startswith('card no:'):
                continue
            m = row_re.match(ln)
            if not m:
                continue
            date_str = m.group('date')
            desc = m.group('middle').strip()
            try:
                amount = float(m.group('amount').replace(',', ''))
            except Exception:
                continue
            if m.group('dc') == 'Cr':
                amount = -amount
            if 'PAYMENT' in desc.upper():
                continue
            try:
                iso_date = self._parse_date(date_str).strftime('%Y-%m-%d')
            except Exception:
                iso_date = date_str
            rows.append({
                'transaction_date': iso_date,
                'description': desc,
                'merchant': desc,
                'amount': amount,
            })

        return rows

    def _extract_hdfc_email_summary(self, body_text: str) -> Optional[Dict]:
        """Extract HDFC Total/Minimum Amount Due and payment date from email body.

        Expected compressed pattern (after whitespace normalization):

        Total Amount Due  minimum amount due  payment due date (DD-MM-YYYY)
        ₹13.00  ₹13.00  03-12-2025
        """
        compact = re.sub(r'\s+', ' ', body_text)
        m = re.search(
            r'Total Amount Due\s+minimum amount due\s+payment due date\s*\(DD-MM-YYYY\)\s+[^\d]*([\d,]+\.?\d*)\s+[^\d]*([\d,]+\.?\d*)\s+(\d{2}-\d{2}-\d{4})',
            compact,
            re.IGNORECASE,
        )
        if not m:
            return None

        try:
            total_str = m.group(1).replace(',', '')
            min_str = m.group(2).replace(',', '')
            due_raw = m.group(3)

            total_val = float(total_str)
            min_val = float(min_str)
            due_dt = self._parse_date(due_raw)

            return {
                'total_spend': total_val,
                'total_due': total_val,
                'min_due': min_val,
                'payment_due_date': due_dt.strftime('%Y-%m-%d'),
            }
        except Exception:
            return None

    def _extract_axis_email_summary(self, body_text: str) -> Optional[Dict]:
        """Extract Axis Total/Minimum Payment Due and payment date from email body.

        Expected compressed pattern (after whitespace normalization):

        Total Amount Due INR  Minimum Amount Due (INR)  Payment Due Date (DD-MM-YYYY)
        3690.15 Cr  0 Cr  08/07/2025
        """
        compact = re.sub(r'\s+', ' ', body_text)
        m = re.search(
            r'Total Amount Due\s+INR\s+Minimum Amount Due\s*\(INR\)\s+Payment Due Date\s*\(DD-MM-YYYY\)\s+([\d,]+\.?\d*)\s*(Cr|Dr)?\s+([\d,]+\.?\d*)\s*(Cr|Dr)?\s+(\d{2}/\d{2}/\d{4})',
            compact,
            re.IGNORECASE,
        )
        if not m:
            return None

        try:
            total_str = m.group(1).replace(',', '')
            total_sign = m.group(2) or ''
            min_str = m.group(3).replace(',', '')
            # m.group(4) is min sign (Cr/Dr) but we don't currently use it
            due_raw = m.group(5)

            total_val = float(total_str)
            # Treat Cr as negative (card is in credit), Dr/blank as positive
            if total_sign.strip().lower() == 'cr':
                total_val = -total_val

            min_val = float(min_str)
            due_dt = self._parse_date(due_raw)

            return {
                'total_spend': total_val,
                'total_due': total_val,
                'min_due': min_val,
                'payment_due_date': due_dt.strftime('%Y-%m-%d'),
            }
        except Exception:
            return None

