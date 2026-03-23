# ==============================================
# CryptoTradeHub - Script de Inicialização
# Inicia Frontend + Backend automaticamente
# ==============================================

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   CryptoTradeHub - Iniciando Sistema  " -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$rootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDir = Join-Path $rootDir "backend"
$venvPath = Join-Path $rootDir ".venv\Scripts\Activate.ps1"

# Função para verificar se a porta está em uso
function Test-Port {
    param([int]$Port)
    $connection = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    return $null -ne $connection
}

# Parar processos anteriores
Write-Host "[1/5] Parando processos anteriores..." -ForegroundColor Yellow
Get-Process node -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Get-Process python -ErrorAction SilentlyContinue | Where-Object { $_.Path -like "*crypto-trade-hub*" } | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2

# Verificar se as portas estão livres
Write-Host "[2/5] Verificando portas disponíveis..." -ForegroundColor Yellow
if (Test-Port 8000) {
    Write-Host "  [!] Porta 8000 em uso. Liberando..." -ForegroundColor Red
    $process = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | 
               Select-Object -ExpandProperty OwningProcess | 
               Get-Process -ErrorAction SilentlyContinue
    if ($process) { Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue }
    Start-Sleep -Seconds 1
}

if (Test-Port 8080) {
    Write-Host "  [!] Porta 8080 em uso. Liberando..." -ForegroundColor Red
    $process = Get-NetTCPConnection -LocalPort 8080 -State Listen -ErrorAction SilentlyContinue | 
               Select-Object -ExpandProperty OwningProcess | 
               Get-Process -ErrorAction SilentlyContinue
    if ($process) { Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue }
    Start-Sleep -Seconds 1
}

Write-Host "  [OK] Portas 8000 e 8080 disponíveis" -ForegroundColor Green

# Iniciar Backend
Write-Host "[3/5] Iniciando Backend (FastAPI)..." -ForegroundColor Yellow
$backendJob = Start-Job -ScriptBlock {
    param($backendDir, $venvPath)
    Set-Location $backendDir
    & $venvPath
    python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
} -ArgumentList $backendDir, $venvPath

# Aguardar backend iniciar
Write-Host "  [*] Aguardando backend inicializar..." -ForegroundColor Gray
$timeout = 30
$elapsed = 0
while (-not (Test-Port 8000) -and $elapsed -lt $timeout) {
    Start-Sleep -Seconds 1
    $elapsed++
    Write-Host "." -NoNewline -ForegroundColor Gray
}
Write-Host ""

if (Test-Port 8000) {
    Write-Host "  [OK] Backend rodando em http://localhost:8000" -ForegroundColor Green
} else {
    Write-Host "  [ERRO] Backend não iniciou corretamente!" -ForegroundColor Red
    Write-Host "  Verifique os logs do backend." -ForegroundColor Red
}

# Iniciar Frontend
Write-Host "[4/5] Iniciando Frontend (Vite/React)..." -ForegroundColor Yellow
$frontendJob = Start-Job -ScriptBlock {
    param($rootDir)
    Set-Location $rootDir
    npm run dev
} -ArgumentList $rootDir

# Aguardar frontend iniciar
Write-Host "  [*] Aguardando frontend inicializar..." -ForegroundColor Gray
$elapsed = 0
while (-not (Test-Port 8080) -and $elapsed -lt $timeout) {
    Start-Sleep -Seconds 1
    $elapsed++
    Write-Host "." -NoNewline -ForegroundColor Gray
}
Write-Host ""

if (Test-Port 8080) {
    Write-Host "  [OK] Frontend rodando em http://localhost:8080" -ForegroundColor Green
} else {
    Write-Host "  [ERRO] Frontend não iniciou corretamente!" -ForegroundColor Red
}

# Resumo
Write-Host ""
Write-Host "[5/5] Sistema iniciado com sucesso!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Frontend: http://localhost:8080" -ForegroundColor White
Write-Host "  Backend:  http://localhost:8000" -ForegroundColor White
Write-Host "  API Docs: http://localhost:8000/docs" -ForegroundColor White
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Pressione Ctrl+C para parar os servidores." -ForegroundColor Yellow
Write-Host ""

# Abrir navegador
Start-Process "http://localhost:8080"

# Manter script rodando e mostrar logs
try {
    while ($true) {
        # Verificar se os jobs ainda estão rodando
        if ($backendJob.State -eq "Failed") {
            Write-Host "[ERRO] Backend parou inesperadamente!" -ForegroundColor Red
            Receive-Job $backendJob
        }
        if ($frontendJob.State -eq "Failed") {
            Write-Host "[ERRO] Frontend parou inesperadamente!" -ForegroundColor Red
            Receive-Job $frontendJob
        }
        Start-Sleep -Seconds 5
    }
} finally {
    # Cleanup ao encerrar
    Write-Host ""
    Write-Host "Encerrando servidores..." -ForegroundColor Yellow
    Stop-Job $backendJob -ErrorAction SilentlyContinue
    Stop-Job $frontendJob -ErrorAction SilentlyContinue
    Remove-Job $backendJob -ErrorAction SilentlyContinue
    Remove-Job $frontendJob -ErrorAction SilentlyContinue
    Get-Process node -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    Write-Host "Servidores encerrados." -ForegroundColor Green
}
