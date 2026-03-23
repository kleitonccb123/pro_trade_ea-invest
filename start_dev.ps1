# ============================================================
# Crypto Trade Hub - Script de Inicialização para Desenvolvimento
# ============================================================
# Este script:
# 1. Mata todos os processos Python e Node antigos nas portas usadas
# 2. Inicia o backend (FastAPI) na porta 8000
# 3. Inicia o frontend (Vite) na porta 8081
# ============================================================

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   Crypto Trade Hub - Dev Startup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Definir diretório do projeto
$PROJECT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $PROJECT_DIR

Write-Host "[1/4] Encerrando processos antigos..." -ForegroundColor Yellow

# Matar processos nas portas 8000 e 8081
$ports = @(8000, 8081)
foreach ($port in $ports) {
    $processes = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue | 
                 Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($pid in $processes) {
        if ($pid -and $pid -ne 0) {
            Write-Host "  Matando processo PID $pid na porta $port" -ForegroundColor Gray
            Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
        }
    }
}

# Aguardar liberação das portas
Start-Sleep -Seconds 2

Write-Host "[2/4] Ativando ambiente virtual Python..." -ForegroundColor Yellow
$venvPath = Join-Path $PROJECT_DIR ".venv\Scripts\Activate.ps1"
if (Test-Path $venvPath) {
    & $venvPath
    Write-Host "  Ambiente virtual ativado" -ForegroundColor Green
} else {
    Write-Host "  AVISO: Ambiente virtual não encontrado em .venv\" -ForegroundColor Red
}

Write-Host "[3/4] Iniciando Backend (FastAPI) na porta 8000..." -ForegroundColor Yellow

# Configurar variáveis de ambiente para modo offline
$env:OFFLINE_MODE = "true"
$env:APP_MODE = "staging"  # Menos logs que 'dev'

# Iniciar backend em background
$backendJob = Start-Job -ScriptBlock {
    param($dir)
    Set-Location $dir
    & ".\.venv\Scripts\python.exe" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --log-level warning
} -ArgumentList $PROJECT_DIR, "backend"

Write-Host "  Backend iniciado (Job ID: $($backendJob.Id))" -ForegroundColor Green

# Aguardar backend inicializar
Start-Sleep -Seconds 3

Write-Host "[4/4] Iniciando Frontend (Vite) na porta 8081..." -ForegroundColor Yellow

# Iniciar frontend em background
$frontendJob = Start-Job -ScriptBlock {
    param($dir)
    Set-Location $dir
    & npm run dev -- --port 8081
} -ArgumentList $PROJECT_DIR

Write-Host "  Frontend iniciado (Job ID: $($frontendJob.Id))" -ForegroundColor Green

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "   Sistema Iniciado com Sucesso!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "URLs disponíveis:" -ForegroundColor White
Write-Host "  Frontend:  http://localhost:8081" -ForegroundColor Cyan
Write-Host "  Backend:   http://localhost:8000" -ForegroundColor Cyan
Write-Host "  API Docs:  http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host ""
Write-Host "Credenciais de teste:" -ForegroundColor White
Write-Host "  Email:    demo@tradehub.com" -ForegroundColor Yellow
Write-Host "  Senha:    demo123" -ForegroundColor Yellow
Write-Host ""
Write-Host "Para parar os servidores, execute:" -ForegroundColor Gray
Write-Host "  Stop-Job $($backendJob.Id), $($frontendJob.Id)" -ForegroundColor Gray
Write-Host "  Remove-Job $($backendJob.Id), $($frontendJob.Id)" -ForegroundColor Gray
Write-Host ""
Write-Host "Ou simplesmente feche este terminal." -ForegroundColor Gray
