@echo off
cd /d "%~dp0\..\.."
python tools\gateway\pxd_gateway.py --authority pxd\authority.json
pause
