@echo off
REM ==============================================
REM CryptoTradeHub - Script de Inicialização
REM Inicia Frontend + Backend automaticamente
REM ==============================================

echo ========================================
echo    CryptoTradeHub - Iniciando Sistema
echo ========================================
echo.

cd /d "%~dp0"

REM Parar processos anteriores
echo [1/4] Parando processos anteriores...
taskkill /F /IM node.exe >nul 2>&1
timeout /t 2 /nobreak >nul

REM Iniciar Backend em nova janela
echo [2/4] Iniciando Backend (FastAPI)...
start "CryptoTradeHub Backend" cmd /k "cd backend && ..\\.venv\\Scripts\\activate.bat && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"

REM Aguardar backend iniciar
echo [3/4] Aguardando backend inicializar...
timeout /t 8 /nobreak >nul

REM Iniciar Frontend em nova janela
echo [4/4] Iniciando Frontend (Vite/React)...
start "CryptoTradeHub Frontend" cmd /k "npm run dev"

REM Aguardar frontend iniciar
timeout /t 5 /nobreak >nul

echo.
echo ========================================
echo    Sistema iniciado com sucesso!
echo ========================================
echo.
echo   Frontend: http://localhost:8080
echo   Backend:  http://localhost:8000
echo   API Docs: http://localhost:8000/docs
echo.
echo ========================================
echo.

REM Abrir navegador
start http://localhost:8080

echo Pressione qualquer tecla para encerrar os servidores...
pause >nul

REM Encerrar processos
taskkill /F /IM node.exe >nul 2>&1
echo Servidores encerrados.
