@echo off
cd /d "%~dp0"
python -c "import PyQt6.QtWebEngineWidgets, websockets, cryptography" 2>nul || pip install PyQt6 PyQt6-WebEngine websockets cryptography
start "" pythonw pxd_browser.py
