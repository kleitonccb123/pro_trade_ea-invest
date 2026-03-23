# 🚀 GUIA DE INICIALIZAÇÃO RÁPIDA - Crypto Trade Hub

## ⚠️ IMPORTANTE: Para Usuários Windows

Este sistema foi configurado para funcionar em **modo offline** (sem MongoDB Atlas) devido a incompatibilidades de SSL com Python 3.14.

---

## 📋 Pré-requisitos

1. **Python 3.10+** (recomendado < 3.14 para MongoDB Atlas)
2. **Node.js 18+**
3. **npm** ou **bun**

---

## 🔧 Configuração Inicial (Apenas primeira vez)

```powershell
# 1. Clone ou navegue até o projeto
cd crypto-trade-hub-main

# 2. Crie e ative o ambiente virtual Python
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 3. Instale dependências do backend
cd backend
pip install -r requirements.txt
cd ..

# 4. Instale dependências do frontend
npm install
```

---

## 🚀 Iniciar o Sistema

### Opção 1: Script Automático (Recomendado)

```powershell
# Windows PowerShell
.\start_dev.ps1
```

ou

```cmd
# Prompt de Comando Windows
start_dev.bat
```

### Opção 2: Manual (Dois terminais)

**Terminal 1 - Backend:**
```powershell
cd crypto-trade-hub-main
.\.venv\Scripts\Activate.ps1
$env:OFFLINE_MODE="true"
$env:APP_MODE="staging"
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --log-level warning
```

**Terminal 2 - Frontend:**
```powershell
cd crypto-trade-hub-main
npm run dev -- --port 8081
```

---

## 🌐 URLs do Sistema

| Serviço | URL |
|---------|-----|
| **Frontend** | http://localhost:8081 |
| **Backend API** | http://localhost:8000 |
| **API Docs (Swagger)** | http://localhost:8000/docs |
| **Health Check** | http://localhost:8000/health |

---

## 🔐 Credenciais de Teste

| Campo | Valor |
|-------|-------|
| **Email** | `demo@tradehub.com` |
| **Senha** | `demo123` |

Outros usuários disponíveis:
- `demo@cryptotrade.com` / `demo123`
- `admin@cryptotrade.com` / `demo123`

---

## ⛔ Parar os Servidores

### Se iniciou com script:
Feche os terminais ou use:
```powershell
# Encontrar e matar processos nas portas
Get-NetTCPConnection -LocalPort 8000,8081 -ErrorAction SilentlyContinue | 
    Select-Object -ExpandProperty OwningProcess -Unique | 
    ForEach-Object { Stop-Process -Id $_ -Force }
```

### Se iniciou manualmente:
Pressione `Ctrl+C` em cada terminal.

---

## 🐛 Solução de Problemas

### 1. "Porta 8000 já está em uso"
```powershell
# Encontrar e matar processo na porta
$pid = (Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue).OwningProcess | Select-Object -First 1
if ($pid) { Stop-Process -Id $pid -Force }
```

### 2. "Erro de SSL/TLS com MongoDB"
O sistema já está configurado para usar modo offline automaticamente. Se precisar forçar:
```powershell
$env:OFFLINE_MODE="true"
```

### 3. "Login não funciona"
Verifique se o backend está rodando em http://localhost:8000/health

### 4. "CORS Error"
Verifique se ambos os servidores estão nas portas corretas:
- Backend: 8000
- Frontend: 8081

### 5. "Muitos logs no terminal"
Configure `APP_MODE=staging` ou `APP_MODE=prod` para reduzir logs:
```powershell
$env:APP_MODE="staging"
```

---

## 📁 Estrutura do Projeto

```
crypto-trade-hub-main/
├── backend/                 # FastAPI Backend
│   ├── app/
│   │   ├── auth/           # Autenticação
│   │   ├── bots/           # Gerenciamento de bots
│   │   ├── core/           # Configurações, DB, scheduler
│   │   ├── strategies/     # Estratégias de trading
│   │   └── main.py         # Entrada do backend
│   └── requirements.txt
├── src/                     # React Frontend
│   ├── components/         # Componentes React
│   ├── pages/              # Páginas
│   ├── context/            # Estado global (Zustand)
│   └── services/           # Chamadas API
├── start_dev.ps1           # Script de inicialização (PowerShell)
├── start_dev.bat           # Script de inicialização (CMD)
└── package.json            # Dependências frontend
```

---

## 🔄 Modo Offline vs Online

### Modo Offline (Padrão)
- Dados armazenados em memória
- **Dados são perdidos ao reiniciar o servidor**
- Não requer MongoDB
- Ideal para desenvolvimento e testes

### Modo Online (MongoDB Atlas)
- Requer Python < 3.14 (incompatibilidade SSL)
- Configure as variáveis no `.env`:
```env
DATABASE_URL=mongodb+srv://user:pass@cluster.mongodb.net/
DATABASE_NAME=crypto_trade_hub
OFFLINE_MODE=false
```

---

## 📝 Notas de Desenvolvimento

1. **Renomeação**: "Robôs" foi renomeado para "Estratégias" em toda a interface
2. **Autenticação**: Login local com bcrypt (SHA256 pré-hash + bcrypt)
3. **Google OAuth**: Configurável via `GOOGLE_CLIENT_ID` no `.env`

---

**Versão:** 2.0.0  
**Última atualização:** Fevereiro 2026
