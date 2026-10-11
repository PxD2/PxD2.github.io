@echo off
cd /d "%~dp0"
REM First time: pip install -r requirements.txt  and  python -m playwright install chromium
start "" http://127.0.0.1:8793/
python pxd_operator.py %*
pause
