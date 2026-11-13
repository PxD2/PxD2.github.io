@echo off
title PXD2 Game Test - reports and testers
cd /d "%~dp0"
python pxdplaytest.py testers
echo.
python pxdplaytest.py reports
echo.
set "R=%~dp0..\..\keys\playtest\reports"
if exist "%R%" start "" "%R%"
pause
