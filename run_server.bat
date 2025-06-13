@echo off
setlocal enabledelayedexpansion

echo iPhone Webcam Server Launcher
echo ===========================

REM Check if running with admin privileges
net session >nul 2>&1
if %errorLevel% == 0 (
    echo Running with administrator privileges
) else (
    echo Please run this script as Administrator
    echo Right-click on this file and select "Run as administrator"
    pause
    exit /b 1
)

REM Run the firewall setup first
call setup_firewall.bat

echo.
echo Starting server...
echo.

REM Try to start the server
python src/iphone_webcam_qr.py

if %errorLevel% neq 0 (
    echo.
    echo Server failed to start. Trying alternate port...
    set PORT=8000
    echo Using port !PORT!
    
    REM Set environment variable for the Python script
    set WEBCAM_SERVER_PORT=!PORT!
    
    python src/iphone_webcam_qr.py
)

pause
