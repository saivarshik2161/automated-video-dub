@echo off
title AutoDub AI - Local Laptop Server
echo ========================================================
echo Starting AutoDub AI Local Server on your laptop...
echo ========================================================
echo.
cd /d "%~dp0"

:: Activate virtual environment (checks external location first, then local)
if exist "C:\Users\saiva\.venvs\intern\Scripts\activate.bat" (
    call "C:\Users\saiva\.venvs\intern\Scripts\activate.bat"
) else if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
) else (
    echo [ERROR] Virtual environment not found in C:\Users\saiva\.venvs\intern or .venv!
    pause
    exit /b 1
)

:: Open browser automatically after 2 seconds
start "" cmd /c "timeout /t 2 /nobreak >nul && start http://localhost:8000"

:: Start FastAPI backend and UI server
echo Server running at: http://localhost:8000
echo Press Ctrl+C in this terminal window to stop the server.
echo.
python server.py

pause
