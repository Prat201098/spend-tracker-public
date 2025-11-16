# 💰 Spend Tracker Automation

An automated system to track your credit card spending across multiple cards by parsing monthly statement emails, analyzing spending patterns, and providing bill payment reminders.

## Features

- 📧 **Email Integration**: Automatically fetches credit card statement emails from your inbox
- 📊 **Spending Analysis**: Tracks spending by card, category, merchant, and time period
- 📈 **Interactive Dashboard**: Beautiful Streamlit dashboard with charts and insights
- 🔔 **Bill Reminders**: Automated reminders for upcoming bill payments
- 💾 **Data Storage**: SQLite database for reliable data persistence
- 📄 **PDF Support**: Parses both email body text and PDF attachments

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Your Banks

Edit `config.yaml` to add your credit card email patterns:

```yaml
email:
  bank_emails:
    - sender_pattern: "@yourbank.com"
      card_name: "Your Card Name"
      subject_keywords: ["statement", "bill", "spend summary"]
```

### 3. Set Up Email Access

For Gmail users, you'll need to:
1. Enable "Less secure app access" OR
2. Use an "App Password" (recommended):
   - Go to Google Account → Security → 2-Step Verification → App passwords
   - Generate an app password for "Mail"
   - Use this password instead of your regular password

For other email providers, check their IMAP settings and update `config.yaml` accordingly.

## Usage

### Run Email Automation

Fetch and process emails from the last 30 days:

```bash
python main.py --email your.email@example.com --days 30
```

Or run interactively:

```bash
python main.py
```

### Launch Dashboard

**Easy Way (Double-click shortcut):**
- Double-click `Start_Prat_Spend_Analyzer.bat` in the project folder

**Or manually:**
```bash
streamlit run prat_spend_dashboard.py
```

The dashboard will open in your browser at `http://localhost:8501`

## Dashboard Features

- **Overview**: Key metrics, monthly trends, spending by card
- **Monthly Analysis**: Detailed breakdown for any month/year
- **Spending Breakdown**: Analysis by category and top merchants
- **Bill Reminders**: Upcoming bills and payment reminders
- **Transactions**: Detailed transaction list with filters

## Project Structure

```
.
├── config.yaml              # Configuration file
├── requirements.txt         # Python dependencies
├── main.py                  # Main automation script
├── prat_spend_dashboard.py  # Streamlit dashboard
├── Start_Prat_Spend_Analyzer.bat  # Quick start shortcut
├── src/
│   ├── database.py          # Database operations
│   ├── email_fetcher.py     # Email fetching (IMAP)
│   ├── email_parser.py      # Email/PDF parsing
│   ├── analyzer.py          # Spending analysis
│   └── reminder_system.py   # Bill reminders
└── data/
    └── spend_tracker.db     # SQLite database (created automatically)
```

## How It Works

1. **Email Fetching**: Connects to your email via IMAP and searches for credit card statement emails
2. **Parsing**: Extracts transaction data from email body text and PDF attachments
3. **Storage**: Saves transactions and monthly summaries to SQLite database
4. **Analysis**: Analyzes spending patterns, trends, and categories
5. **Reminders**: Checks for upcoming bills and sends reminders
6. **Dashboard**: Visualizes all data in an interactive web interface

## Customization

### Adding New Banks

Add entries to `config.yaml` under `email.bank_emails`:

```yaml
- sender_pattern: "@newbank.com"
  card_name: "New Bank Card"
  subject_keywords: ["statement", "bill"]
```

### Email Parsing

The parser uses regex patterns to extract data. If your bank's email format is different, you may need to customize the patterns in `src/email_parser.py`.

### Categories

Edit categories in `config.yaml`:

```yaml
categories:
  - "Food & Dining"
  - "Shopping"
  # Add your categories
```

## Security Notes

- Never commit your email password or `.env` files
- Use app passwords instead of your main email password
- The database is stored locally - keep it secure
- Consider encrypting sensitive data if needed

## Troubleshooting

### Email Connection Issues

- Verify IMAP settings in `config.yaml`
- Check if your email provider requires app passwords
- Ensure IMAP is enabled in your email account settings

### Parsing Issues

- Some banks use unique email formats
- You may need to customize parsing patterns in `src/email_parser.py`
- Check the email body format and adjust regex patterns accordingly

### No Data in Dashboard

- Run `main.py` first to fetch and process emails
- Check if emails are being found (look for "Found X emails" in output)
- Verify bank email patterns in `config.yaml` match your actual emails

## Future Enhancements

- [ ] Automatic category assignment using ML
- [ ] Budget tracking and alerts
- [ ] Export to Excel/CSV
- [ ] Multi-currency support
- [ ] SMS reminders
- [ ] Bank API integration (Plaid, Yodlee)

## License

This project is for personal use. Feel free to modify and extend it for your needs.

## Support

For issues or questions, check the code comments or customize the parsing logic based on your bank's email format.

