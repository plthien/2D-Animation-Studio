@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title 2D Animation Studio
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\windows\start_studio.ps1"
set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" echo [ERROR] 2D Animation Studio exited with code %EXIT_CODE%.
exit /b %EXIT_CODE%
