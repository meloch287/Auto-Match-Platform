@echo off
chcp 65001 >nul
echo ========================================
echo    Auto-Match Platform Launcher
echo    (Infrastructure in Docker, Apps local)
echo ========================================
echo.

REM Проверяем Docker
echo [1/5] Checking Docker...
docker ps >nul 2>&1
if errorlevel 1 (
    echo ERROR: Docker is not running!
    echo Please start Docker Desktop first.
    pause
    exit /b 1
)

REM Останавливаем приложения в Docker
echo [2/5] Stopping Docker apps (keeping infrastructure)...
docker stop automatch-bot automatch-api automatch-worker 2>nul

REM Запускаем только инфраструктуру
echo [3/5] Starting infrastructure (PostgreSQL, Redis, MinIO)...
docker-compose up -d postgres redis minio minio-init
echo Waiting for services to be ready...
timeout /t 8 /nobreak >nul

REM Проверяем venv
echo [4/5] Checking virtual environment...
if not exist "venv\Scripts\activate.bat" (
    echo ERROR: Virtual environment not found!
    echo.
    echo Run these commands first:
    echo   python -m venv venv
    echo   venv\Scripts\activate
    echo   pip install -e ".[dev]"
    pause
    exit /b 1
)

REM Запускаем приложения локально в отдельных окнах
echo [5/5] Starting applications locally...
echo.

start "Auto-Match Bot" cmd /k "title Auto-Match Bot && color 0A && venv\Scripts\activate.bat && echo Starting Bot... && python -m app.bot.main"
timeout /t 2 /nobreak >nul

start "Auto-Match API" cmd /k "title Auto-Match API && color 0B && venv\Scripts\activate.bat && echo Starting API on http://localhost:8000 && uvicorn app.api.main:app --reload --host 0.0.0.0 --port 8000"

echo.
echo ========================================
echo   Services started in separate windows:
echo.
echo   [Green]  Bot  - Telegram bot
echo   [Blue]   API  - http://localhost:8000
echo.
echo   Infrastructure (Docker):
echo   - PostgreSQL: localhost:5432
echo   - Redis: localhost:6379
echo   - MinIO: localhost:9000
echo ========================================
echo.
echo Press any key to close this window...
pause >nul
