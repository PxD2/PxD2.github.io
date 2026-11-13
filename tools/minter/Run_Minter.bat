@echo off
title PXD MINTER - mint and secure .pxd names
rem Double-click: opens the PXD Minter panel in your browser. Close this window to stop it.
rem First time on base1 only: the panel works without a key; to sign deeds run "py -3 tools\minter\pxdmint.py init" once.
cd /d "%~dp0..\.."
where py >nul 2>&1 && (set "PY=py -3") || (set "PY=python")
%PY% -c "import cryptography" 2>nul || %PY% -m pip install --user cryptography
%PY% tools\minter\pxdmint.py gui
pause
