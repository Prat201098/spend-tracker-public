"""
Advanced PDF table parser for credit card statements.
Detects table structures and extracts transactions with flexible column mapping.
"""

import re
from typing import List, Dict, Optional
from datetime import datetime
import pdfplumber


class PDFTableParser:
    """Parses PDF tables to extract transaction data with flexible column detection."""
    
    def __init__(self):
        """Initialize parser."""
        self.date_patterns = [
            r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}',
            r'\d{1,2}\s+\w{3}\s+\d{4}',
            r'\d{1,2}\s+\w+\s+\d{4}',
        ]
        self.amount_patterns = [
            r'[\d,]+\.?\d{0,2}',
            r'₹\s*[\d,]+\.?\d{0,2}',
            r'INR\s*[\d,]+\.?\d{0,2}',
        ]
    
    def parse_pdf_tables(self, pdf) -> List[Dict]:
        """Extract transactions from PDF tables.
        
        Args:
            pdf: pdfplumber PDF object
        
        Returns:
            List of transaction dictionaries
        """
        all_transactions = []
        
        for page_num, page in enumerate(pdf.pages):
            # Try to extract tables
            tables = page.extract_tables()
            
            if tables:
                for table in tables:
                    transactions = self._parse_table(table)
                    all_transactions.extend(transactions)
            
            # If no tables found, try text-based parsing
            if not tables:
                text = page.extract_text()
                if text:
                    transactions = self._parse_text_table(text)
                    all_transactions.extend(transactions)
        
        return all_transactions
    
    def _parse_table(self, table: List[List]) -> List[Dict]:
        """Parse a table structure to extract transactions."""
        transactions = []
        
        if not table or len(table) < 2:
            return transactions
        
        # First row is usually headers
        headers = [str(cell).strip().lower() if cell else '' for cell in table[0]]
        
        # Detect column indices
        date_col = self._find_column(headers, ['date', 'transaction date', 'tran date', 'posting date'])
        desc_col = self._find_column(headers, ['description', 'merchant', 'particulars', 'details', 'narration'])
        amount_col = self._find_column(headers, ['amount', 'debit', 'credit', 'transaction amount', 'value'])
        points_col = self._find_column(headers, ['points', 'reward', 'rewards'])
        category_col = self._find_column(headers, ['category', 'classification', 'type', 'mcc'])
        
        # If columns not found, try to detect by content
        if date_col is None or desc_col is None or amount_col is None:
            date_col, desc_col, amount_col = self._detect_columns_by_content(table[1:5])  # Check first few rows
        
        # Parse data rows
        for row in table[1:]:
            if not row or len(row) < 3:
                continue
            
            try:
                # Extract date
                date_str = None
                if date_col is not None and date_col < len(row):
                    date_str = str(row[date_col]).strip() if row[date_col] else None
                
                # Extract description
                description = None
                if desc_col is not None and desc_col < len(row):
                    description = str(row[desc_col]).strip() if row[desc_col] else None
                
                # Extract amount
                amount = None
                if amount_col is not None and amount_col < len(row):
                    amount_str = str(row[amount_col]).strip() if row[amount_col] else None
                    if amount_str:
                        amount = self._parse_amount(amount_str)
                
                # Extract points
                points = None
                if points_col is not None and points_col < len(row):
                    points_str = str(row[points_col]).strip() if row[points_col] else None
                    if points_str:
                        points = self._parse_amount(points_str)
                
                # Extract category/classification
                classification = None
                if category_col is not None and category_col < len(row):
                    classification = str(row[category_col]).strip() if row[category_col] else None
                
                # Validate transaction
                if date_str and description and amount is not None:
                    date = self._parse_date(date_str)
                    if date:
                        transactions.append({
                            'transaction_date': date.strftime('%Y-%m-%d'),
                            'description': description,
                            'amount': amount,
                            'merchant': description[:50],
                            'points': points,
                            'classification': classification
                        })
            except Exception as e:
                continue
        
        return transactions
    
    def _parse_text_table(self, text: str) -> List[Dict]:
        """Parse transactions from unstructured text."""
        transactions = []
        lines = text.split('\n')
        
        for line in lines:
            line = line.strip()
            if len(line) < 10:
                continue
            
            # Look for date pattern
            date_match = re.search(r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', line)
            if not date_match:
                continue
            
            date_str = date_match.group(1)
            
            # Look for amount (usually at end or after description)
            amount_match = re.search(r'([\d,]+\.?\d{0,2})', line)
            if not amount_match:
                continue
            
            # Extract description (between date and amount)
            date_end = date_match.end()
            amount_start = amount_match.start()
            description = line[date_end:amount_start].strip()
            
            if description and len(description) > 3:
                try:
                    date = self._parse_date(date_str)
                    amount = self._parse_amount(amount_match.group(1))
                    
                    if date and amount is not None:
                        transactions.append({
                            'transaction_date': date.strftime('%Y-%m-%d'),
                            'description': description,
                            'amount': amount,
                            'merchant': description[:50]
                        })
                except:
                    continue
        
        return transactions
    
    def _find_column(self, headers: List[str], keywords: List[str]) -> Optional[int]:
        """Find column index by header keywords."""
        for idx, header in enumerate(headers):
            for keyword in keywords:
                if keyword in header:
                    return idx
        return None
    
    def _detect_columns_by_content(self, sample_rows: List[List]) -> tuple:
        """Detect column indices by analyzing content."""
        if not sample_rows:
            return None, None, None
        
        date_col = None
        desc_col = None
        amount_col = None
        
        # Analyze first few rows
        for row in sample_rows[:3]:
            if not row:
                continue
            
            for idx, cell in enumerate(row):
                if not cell:
                    continue
                
                cell_str = str(cell).strip()
                
                # Check if it's a date
                if date_col is None and re.match(r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}', cell_str):
                    date_col = idx
                
                # Check if it's an amount
                if amount_col is None and re.match(r'[\d,]+\.?\d{0,2}', cell_str.replace(',', '')):
                    try:
                        float(cell_str.replace(',', ''))
                        amount_col = idx
                    except:
                        pass
                
                # Description is usually the longest text field
                if desc_col is None and len(cell_str) > 10 and not re.match(r'^[\d,\.]+$', cell_str):
                    desc_col = idx
        
        return date_col, desc_col, amount_col
    
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse various date formats."""
        date_formats = [
            '%d/%m/%Y', '%d-%m-%Y', '%d/%m/%y', '%d-%m-%y',
            '%m/%d/%Y', '%m-%d-%Y', '%Y-%m-%d',
            '%d %b %Y', '%d %B %Y', '%d-%b-%Y', '%d-%B-%Y'
        ]
        
        date_str = date_str.strip()
        
        for fmt in date_formats:
            try:
                return datetime.strptime(date_str, fmt)
            except:
                continue
        
        return None
    
    def _parse_amount(self, amount_str: str) -> Optional[float]:
        """Parse amount string to float."""
        if not amount_str:
            return None
        
        # Remove currency symbols and spaces
        amount_str = re.sub(r'[₹$€£,\s]', '', str(amount_str))
        
        # Handle negative amounts
        is_negative = amount_str.startswith('-') or amount_str.startswith('(')
        amount_str = amount_str.replace('(', '').replace(')', '').replace('-', '')
        
        try:
            amount = float(amount_str)
            return -amount if is_negative else amount
        except:
            return None

