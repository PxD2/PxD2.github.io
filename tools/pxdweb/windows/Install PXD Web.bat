@echo off
rem Double-click once: installs PXD Web on this PC, puts PXD Web ON / OFF / STATUS on the desktop, and turns it on.
net session >nul 2>&1 || (
  powershell -NoProfile -Command "Start-Process -Verb RunAs -FilePath '%~f0'"
  exit /b
)
title Installing PXD Web
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0pxdweb.ps1" install
echo.
pause
