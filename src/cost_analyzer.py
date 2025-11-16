"""
Cost Analyzer module for tracking fixed expenses and total monthly costs.
"""

import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional
import sqlite3
from src.config_loader import load_config


class CostAnalyzer:
    """Analyzes total costs including credit card spending and fixed expenses."""
    
    def __init__(self, db, config_path: str = "config.yaml"):
        """Initialize cost analyzer.
        Note: config_path is kept for compatibility but values are loaded via load_config()
        which supports Streamlit Secrets overlay when available.
        """
        self.db = db
        self.config = load_config(config_path)
        self._create_fixed_expenses_table()
        self._load_default_expenses()
    
    def _create_fixed_expenses_table(self):
        """Create fixed expenses table if it doesn't exist."""
        conn = sqlite3.connect(self.db.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS fixed_expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                expense_name TEXT NOT NULL,
                amount REAL NOT NULL,
                category TEXT,
                start_date DATE,
                end_date DATE,
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        conn.close()
    
    def _load_default_expenses(self):
        """Load default fixed expenses from config or create them."""
        default_expenses = self.config.get('fixed_expenses', [])
        
        if default_expenses:
            for expense in default_expenses:
                self.add_fixed_expense(
                    expense_name=expense.get('name'),
                    amount=expense.get('amount', 0),
                    category=expense.get('category', 'Bills & Utilities')
                )
    
    def add_fixed_expense(self, expense_name: str, amount: float, 
                         category: str = "Bills & Utilities",
                         start_date: str = None, end_date: str = None):
        """Add or update a fixed expense."""
        conn = sqlite3.connect(self.db.db_path)
        cursor = conn.cursor()
        
        # Check if expense already exists
        cursor.execute("SELECT id FROM fixed_expenses WHERE expense_name = ?", (expense_name,))
        existing = cursor.fetchone()
        
        if existing:
            # Update existing
            cursor.execute("""
                UPDATE fixed_expenses 
                SET amount = ?, category = ?, updated_at = CURRENT_TIMESTAMP
                WHERE expense_name = ?
            """, (amount, category, expense_name))
        else:
            # Insert new
            cursor.execute("""
                INSERT INTO fixed_expenses 
                (expense_name, amount, category, start_date, end_date)
                VALUES (?, ?, ?, ?, ?)
            """, (expense_name, amount, category, start_date, end_date))
        
        conn.commit()
        conn.close()
    
    def get_fixed_expenses(self) -> pd.DataFrame:
        """Get all active fixed expenses."""
        conn = sqlite3.connect(self.db.db_path)
        
        query = """
            SELECT * FROM fixed_expenses 
            WHERE is_active = 1
            ORDER BY expense_name
        """
        
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df
    
    def get_monthly_total(self, month: int = None, year: int = None) -> Dict:
        """Get total monthly expenses (credit card + fixed expenses)."""
        if month is None:
            month = datetime.now().month
        if year is None:
            year = datetime.now().year
        
        # Get credit card spending
        transactions = self.db.get_transactions()
        transactions['date'] = pd.to_datetime(transactions['transaction_date'])
        month_transactions = transactions[
            (transactions['date'].dt.month == month) &
            (transactions['date'].dt.year == year)
        ]
        credit_card_spend = month_transactions['amount'].sum() if not month_transactions.empty else 0
        
        # Get fixed expenses
        fixed_expenses = self.get_fixed_expenses()
        fixed_expenses_total = fixed_expenses['amount'].sum() if not fixed_expenses.empty else 0
        
        # Total
        total_spend = credit_card_spend + fixed_expenses_total
        
        return {
            'month': month,
            'year': year,
            'credit_card_spend': credit_card_spend,
            'fixed_expenses': fixed_expenses_total,
            'total_spend': total_spend,
            'credit_card_count': len(month_transactions),
            'fixed_expenses_count': len(fixed_expenses)
        }
    
    def get_expense_breakdown(self, month: int = None, year: int = None) -> pd.DataFrame:
        """Get detailed expense breakdown by category."""
        if month is None:
            month = datetime.now().month
        if year is None:
            year = datetime.now().year
        
        # Credit card spending by category
        transactions = self.db.get_transactions()
        transactions['date'] = pd.to_datetime(transactions['transaction_date'])
        month_transactions = transactions[
            (transactions['date'].dt.month == month) &
            (transactions['date'].dt.year == year)
        ]
        
        breakdown = []
        
        # Credit card categories
        if not month_transactions.empty:
            category_spend = month_transactions.groupby('category')['amount'].sum().reset_index()
            for _, row in category_spend.iterrows():
                breakdown.append({
                    'Category': row['category'] or 'Uncategorized',
                    'Amount': row['amount'],
                    'Type': 'Credit Card',
                    'Count': len(month_transactions[month_transactions['category'] == row['category']])
                })
        
        # Fixed expenses
        fixed_expenses = self.get_fixed_expenses()
        if not fixed_expenses.empty:
            fixed_by_category = fixed_expenses.groupby('category')['amount'].sum().reset_index()
            for _, row in fixed_by_category.iterrows():
                breakdown.append({
                    'Category': row['category'],
                    'Amount': row['amount'],
                    'Type': 'Fixed Expense',
                    'Count': len(fixed_expenses[fixed_expenses['category'] == row['category']])
                })
        
        df = pd.DataFrame(breakdown)
        if not df.empty:
            df = df.groupby(['Category', 'Type']).agg({
                'Amount': 'sum',
                'Count': 'sum'
            }).reset_index()
            df = df.sort_values('Amount', ascending=False)
        
        return df

