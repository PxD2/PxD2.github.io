@echo off
title PXD2 Game Test - invite
cd /d "%~dp0"
set /p WHO=Tester's name: 
python pxdplaytest.py invite --name "%WHO%"
echo.
echo Send them the code above and the link  pxd2.github.io/playtest/  (pxd2gametest.pxd)
pause
