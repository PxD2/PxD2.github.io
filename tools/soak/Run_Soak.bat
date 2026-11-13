@echo off
title PXD2 SOAK - every .pxd name and every page, held under load
rem Double-click: starts a private-hosting root from this copy of the site on test ports (5353 / 8080, no admin),
rem soaks every .pxd name for 10 minutes, stops it, and opens the report. Reads only; changes nothing.
rem Longer run:  Run_Soak.bat --minutes 30        Public pages too:  Run_Soak.bat --live
cd /d "%~dp0..\.."
where py >nul 2>&1 && (set "PY=py -3") || (set "PY=python")
%PY% tools\soak\pxdsoak.py --spawn %*
for /f "delims=" %%f in ('dir /b /o-d tools\soak\reports\soak-*.html 2^>nul') do (start "" "tools\soak\reports\%%f" & goto :done)
:done
pause
