"""
Database module for storing and retrieving spend data.
Uses SQLite for simplicity and portability.
"""

import sqlite3
import pandas as pd
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict


class SpendDatabase:
    """Manages database operations for spend tracking."""
    
    def __init__(self, db_path: str = "data/spend_tracker.db"):
        """Initialize database connection and create tables if needed."""
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._create_tables()
    
    def _create_tables(self):
        """Create necessary database tables."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Transactions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                card_name TEXT NOT NULL,
                transaction_date DATE NOT NULL,
                amount REAL NOT NULL,
                description TEXT,
                category TEXT,
                merchant TEXT,
                points REAL,
                classification TEXT,
                auto_classified BOOLEAN DEFAULT 0,
                statement_month TEXT,
                statement_year INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(card_name, transaction_date, amount, description)
            )
        """)
        
        # Add new columns if they don't exist (for existing databases)
        try:
            cursor.execute("ALTER TABLE transactions ADD COLUMN points REAL")
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        try:
            cursor.execute("ALTER TABLE transactions ADD COLUMN classification TEXT")
        except sqlite3.OperationalError:
            pass
        
        try:
            cursor.execute("ALTER TABLE transactions ADD COLUMN auto_classified BOOLEAN DEFAULT 0")
        except sqlite3.OperationalError:
            pass
        
        # Monthly summaries table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS monthly_summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                card_name TEXT NOT NULL,
                month INTEGER NOT NULL,
                year INTEGER NOT NULL,
                total_spend REAL NOT NULL,
                min_due REAL,
                transaction_count INTEGER,
                due_date DATE,
                payment_date DATE,
                payment_status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(card_name, month, year)
            )
        """)
        
        # Add additional columns if they don't exist (for existing databases)
        try:
            cursor.execute("ALTER TABLE monthly_summaries ADD COLUMN min_due REAL")
        except sqlite3.OperationalError:
            pass

        # Add verification columns if they don't exist
        try:
            cursor.execute("ALTER TABLE monthly_summaries ADD COLUMN verified BOOLEAN DEFAULT 0")
        except sqlite3.OperationalError:
            pass
        try:
            cursor.execute("ALTER TABLE monthly_summaries ADD COLUMN computed_total REAL")
        except sqlite3.OperationalError:
            pass
        try:
            cursor.execute("ALTER TABLE monthly_summaries ADD COLUMN verification_diff REAL")
        except sqlite3.OperationalError:
            pass
        
        # Bill reminders table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bill_reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                card_name TEXT NOT NULL,
                due_date DATE NOT NULL,
                amount REAL NOT NULL,
                reminder_sent_7d BOOLEAN DEFAULT 0,
                reminder_sent_3d BOOLEAN DEFAULT 0,
                reminder_sent_1d BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Processed emails table (to avoid duplicates)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS processed_emails (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email_id TEXT NOT NULL,
                card_name TEXT NOT NULL,
                subject TEXT,
                email_date DATE,
                processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(email_id, card_name)
            )
        """)
        
        conn.commit()
        conn.close()
    
    def add_transaction(self, card_name: str, transaction_date: str, amount: float,
                       description: str = "", category: str = "", merchant: str = "",
                       points: float = None, classification: str = "", auto_classified: bool = False,
                       statement_month: str = "", statement_year: int = None):
        """Add a single transaction to the database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT OR IGNORE INTO transactions 
                (card_name, transaction_date, amount, description, category, merchant, 
                 points, classification, auto_classified, statement_month, statement_year)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (card_name, transaction_date, amount, description, category, merchant,
                  points, classification, auto_classified, statement_month, statement_year))
            conn.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            return None
        finally:
            conn.close()

    def clear_processed_emails(self, card_name: str = None) -> int:
        """Delete processed email flags. If card_name is None, clears all."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            if card_name:
                cursor.execute("DELETE FROM processed_emails WHERE card_name = ?", (card_name,))
            else:
                cursor.execute("DELETE FROM processed_emails")
            affected = cursor.rowcount
            conn.commit()
            return affected
        except Exception:
            return 0
        finally:
            conn.close()

    def clear_processed_emails_for_month(self, card_name: str, year: int, month: int) -> int:
        """Delete processed email flags for a card within a given month/year (based on email_date)."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            start = datetime(year, month, 1).strftime('%Y-%m-%d')
            if month == 12:
                end = datetime(year + 1, 1, 1).strftime('%Y-%m-%d')
            else:
                end = datetime(year, month + 1, 1).strftime('%Y-%m-%d')
            cursor.execute(
                """
                DELETE FROM processed_emails
                WHERE card_name = ? AND email_date >= ? AND email_date < ?
                """,
                (card_name, start, end)
            )
            affected = cursor.rowcount
            conn.commit()
            return affected
        except Exception:
            return 0
        finally:
            conn.close()

    def set_monthly_verification(self, card_name: str, month: int, year: int,
                                 computed_total: float, verified: bool, verification_diff: float):
        """Update verification fields for a monthly summary."""
        conn = sqlite3.connect(self.db.db_path if hasattr(self, 'db') else self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute("""
                UPDATE monthly_summaries
                SET computed_total = ?, verified = ?, verification_diff = ?, updated_at = CURRENT_TIMESTAMP
                WHERE card_name = ? AND month = ? AND year = ?
            """, (computed_total, int(bool(verified)), verification_diff, card_name, month, year))
            conn.commit()
            return True
        except Exception as e:
            print(f"Error updating monthly verification: {e}")
            return False
        finally:
            conn.close()

    def monthly_verified(self, card_name: str, month: int, year: int) -> bool:
        """Check if a monthly summary is verified."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT verified FROM monthly_summaries
                WHERE card_name = ? AND month = ? AND year = ?
            """, (card_name, month, year))
            row = cursor.fetchone()
            if not row:
                return False
            return bool(row[0])
        except Exception:
            return False
        finally:
            conn.close()
    
    def add_transactions_batch(self, transactions: List[Dict]):
        """Add multiple transactions in a batch."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        for txn in transactions:
            try:
                cursor.execute("""
                    INSERT OR IGNORE INTO transactions 
                    (card_name, transaction_date, amount, description, category, merchant, 
                     points, classification, auto_classified, statement_month, statement_year)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (txn.get('card_name'), txn.get('transaction_date'), txn.get('amount'),
                      txn.get('description', ''), txn.get('category', ''),
                      txn.get('merchant', ''), txn.get('points'),
                      txn.get('classification', ''), txn.get('auto_classified', False),
                      txn.get('statement_month', ''), txn.get('statement_year')))
            except sqlite3.IntegrityError:
                continue
        
        conn.commit()
        conn.close()
    
    def update_monthly_summary(self, card_name: str, month: int, year: int,
                              total_spend: float, transaction_count: int,
                              min_due: float = None, due_date: str = None,
                              payment_date: str = None,
                              payment_status: str = 'pending'):
        """Update or create monthly summary."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO monthly_summaries 
            (card_name, month, year, total_spend, min_due, transaction_count, due_date, 
             payment_date, payment_status, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (card_name, month, year, total_spend, min_due, transaction_count, due_date,
              payment_date, payment_status))
        
        conn.commit()
        conn.close()
    
    def get_transactions(self, card_name: str = None, start_date: str = None,
                        end_date: str = None) -> pd.DataFrame:
        """Retrieve transactions as a DataFrame."""
        conn = sqlite3.connect(self.db_path)
        
        query = "SELECT * FROM transactions WHERE 1=1"
        params = []
        
        if card_name:
            query += " AND card_name = ?"
            params.append(card_name)
        
        if start_date:
            query += " AND transaction_date >= ?"
            params.append(start_date)
        
        if end_date:
            query += " AND transaction_date <= ?"
            params.append(end_date)
        
        query += " ORDER BY transaction_date DESC"
        
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        return df

    def delete_transactions_for_month(self, card_name: str, year: int, month: int) -> int:
        """Delete all transactions for a card within a given month/year."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            start = datetime(year, month, 1).strftime('%Y-%m-%d')
            if month == 12:
                end = datetime(year + 1, 1, 1).strftime('%Y-%m-%d')
            else:
                end = datetime(year, month + 1, 1).strftime('%Y-%m-%d')
            cursor.execute(
                """
                DELETE FROM transactions
                WHERE card_name = ? AND transaction_date >= ? AND transaction_date < ?
                """,
                (card_name, start, end)
            )
            affected = cursor.rowcount
            conn.commit()
            return affected
        except Exception:
            return 0
        finally:
            conn.close()
    
    def get_monthly_summaries(self, card_name: str = None) -> pd.DataFrame:
        """Get monthly summaries as DataFrame."""
        conn = sqlite3.connect(self.db_path)
        
        query = "SELECT * FROM monthly_summaries WHERE 1=1"
        params = []
        
        if card_name:
            query += " AND card_name = ?"
            params.append(card_name)
        
        query += " ORDER BY year DESC, month DESC"
        
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        return df
    
    def get_upcoming_bills(self, days_ahead: int = 30) -> pd.DataFrame:
        """Get bills due within specified days."""
        conn = sqlite3.connect(self.db_path)
        
        query = """
            SELECT * FROM monthly_summaries 
            WHERE due_date IS NOT NULL 
            AND due_date >= date('now')
            AND due_date <= date('now', '+' || ? || ' days')
            AND payment_status = 'pending'
            ORDER BY due_date ASC
        """
        
        df = pd.read_sql_query(query, conn, params=[days_ahead])
        conn.close()
        return df
    
    def is_email_processed(self, email_id: str, card_name: str) -> bool:
        """Check if an email has already been processed."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT COUNT(*) FROM processed_emails 
            WHERE email_id = ? AND card_name = ?
        """, (email_id, card_name))
        
        count = cursor.fetchone()[0]
        conn.close()
        return count > 0
    
    def mark_email_processed(self, email_id: str, card_name: str, subject: str = None, email_date: str = None):
        """Mark an email as processed."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT OR IGNORE INTO processed_emails 
                (email_id, card_name, subject, email_date)
                VALUES (?, ?, ?, ?)
            """, (email_id, card_name, subject, email_date))
            conn.commit()
        except:
            pass
        finally:
            conn.close()
    
    def update_transaction_category(self, transaction_id: int, category: str):
        """Update category for a specific transaction."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE transactions 
                SET category = ? 
                WHERE id = ?
            """, (category, transaction_id))
            conn.commit()
            return True
        except Exception as e:
            print(f"Error updating category: {e}")
            return False
        finally:
            conn.close()
    
    def update_transactions_category_batch(self, transaction_ids: List[int], category: str):
        """Update category for multiple transactions."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            placeholders = ','.join(['?'] * len(transaction_ids))
            cursor.execute(f"""
                UPDATE transactions 
                SET category = ? 
                WHERE id IN ({placeholders})
            """, (category, *transaction_ids))
            conn.commit()
            return cursor.rowcount
        except Exception as e:
            print(f"Error updating categories: {e}")
            return 0
        finally:
            conn.close()

