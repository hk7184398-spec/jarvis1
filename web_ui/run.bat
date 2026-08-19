@echo off
REM JARVIS Web UI - Startup Script (Windows)
REM Usage: run.bat [port]

setlocal enabledelayedexpansion

REM Configuration
set PORT=5000
if not "%1"=="" set PORT=%1

set SCRIPT_DIR=%~dp0
set REPO_ROOT=%SCRIPT_DIR%..

echo.
echo ======================================================================
echo          J.A.R.V.I.S. WEB SERVER STARTUP
echo ======================================================================
echo.

REM Check Python
echo [CHECK] Python availability...
python3 --version >nul 2>&1
if errorlevel 1 (
    python --version >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] Python 3 not found
        pause
        exit /b 1
    )
    set PYTHON=python
) else (
    set PYTHON=python3
)

for /f "tokens=*" %%i in ('%PYTHON% --version') do set PYTHON_VERSION=%%i
echo [OK] %PYTHON_VERSION%
echo.

REM Check environment
echo [CHECK] API keys in environment...
if "%GEMINI_API_KEY%"=="" (
    echo [WARN] GEMINI_API_KEY not set (will prompt on web UI)
) else (
    echo [OK] GEMINI_API_KEY set
)

if "%OPENROUTER_API_KEY%"=="" (
    echo [WARN] OPENROUTER_API_KEY not set (will prompt on web UI)
) else (
    echo [OK] OPENROUTER_API_KEY set
)
echo.

REM Create virtual environment if needed
if not exist "%SCRIPT_DIR%.venv" (
    echo [INSTALL] Creating virtual environment...
    %PYTHON% -m venv "%SCRIPT_DIR%.venv"
)

REM Activate virtual environment
call "%SCRIPT_DIR%.venv\Scripts\activate.bat"

REM Install dependencies
echo [INSTALL] Python dependencies...
if exist "%SCRIPT_DIR%requirements_web.txt" (
    pip install -q -r "%SCRIPT_DIR%requirements_web.txt"
    echo [OK] Dependencies installed
) else (
    echo [WARN] requirements_web.txt not found
)
echo.

REM Install parent repo dependencies
if exist "%REPO_ROOT%\requirements.txt" (
    echo [INSTALL] Parent repo dependencies...
    pip install -q -r "%REPO_ROOT%\requirements.txt"
    echo [OK] Parent dependencies installed
)
echo.

REM Start server
echo [START] Starting JARVIS web server...
echo.
echo.
echo Web UI:    http://localhost:%PORT%
echo WebSocket: ws://localhost:%PORT%/socket.io
echo API:       http://localhost:%PORT%/api
echo.
echo Press Ctrl+C to stop
echo.

set PYTHONUNBUFFERED=1
set FLASK_ENV=development

cd /d "%SCRIPT_DIR%"
%PYTHON% app.py

pause
