"""
Data analysis module for spending patterns and insights.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List


class SpendAnalyzer:
    """Analyzes spending data and generates insights."""
    
    def __init__(self, db):
        """Initialize with database connection."""
        self.db = db
    
    def get_monthly_summary(self, month: int = None, year: int = None) -> Dict:
        """Get summary for a specific month or current month."""
        if month is None:
            month = datetime.now().month
        if year is None:
            year = datetime.now().year
        
        summaries = self.db.get_monthly_summaries()
        summary = summaries[
            (summaries['month'] == month) & 
            (summaries['year'] == year)
        ]
        
        if summary.empty:
            # Calculate from transactions
            transactions = self.db.get_transactions()
            transactions['date'] = pd.to_datetime(transactions['transaction_date'])
            month_transactions = transactions[
                (transactions['date'].dt.month == month) &
                (transactions['date'].dt.year == year)
            ]
            
            return {
                'month': month,
                'year': year,
                'total_spend': month_transactions['amount'].sum() if not month_transactions.empty else 0,
                'transaction_count': len(month_transactions),
                'cards': month_transactions.groupby('card_name')['amount'].sum().to_dict() if not month_transactions.empty else {}
            }
        
        return summary.iloc[0].to_dict()
    
    def get_spending_by_category(self, start_date: str = None, end_date: str = None) -> pd.DataFrame:
        """Get spending breakdown by category."""
        transactions = self.db.get_transactions(start_date=start_date, end_date=end_date)
        
        if transactions.empty:
            return pd.DataFrame()
        
        # If no categories assigned, use 'Other'
        transactions['category'] = transactions['category'].fillna('Other')
        
        category_spend = transactions.groupby('category')['amount'].agg(['sum', 'count']).reset_index()
        category_spend.columns = ['category', 'total_amount', 'transaction_count']
        category_spend = category_spend.sort_values('total_amount', ascending=False)
        
        return category_spend
    
    def get_spending_by_card(self, start_date: str = None, end_date: str = None) -> pd.DataFrame:
        """Get spending breakdown by card."""
        transactions = self.db.get_transactions(start_date=start_date, end_date=end_date)
        
        if transactions.empty:
            return pd.DataFrame()
        
        card_spend = transactions.groupby('card_name')['amount'].agg(['sum', 'count', 'mean']).reset_index()
        card_spend.columns = ['card_name', 'total_amount', 'transaction_count', 'avg_transaction']
        card_spend = card_spend.sort_values('total_amount', ascending=False)
        
        return card_spend
    
    def get_monthly_trends(self, months: int = 12) -> pd.DataFrame:
        """Get spending trends over the last N months."""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=months * 30)
        
        transactions = self.db.get_transactions(
            start_date=start_date.strftime('%Y-%m-%d'),
            end_date=end_date.strftime('%Y-%m-%d')
        )
        
        if transactions.empty:
            return pd.DataFrame()
        
        transactions['date'] = pd.to_datetime(transactions['transaction_date'])
        transactions['year_month'] = transactions['date'].dt.to_period('M')
        
        monthly_trends = transactions.groupby('year_month')['amount'].agg(['sum', 'count']).reset_index()
        monthly_trends.columns = ['period', 'total_spend', 'transaction_count']
        monthly_trends['period'] = monthly_trends['period'].astype(str)
        
        return monthly_trends
    
    def get_top_merchants(self, limit: int = 10, start_date: str = None, 
                         end_date: str = None) -> pd.DataFrame:
        """Get top merchants by spending."""
        transactions = self.db.get_transactions(start_date=start_date, end_date=end_date)
        
        if transactions.empty:
            return pd.DataFrame()
        
        # Use merchant if available, otherwise use description
        transactions['merchant_name'] = transactions['merchant'].fillna(
            transactions['description'].str[:50]
        )
        
        top_merchants = transactions.groupby('merchant_name')['amount'].agg(['sum', 'count']).reset_index()
        top_merchants.columns = ['merchant', 'total_amount', 'transaction_count']
        top_merchants = top_merchants.sort_values('total_amount', ascending=False).head(limit)
        
        return top_merchants
    
    def get_spending_insights(self) -> Dict:
        """Generate overall spending insights."""
        transactions = self.db.get_transactions()
        
        if transactions.empty:
            return {
                'total_spend': 0,
                'avg_daily_spend': 0,
                'total_transactions': 0,
                'avg_transaction': 0
            }
        
        transactions['date'] = pd.to_datetime(transactions['transaction_date'])
        days_span = (transactions['date'].max() - transactions['date'].min()).days + 1
        
        return {
            'total_spend': transactions['amount'].sum(),
            'avg_daily_spend': transactions['amount'].sum() / max(days_span, 1),
            'total_transactions': len(transactions),
            'avg_transaction': transactions['amount'].mean(),
            'max_transaction': transactions['amount'].max(),
            'min_transaction': transactions['amount'].min(),
            'date_range': {
                'start': transactions['date'].min().strftime('%Y-%m-%d'),
                'end': transactions['date'].max().strftime('%Y-%m-%d')
            }
        }

