@echo off
setlocal
cd /d "%~dp0"

if /i "%~1"=="backend" goto backend
if /i "%~1"=="frontend" goto frontend

if not exist ".venv\Scripts\activate.bat" (
    echo ERROR: Backend virtual environment was not found in .venv.
    goto failed
)
if not exist "..\Frontend\package.json" (
    echo ERROR: Expected the Frontend folder next to Backend.
    goto failed
)
where npm.cmd >nul 2>&1
if errorlevel 1 (
    echo ERROR: npm was not found. Install Node.js and reopen this launcher.
    goto failed
)
if not exist "..\Frontend\node_modules\.bin\vite.cmd" (
    echo ERROR: Frontend dependencies are missing. Run npm install in Frontend first.
    goto failed
)

start "HR Pilot Backend" "%ComSpec%" /d /k call "%~f0" backend
start "HR Pilot Frontend" "%ComSpec%" /d /k call "%~f0" frontend
echo Backend and frontend launch commands opened in separate windows.
echo Backend docs: http://127.0.0.1:8001/docs
echo Frontend:     http://127.0.0.1:5173
echo Keep PostgreSQL, Redis and Qdrant running separately.
echo To stop a server, press Ctrl+C in its window.
exit /b 0

:backend
title HR Pilot Backend
call ".venv\Scripts\activate.bat"
if errorlevel 1 goto failed
rem The existing activation script may still reference the old app_v2 folder.
set "VIRTUAL_ENV=%~dp0.venv"
set "PATH=%~dp0.venv\Scripts;%PATH%"
rem Use the local interpreter explicitly, even if the environment was moved.
"%~dp0.venv\Scripts\python.exe" -m uvicorn src.main:app --reload --host 127.0.0.1 --port 8001
exit /b %errorlevel%

:frontend
title HR Pilot Frontend
cd /d "%~dp0..\Frontend"
call npm.cmd run dev -- --port 5173 --strictPort
exit /b %errorlevel%

:failed
pause
exit /b 1
