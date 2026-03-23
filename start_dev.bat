@echo off
REM ============================================================
REM Crypto Trade Hub - Script de Inicializacao para Desenvolvimento
REM ============================================================
REM Este script:
REM 1. Mata todos os processos Python e Node antigos nas portas usadas
REM 2. Inicia o backend (FastAPI) na porta 8000
REM 3. Inicia o frontend (Vite) na porta 8081
REM ============================================================

echo ========================================
echo    Crypto Trade Hub - Dev Startup
echo ========================================
echo.

cd /d "%~dp0"

echo [1/4] Encerrando processos antigos...
REM Matar processos nas portas 8000 e 8081
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000 ^| findstr LISTENING') do (
    taskkill /F /PID %%a >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8081 ^| findstr LISTENING') do (
    taskkill /F /PID %%a >nul 2>&1
)
timeout /t 2 /nobreak >nul

echo [2/4] Configurando ambiente...
set OFFLINE_MODE=true
set APP_MODE=staging

echo [3/4] Iniciando Backend na porta 8000...
start "CryptoHub Backend" cmd /c ".venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --log-level warning"
timeout /t 3 /nobreak >nul

echo [4/4] Iniciando Frontend na porta 8081...
start "CryptoHub Frontend" cmd /c "npm run dev -- --port 8081"

echo.
echo ========================================
echo    Sistema Iniciado com Sucesso!
echo ========================================
echo.
echo URLs disponiveis:
echo   Frontend:  http://localhost:8081
echo   Backend:   http://localhost:8000
echo   API Docs:  http://localhost:8000/docs
echo.
echo Credenciais de teste:
echo   Email:    demo@tradehub.com
echo   Senha:    demo123
echo.
echo Para parar os servidores, feche as janelas do terminal
echo ou use o Gerenciador de Tarefas.
echo.
pause
