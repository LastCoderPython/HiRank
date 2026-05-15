@echo off
echo ============================================
echo RankRoute Backend Setup
echo ============================================

cd /d %~dp0

echo.
echo Creating virtual environment...
python -m venv venv

echo.
echo Activating virtual environment...
call venv\Scripts\activate.bat

echo.
echo Installing dependencies...
pip install -r requirements.txt

echo.
echo ============================================
echo Setup Complete!
echo ============================================
echo.
echo Next steps:
echo 1. Run: python scripts\ingest_data.py
echo 2. Run: python run.py
echo.
pause
