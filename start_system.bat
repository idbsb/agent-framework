@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] Python virtual environment not found.
  echo Run: python -m venv .venv ^&^& .venv\Scripts\python.exe -m pip install -r requirements.txt
  pause
  exit /b 1
)

if not exist "frontend\node_modules" (
  echo [ERROR] Frontend dependencies not found.
  echo Run: cd frontend ^&^& npm install
  pause
  exit /b 1
)

start "Challenge Cup FastAPI" /D "%~dp0" ".venv\Scripts\python.exe" -m uvicorn src.api.app:app --host 127.0.0.1 --port 8000
start "Challenge Cup Frontend" /D "%~dp0frontend" cmd /k npm run dev
timeout /t 4 /nobreak >nul
start "" "http://127.0.0.1:5173"
endlocal
