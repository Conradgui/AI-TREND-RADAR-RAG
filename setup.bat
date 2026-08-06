@echo off
chcp 65001 >nul
title AI Trend Radar RAG - 首次配置

REM PowerShell handles the Provider key as a SecureString so it is not echoed.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\setup-windows.ps1"
exit /b %ERRORLEVEL%
