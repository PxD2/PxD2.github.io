@echo off
title PXD2 PRIVATE HOSTING - .pxd names served from this machine
rem Serves every .pxd name (client sites, the $500 special, PXD2 pages) from THIS copy of the site,
rem not from GitHub. Ports 53 and 80 need "Run as administrator". Nothing here changes the firewall or router:
rem when you are ready to go live, point the router DNS (or each device) at this machine yourself.
cd /d "%~dp0..\.."
where py >nul 2>&1 && (set "PY=py -3") || (set "PY=python")
%PY% tools\pxd2root\pxd2root.py --registry names.json --site . %*
pause
