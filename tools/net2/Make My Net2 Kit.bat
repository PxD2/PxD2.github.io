@echo off
title PXD Net2 - make your personal kit
rem Double-click: makes your Net2 kit (your private encrypt/decrypt keys, locked with your passphrase)
rem and your card (the public half you give people). Both land in Documents\PXD Net2.
cd /d "%~dp0..\.."
where py >nul 2>&1 && (set "PY=py -3") || (set "PY=python")
%PY% -c "import cryptography" 2>nul || %PY% -m pip install --user cryptography
set "OUT=%USERPROFILE%\Documents\PXD Net2"
if not exist "%OUT%" mkdir "%OUT%"
set /p NAME=Your name for your card: 
%PY% tools\net2\net2.py kit --out "%OUT%\%NAME%.n2kit" --name "%NAME%"
explorer "%OUT%"
pause
