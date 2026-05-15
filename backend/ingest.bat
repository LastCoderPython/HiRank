@echo off
cd /d %~dp0

echo Ingesting Data into ChromaDB...

call venv\Scripts\activate.bat
python scripts\ingest_data.py

pause
