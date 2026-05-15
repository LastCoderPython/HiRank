@echo off
cd /d %~dp0

echo Starting RankRoute Backend...

call venv\Scripts\activate.bat
python run.py
