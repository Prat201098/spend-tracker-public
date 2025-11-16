# Quick Start Guide

## Step 1: Install Dependencies

```bash
pip install -r requirements.txt
```

## Step 2: Configure Your Banks

Edit `config.yaml` and add your credit card email patterns. For example:

```yaml
email:
  bank_emails:
    - sender_pattern: "@hdfcbank.com"
      card_name: "HDFC Credit Card"
      subject_keywords: ["statement", "bill", "spend summary"]
```

## Step 3: Set Up Email Access

### For Gmail:
1. Go to Google Account → Security
2. Enable 2-Step Verification
3. Go to App passwords → Generate password for "Mail"
4. Use this app password (not your regular password)

### For Other Providers:
- Check IMAP settings in `config.yaml`
- Update `imap_server` and `imap_port` as needed

## Step 4: Run the Automation

```bash
python main.py --email your.email@example.com
```

Or run interactively:
```bash
python main.py
```

This will:
- Connect to your email
- Search for credit card statement emails
- Parse and extract transaction data
- Store everything in the database
- Check for bill reminders

## Step 5: View Your Dashboard

**Easy Way:**
- Double-click `Start_Prat_Spend_Analyzer.bat` in the project folder

**Or manually:**
```bash
streamlit run prat_spend_dashboard.py
```

Open your browser to `http://localhost:8501`

## Tips

- Run `main.py` regularly (weekly/monthly) to keep data updated
- Customize email patterns in `config.yaml` if emails aren't being found
- The parser works best with structured emails - some banks may need custom parsing

## Troubleshooting

**No emails found?**
- Check sender patterns in `config.yaml` match your actual bank emails
- Verify subject keywords match your email subjects
- Try increasing `days_back` parameter

**Parsing issues?**
- Some banks use unique formats
- Check email body format
- May need to customize `src/email_parser.py` for your bank

**Connection errors?**
- Verify IMAP settings
- Use app password for Gmail
- Check firewall/network settings

