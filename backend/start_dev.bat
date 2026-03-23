@echo off
REM 🚀 Crypto Trade Hub - Backend Startup Script for Windows
REM This script makes it easy to start the backend with smart port handling

setlocal enabledelayedexpansion

REM Colors for output
for /F %%a in ('copy /Z "%~f0" nul') do set "BS=%%a"

echo.
echo ╔════════════════════════════════════════════════════════════╗
echo ║                                                            ║
echo ║   🚀 CRYPTO TRADE HUB - FASTAPI BACKEND STARTUP           ║
echo ║                                                            ║
echo ╚════════════════════════════════════════════════════════════╝
echo.

REM Get the script directory
cd /d "%~dp0" || exit /b 1

REM Check if virtual environment is active
if NOT defined VIRTUAL_ENV (
    echo ⚠️  Virtual environment not detected!
    echo.
    echo Attempting to activate virtual environment...
    if exist ".venv\Scripts\activate.bat" (
        call .venv\Scripts\activate.bat
        echo ✅ Virtual environment activated
    ) else if exist ".\.venv\Scripts\activate.bat" (
        call .\.venv\Scripts\activate.bat
        echo ✅ Virtual environment activated
    ) else (
        echo ❌ Could not find virtual environment
        echo Please run: python -m venv .venv
        exit /b 1
    )
)

echo.
echo 📋 Available Options:
echo.
echo   Option 1: Start with default settings (0.0.0.0:8000)
echo   Option 2: Start with auto-port detection (recommended for conflicts)
echo   Option 3: Start with auto-reload (development mode)
echo   Option 4: Custom configuration
echo   Option 5: Exit
echo.

REM If argument provided, skip menu
if "%~1"=="" (
    set /p CHOICE="Select option (1-5) [default: 1]: "
    if "!CHOICE!"=="" set CHOICE=1
) else (
    set CHOICE=%~1
)

echo.

if "!CHOICE!"=="1" (
    echo ▶️  Starting server: 0.0.0.0:8000
    python run_server.py
    goto :eof
)

if "!CHOICE!"=="2" (
    echo ▶️  Starting server with auto-port detection...
    echo ℹ️  If port 8000 is busy, will automatically use 8001, 8002, etc.
    python run_server.py --auto-port
    goto :eof
)

if "!CHOICE!"=="3" (
    echo ▶️  Starting server in development mode with auto-reload...
    python run_server.py --reload --auto-port
    goto :eof
)

if "!CHOICE!"=="4" (
    echo 📝 Custom Configuration:
    echo.
    set /p CUSTOM_HOST="Enter host (default: 0.0.0.0): "
    if "!CUSTOM_HOST!"=="" set CUSTOM_HOST=0.0.0.0
    
    set /p CUSTOM_PORT="Enter port (default: 8000): "
    if "!CUSTOM_PORT!"=="" set CUSTOM_PORT=8000
    
    set /p AUTO_PORT_CHOICE="Enable auto-port? (y/n, default: n): "
    
    set CMD=python run_server.py --host !CUSTOM_HOST! --port !CUSTOM_PORT!
    if /i "!AUTO_PORT_CHOICE!"=="y" (
        set CMD=!CMD! --auto-port
    )
    
    echo.
    echo ▶️  !CMD!
    echo.
    !CMD!
    goto :eof
)

if "!CHOICE!"=="5" (
    echo ⏹️  Exiting...
    exit /b 0
)

echo ❌ Invalid option. Please select 1-5.
exit /b 1
