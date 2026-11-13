@echo off
rem PXD2 Game Test on this machine: the gate in front of the game stream, reachable through a Cloudflare tunnel.
rem Start the game first (Pixel Streaming signalling server + the packaged game), then double-click this.
title PXD2 Game Test
cd /d "%~dp0"
set "KEYS=%~dp0..\..\keys"
if not exist "%KEYS%" mkdir "%KEYS%"
if not exist "%KEYS%\pxd-host.json" echo {"id": "%COMPUTERNAME%", "name": "%COMPUTERNAME% game test"}>"%KEYS%\pxd-host.json"
set "PXD_HOST_CONF=%KEYS%\pxd-host.json"
set "PXD_HOST_TOKEN_FILE=%KEYS%\pxd-host.token"
python pxdplaytest.py serve --tunnel --max-players 1
pause
