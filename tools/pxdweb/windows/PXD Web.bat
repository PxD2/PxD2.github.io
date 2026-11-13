@echo off
rem PXD Web: turn .pxd names on or off for this PC. Usage (the desktop icons do this for you):
rem   "PXD Web.bat" on | off | status
set "MODE=%~1"
if "%MODE%"=="" set "MODE=status"
net session >nul 2>&1 || (
  powershell -NoProfile -Command "Start-Process -Verb RunAs -FilePath '%~f0' -ArgumentList '%MODE%'"
  exit /b
)
title PXD Web %MODE%
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0pxdweb.ps1" %MODE%
echo.
pause
