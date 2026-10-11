@echo off
cd /d "%~dp0\..\.."
python tools\base1\bringup.py %*
pause
