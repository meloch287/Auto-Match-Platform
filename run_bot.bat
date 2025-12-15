@echo off
chcp 65001 >nul
echo ========================================
echo    Auto-Match Bot Launcher
echo ========================================
echo.

REM Проверяем Docker
echo [1/4] Checking Docker...
docker ps >nul 2>&1
if errorlevel 1 (
    echo ERROR: Docker is not running!
    echo Please start Docker Desktop first.
    pause
    exit /b 1
)

REM Останавливаем приложения в Docker (оставляем только инфраструктуру)
echo [2/4] Stopping Docker apps (keeping infrastructure)...
docker stop automatch-bot automatch-api automatch-worker 2>nul

REM Запускаем только инфраструктуру
echo [3/4] Starting infrastructure (PostgreSQL, Redis, MinIO)...
docker-compose up -d postgres redis minio minio-init
echo Waiting for services to be ready...
timeout /t 5 /nobreak >nul

REM Проверяем venv
if not exist "venv\Scripts\activate.bat" (
    echo ERROR: Virtual environment not found!
    echo Run: python -m venv venv
    echo Then: pip install -e ".[dev]"
    pause
    exit /b 1
)

REM Запускаем бота локально
echo [4/4] Starting Bot locally...
echo.
echo ========================================
echo Bot is starting. Press Ctrl+C to stop.
echo ========================================
echo.

call venv\Scripts\activate.bat
python -m app.bot.main

pause
