@echo off
cd /d "%~dp0"
REM Run as administrator. Add --authority ..\..\pxd\authority.json --require-signed once names.json is signed.
python pxd2root.py %*
pause
