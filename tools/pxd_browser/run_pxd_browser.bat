@echo off
cd /d "%~dp0"
python -c "import PyQt6.QtWebEngineWidgets" 2>nul || pip install PyQt6 PyQt6-WebEngine
start "" pythonw pxd_browser.py
