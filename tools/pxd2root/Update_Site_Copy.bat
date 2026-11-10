@echo off
title PXD2 - update the local copy of the site (run when YOU want it)
cd /d "%~dp0..\.."
git pull --ff-only
python tools\names_build.py
pause
