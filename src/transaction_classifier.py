"""
Transaction classification module.
Automatically classifies transactions based on merchant names and keywords.
"""

from typing import Dict, Optional
import re


class TransactionClassifier:
    """Classifies transactions into categories based on merchant/description."""
    
    def __init__(self):
        """Initialize classifier with category rules."""
        self.category_rules = self._build_category_rules()
    
    def _build_category_rules(self) -> Dict[str, list]:
        """Build classification rules for each category."""
        return {
            "Food & Dining": [
                # Food delivery
                r'swiggy', r'zomato', r'blinkit', r'zepto', r'bigbasket',
                r'instamart', r'dunzo', r'grofers',
                # Restaurants
                r'restaurant', r'cafe', r'dining', r'eatery', r'bistro',
                r'pizza', r'burger', r'kfc', r'mcdonald', r'domino',
                r'starbucks', r'barista', r'coffee',
                # Food items from Amazon/others
                r'food', r'grocery', r'kitchen', r'provisions',
            ],
            "Shopping": [
                r'amazon', r'flipkart', r'myntra', r'ajio', r'meesho',
                r'snapdeal', r'paytm mall', r'firstcry', r'purplle',
                r'shopping', r'retail', r'store', r'mart',
            ],
            "Bills & Utilities": [
                r'electricity', r'power', r'water', r'gas', r'utility',
                r'phone', r'mobile', r'internet', r'wifi', r'broadband',
                r'airtel', r'jio', r'vodafone', r'vi', r'bsnl',
                r'gas', r'lpg', r'cylinder',
            ],
            "Transportation": [
                r'uber', r'ola', r'rapido', r'auto', r'taxi',
                r'petrol', r'diesel', r'fuel', r'gas station',
                r'parking', r'toll', r'metro', r'bus',
            ],
            "Entertainment": [
                r'netflix', r'prime video', r'hotstar', r'sony liv',
                r'zee5', r'voot', r'disney', r'spotify', r'wynk',
                r'movie', r'cinema', r'theatre', r'bookmyshow',
                r'gaming', r'playstation', r'xbox',
            ],
            "Healthcare": [
                r'pharmacy', r'medic', r'hospital', r'clinic', r'doctor',
                r'apollo', r'fortis', r'max', r'1mg', r'netmeds',
                r'health', r'medical', r'lab', r'diagnostic',
            ],
            "Travel": [
                r'hotel', r'booking', r'airbnb', r'make my trip', r'goibibo',
                r'irctc', r'flight', r'airline', r'airport',
                r'travel', r'trip', r'vacation', r'holiday',
            ],
            "Other": []  # Default category
        }
    
    def classify(self, description: str, merchant: str = None) -> Optional[str]:
        """Classify a transaction based on description and merchant.
        
        Args:
            description: Transaction description
            merchant: Merchant name (optional)
        
        Returns:
            Category name or None if no match
        """
        # Combine description and merchant for matching
        text = f"{description} {merchant or ''}".lower()
        
        # Check each category
        for category, patterns in self.category_rules.items():
            if category == "Other":
                continue  # Skip default category
            
            for pattern in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    return category
        
        # Special handling for Amazon - check if it's grocery/food
        if 'amazon' in text:
            # Check for food-related keywords in description
            food_keywords = ['grocery', 'food', 'kitchen', 'provisions', 'snacks', 'beverage']
            if any(kw in text for kw in food_keywords):
                return "Food & Dining"
            else:
                return "Shopping"
        
        # Default to Other if no match
        return "Other"
    
    def classify_batch(self, transactions: list) -> list:
        """Classify multiple transactions.
        
        Args:
            transactions: List of transaction dicts
        
        Returns:
            List of transactions with 'category' field added/updated
        """
        classified = []
        for txn in transactions:
            # Only classify if category is missing or empty
            if not txn.get('category') or txn.get('category') == '':
                description = txn.get('description', '')
                merchant = txn.get('merchant', '')
                category = self.classify(description, merchant)
                txn['category'] = category
                txn['auto_classified'] = True
            else:
                txn['auto_classified'] = False
            classified.append(txn)
        
        return classified

