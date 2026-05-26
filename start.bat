@echo off
setlocal

cd /d "%~dp0"
set "ROOT=%CD%"

if not exist ".env" (
    echo [start] Creating .env from .env.example...
    copy /Y ".env.example" ".env" >nul || goto :fail
)

if not exist ".venv\Scripts\python.exe" (
    echo [start] Creating Python virtual environment...
    py -3.11 -m venv .venv >nul 2>nul || python -m venv .venv || goto :fail

    echo [start] Installing backend dependencies...
    ".venv\Scripts\python.exe" -m pip install --upgrade pip || goto :fail
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt || goto :fail
)

echo [start] Starting PostgreSQL and Redis...
docker compose up -d postgres redis || goto :fail

echo [start] Applying database migrations...
".venv\Scripts\python.exe" -m alembic upgrade head || goto :fail

echo [start] Seeding pilot data...
".venv\Scripts\python.exe" -m scripts.seed_pilot || goto :fail

if exist "frontend\package-lock.json" if not exist "frontend\node_modules" (
    echo [start] Installing frontend dependencies...
    pushd "frontend" || goto :fail
    call npm ci || (
        popd
        goto :fail
    )
    popd
)

echo [start] Launching API and dashboard...
start "Winzapp API" cmd /k "cd /d ""%ROOT%"" && .venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000"

if exist "frontend\package.json" (
    start "Winzapp Dashboard" cmd /k "cd /d ""%ROOT%\frontend"" && npm run dev"
)

echo [start] API: http://127.0.0.1:8000
if exist "frontend\package.json" echo [start] Dashboard: http://127.0.0.1:5173
exit /b 0

:fail
echo [start] Startup failed.
exit /b 1
