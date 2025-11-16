@echo off
REM Prat Spend Analyzer - Auto Start Script
REM This script automatically starts the dashboard

echo ========================================
echo Starting Prat Spend Analyzer Dashboard...
echo ========================================
echo.

cd /d "%~dp0"

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python and try again.
    pause
    exit /b 1
)

REM Check if streamlit is installed
python -c "import streamlit" >nul 2>&1
if errorlevel 1 (
    echo ERROR: Streamlit is not installed
    echo Installing required packages...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo ERROR: Failed to install packages
        pause
        exit /b 1
    )
)

echo Starting dashboard...
echo The dashboard will open in your browser automatically.
echo.
echo To stop the dashboard, press Ctrl+C in this window.
echo.

REM Start Streamlit dashboard
streamlit run prat_spend_dashboard.py

pause

