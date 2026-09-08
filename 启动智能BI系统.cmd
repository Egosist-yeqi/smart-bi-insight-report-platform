@echo off
setlocal
chcp 65001 >nul
title Smart BI - One-click launcher
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\launch.ps1"
if errorlevel 1 (
  echo.
  echo Startup failed. Review logs\launcher-latest.log, then press any key to close this window.
  pause >nul
)
endlocal
