# 📱 Mobile Access Guide

Access your Prat Spend Analyzer dashboard on your mobile phone!

## Option 1: Local Network Access (Easiest - Free)

### Setup:
1. **Find your computer's IP address:**
   - Open Command Prompt
   - Type: `ipconfig`
   - Look for "IPv4 Address" (e.g., `192.168.1.100`)

2. **Start the dashboard:**
   - Run `Start_Prat_Spend_Analyzer.bat` or `streamlit run prat_spend_dashboard.py`
   - Note the URL (usually `http://localhost:8501`)

3. **On your phone (same Wi-Fi network):**
   - Open browser
   - Go to: `http://YOUR_IP_ADDRESS:8501`
   - Example: `http://192.168.1.100:8501`

### Pros:
- ✅ Free
- ✅ No setup required
- ✅ Fast (local network)

### Cons:
- ❌ Only works on same Wi-Fi network
- ❌ Need to know your IP address
- ❌ IP may change if router restarts

---

## Option 2: Streamlit Cloud (Recommended - Free)

### Setup:
1. **Create GitHub account** (if you don't have one):
   - Go to https://github.com
   - Sign up for free

2. **Create a repository:**
   - Click "New repository"
   - Name it: `prat-spend-analyzer`
   - Make it **Private** (for security)
   - Click "Create repository"

3. **Upload your code:**
   - Install Git: https://git-scm.com/downloads
   - Open Command Prompt in your project folder
   - Run these commands:
     ```bash
     git init
     git add .
     git commit -m "Initial commit"
     git branch -M main
     git remote add origin https://github.com/YOUR_USERNAME/prat-spend-analyzer.git
     git push -u origin main
     ```

4. **Deploy to Streamlit Cloud:**
   - Go to https://share.streamlit.io
   - Sign in with GitHub
   - Click "New app"
   - Select your repository
   - Main file: `prat_spend_dashboard.py`
   - Click "Deploy"

5. **Access on mobile:**
   - Streamlit will give you a URL like: `https://your-app.streamlit.app`
   - Open this URL on your phone browser
   - Bookmark it for easy access!

### Pros:
- ✅ Free
- ✅ Accessible from anywhere (internet required)
- ✅ Always available (runs in cloud)
- ✅ Easy to share

### Cons:
- ❌ Need GitHub account
- ❌ Need to upload code (but it's private)
- ❌ Database won't persist (need to configure storage)

---

## Option 3: Ngrok (Temporary Public URL - Free)

### Setup:
1. **Sign up for Ngrok:**
   - Go to https://ngrok.com
   - Sign up for free account
   - Download ngrok

2. **Start your dashboard:**
   - Run `streamlit run prat_spend_dashboard.py`

3. **Create tunnel:**
   - Open new Command Prompt
   - Run: `ngrok http 8501`
   - Copy the "Forwarding" URL (e.g., `https://abc123.ngrok.io`)

4. **Access on mobile:**
   - Open the ngrok URL on your phone
   - Works from anywhere!

### Pros:
- ✅ Free (with limitations)
- ✅ Quick setup
- ✅ Accessible from anywhere

### Cons:
- ❌ URL changes each time (unless paid plan)
- ❌ Free tier has session limits
- ❌ Less secure (public URL)

---

## Option 4: VPS/Cloud Server (Paid - Most Reliable)

### Options:
- **DigitalOcean**: ~$5/month
- **AWS EC2**: ~$5-10/month
- **Google Cloud**: ~$5-10/month
- **Azure**: ~$5-10/month

### Setup:
1. Create account with cloud provider
2. Create a virtual server (Ubuntu recommended)
3. Install Python and dependencies
4. Upload your code
5. Run dashboard
6. Access via server's public IP

### Pros:
- ✅ Always available
- ✅ Full control
- ✅ Can store database permanently
- ✅ More secure

### Cons:
- ❌ Costs money (~$5-10/month)
- ❌ Requires technical setup
- ❌ Need to maintain server

---

## Recommended: Start with Option 1, Move to Option 2

1. **For now**: Use Option 1 (Local Network) - it's free and works immediately
2. **Later**: Set up Option 2 (Streamlit Cloud) for permanent access

---

## Security Notes

⚠️ **Important**: 
- Never share your dashboard URL publicly if it contains financial data
- Use strong passwords for email access
- Consider making Streamlit Cloud app private
- Don't commit sensitive data (passwords, API keys) to GitHub

---

## Troubleshooting

**Can't access on phone?**
- Make sure phone and computer are on same Wi-Fi
- Check Windows Firewall (may need to allow port 8501)
- Try disabling firewall temporarily to test

**Dashboard not loading?**
- Make sure dashboard is running on computer
- Check the IP address is correct
- Try accessing from computer first: `http://localhost:8501`

**Need help?**
- Check Streamlit docs: https://docs.streamlit.io
- Check ngrok docs: https://ngrok.com/docs

