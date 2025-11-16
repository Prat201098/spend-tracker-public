# Complete Setup Guide - Step by Step

## What You Need Before Starting

1. **Python installed** on your computer
2. **Your email address** and password (or app password)
3. **Credit card statement emails** from your banks

---

## STEP 1: Check if Python is Installed

### On Windows:
1. Press `Windows Key + R`
2. Type `cmd` and press Enter
3. In the black window, type: `python --version`
4. Press Enter

**What you should see:**
- If you see something like `Python 3.9.0` or higher → ✅ You're good!
- If you see an error → You need to install Python first

### If Python is NOT installed:
1. Go to https://www.python.org/downloads/
2. Click "Download Python" (big yellow button)
3. Run the installer
4. **IMPORTANT:** Check the box that says "Add Python to PATH" before clicking Install
5. Wait for it to finish
6. Close and reopen your command prompt
7. Try `python --version` again

---

## STEP 2: Install the Required Packages

This step downloads all the code libraries the system needs to work.

### What to do:
1. Open Command Prompt (Windows Key + R, type `cmd`, Enter)
2. Navigate to your project folder:
   ```
   cd P:\PRATEEK\Investing\AUTOMATIONS
   ```
   (Press Enter)

3. Install packages:
   ```
   pip install -r requirements.txt
   ```
   (Press Enter)

**What's happening:** This downloads and installs all the tools needed (email reader, database, dashboard, etc.)

**How long:** 2-5 minutes depending on your internet speed

**What you'll see:** Lots of text scrolling - that's normal! Wait until you see a prompt again (like `C:\Users\...>`)

---

## STEP 3: Configure Your Banks

This tells the system which emails to look for.

### What to do:
1. Open the file `config.yaml` in Notepad (or any text editor)
2. Find the section that says `bank_emails:`
3. You'll see example entries like:
   ```yaml
   - sender_pattern: "@hdfcbank.com"
     card_name: "HDFC Credit Card"
     subject_keywords: ["statement", "bill", "spend summary"]
   ```

4. **Replace these with YOUR actual banks:**
   - Look at one of your credit card statement emails
   - Check the "From" email address (e.g., `statements@icicibank.com`)
   - Check the subject line (e.g., "Your ICICI Credit Card Statement")
   - Add an entry for each bank

### Example for ICICI Bank:
```yaml
- sender_pattern: "@icicibank.com"
  card_name: "ICICI Credit Card"
  subject_keywords: ["statement", "bill", "credit card"]
```

### Example for HDFC Bank:
```yaml
- sender_pattern: "@hdfcbank.com"
  card_name: "HDFC Credit Card"
  subject_keywords: ["statement", "bill", "spend"]
```

**Important:** 
- Keep the exact format (spaces, dashes, quotes)
- Add one entry per credit card
- Use keywords that appear in your email subject lines

---

## STEP 4: Set Up Email Access (Gmail Users)

If you use Gmail, you need a special "App Password" instead of your regular password.

### Why?
Gmail blocks regular passwords for security. App passwords are safer.

### How to get an App Password:

1. **Go to your Google Account:**
   - Visit: https://myaccount.google.com/
   - Sign in if needed

2. **Go to Security:**
   - Click "Security" in the left menu

3. **Enable 2-Step Verification (if not already):**
   - Click "2-Step Verification"
   - Follow the steps to enable it
   - (You'll need your phone)

4. **Create App Password:**
   - Go back to Security
   - Click "App passwords" (under "2-Step Verification")
   - Select "Mail" as the app
   - Select "Other" as device, type "Spend Tracker"
   - Click "Generate"
   - **Copy the 16-character password** (looks like: `abcd efgh ijkl mnop`)

5. **Save this password** - you'll use it in the next step!

**For other email providers (Outlook, Yahoo, etc.):**
- You might be able to use your regular password
- Or check their website for "App Password" or "IMAP settings"
- Update `config.yaml` with correct IMAP server settings

---

## STEP 5: Test the Email Connection

Let's make sure everything works!

### What to do:
1. Open Command Prompt
2. Navigate to your folder:
   ```
   cd P:\PRATEEK\Investing\AUTOMATIONS
   ```

3. Run the automation:
   ```
   python main.py
   ```

4. **It will ask you:**
   - "Enter your email address:" → Type your email, press Enter
   - "Enter your email password:" → Type your app password (or regular password), press Enter
     - Note: The password won't show as you type (that's normal for security)

### What should happen:
- You'll see: "Connecting to imap.gmail.com..."
- Then: "Connected successfully!"
- Then: "Processing emails for: [Your Card Name]"
- Then: "Found X emails"
- Then it will parse them

### If you see errors:
- **"Authentication failed"** → Wrong password, or need app password
- **"Connection refused"** → Check internet, or wrong IMAP server in config.yaml
- **"No emails found"** → Check sender_pattern and subject_keywords in config.yaml

---

## STEP 6: View Your Dashboard

Once emails are processed, see your data!

### What to do:
1. In Command Prompt (same window or new one):
   ```
   cd P:\PRATEEK\Investing\AUTOMATIONS
   ```

2. Start the dashboard:
   ```
   streamlit run prat_spend_dashboard.py
   ```

3. **Your browser should open automatically** to `http://localhost:8501`

4. If it doesn't open:
   - Open your browser manually
   - Go to: `http://localhost:8501`

### What you'll see:
- Overview page with your spending totals
- Charts and graphs
- Different pages in the left sidebar

### To stop the dashboard:
- Go back to Command Prompt
- Press `Ctrl + C`
- Type `Y` and press Enter

---

## Common Issues & Solutions

### Issue: "python is not recognized"
**Solution:** Python not in PATH. Reinstall Python and check "Add to PATH" box.

### Issue: "pip is not recognized"
**Solution:** Python wasn't installed correctly. Reinstall Python.

### Issue: "No module named 'streamlit'"
**Solution:** Packages didn't install. Try: `pip install -r requirements.txt` again.

### Issue: "No emails found"
**Solution:** 
- Check your `config.yaml` - sender_pattern must match the "From" email
- Check subject_keywords match your email subjects
- Try increasing days_back: `python main.py --days 60`

### Issue: "Can't parse transactions"
**Solution:** Your bank's email format might be different. We may need to customize the parser.

---

## Next Steps After Setup

1. **Run automation regularly:**
   - Weekly: `python main.py`
   - Or set up a scheduled task (Windows Task Scheduler)

2. **Check dashboard:**
   - Run `streamlit run dashboard.py` whenever you want to see your spending

3. **Update config:**
   - Add more banks as you get new cards
   - Adjust categories as needed

---

## Need Help?

If you get stuck at any step:
1. Tell me which step you're on
2. Copy and paste the exact error message (if any)
3. I'll help you fix it!

