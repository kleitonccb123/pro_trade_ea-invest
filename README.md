# 🚀 Crypto Trade Hub

Plataforma completa de trading de criptomoedas com robôs automatizados e dashboard em tempo real.

![TypeScript](https://img.shields.io/badge/TypeScript-007ACC?style=flat&logo=typescript&logoColor=white)
![React](https://img.shields.io/badge/React-20232A?style=flat&logo=react&logoColor=61DAFB)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat&logo=fastapi&logoColor=white)
![Python](https://img.shields.io/badge/Python-3776AB?style=flat&logo=python&logoColor=white)

## 📋 Funcionalidades

- **Dashboard Interativo**: Visualize saldo, lucros, trades e performance em tempo real
- **Robôs de Trading**: Configure e gerencie robôs automatizados com diferentes estratégias
- **Projeções de Mercado**: Cenários pessimista, neutro e otimista baseados em analytics
- **Sistema de Autenticação**: Login seguro com JWT tokens

## 🛠️ Stack Tecnológica

### Frontend
- React 18 + TypeScript
- Vite (build tool)
- TailwindCSS + ShadcnUI
- TanStack Query (cache e sincronização)
- Axios (HTTP client)
- Recharts (gráficos)

### Backend
- FastAPI (Python)
- SQLAlchemy + Alembic (ORM e migrations)
- Pydantic v2 (validação)
- JWT Authentication
- Groq AI + Google Vision API

## 📦 Instalação

### Pré-requisitos

- Node.js >= 18.x
- Python >= 3.10
- npm ou bun

### 1. Clone o Repositório

```bash
git clone https://github.com/seu-usuario/crypto-trade-hub.git
cd crypto-trade-hub
```

### 2. Configure o Frontend

```bash
# Instalar dependências
npm install

# Copiar arquivo de ambiente
cp .env.example .env

# Editar .env com suas configurações
# VITE_API_BASE=http://localhost:8000
```

### 3. Configure o Backend

```bash
cd backend

# Criar ambiente virtual
python -m venv .venv

# Ativar ambiente (Windows)
.\.venv\Scripts\activate

# Ativar ambiente (Linux/Mac)
source .venv/bin/activate

# Instalar dependências
pip install -r requirements.txt

# Copiar arquivo de ambiente
cp .env.example .env

# Editar .env com suas configurações (API keys, SECRET_KEY, etc.)
```

### 4. Configure o Banco de Dados

```bash
# O SQLite é usado por padrão para desenvolvimento
# O banco será criado automaticamente ao iniciar o servidor

# Para usar PostgreSQL em produção, configure DATABASE_URL no .env:
# DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/crypto_db
```

## 🚀 Executando o Projeto

### Terminal 1 - Backend

```bash
cd backend
.\.venv\Scripts\activate  # Windows
# ou: source .venv/bin/activate  # Linux/Mac

uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

O backend estará disponível em: http://localhost:8000
Documentação da API: http://localhost:8000/docs

### Terminal 2 - Frontend

```bash
npm run dev
```

O frontend estará disponível em: http://localhost:5173 ou http://localhost:8080

## ⚙️ Variáveis de Ambiente

### Frontend (.env)

```env
VITE_API_BASE=http://localhost:8000
```

### Backend (backend/.env)

```env
# Database
DATABASE_URL=sqlite+aiosqlite:///./dev.db

# Security (IMPORTANTE: Altere em produção!)
SECRET_KEY=sua_chave_secreta_aqui
ALLOWED_ORIGINS=http://localhost:8080,http://localhost:5173

# AI APIs
GOOGLE_API_KEY=sua_chave_google
GROQ_API_KEY=sua_chave_groq

# Features
ENABLE_BOTS=true
ENABLE_ANALYTICS=true
TRANSLATION_ENABLED=true
TRANSLATION_TARGET=pt
```

Consulte `backend/.env.example` para todas as opções disponíveis.

## 📁 Estrutura do Projeto

```
crypto-trade-hub/
├── src/                    # Frontend React
│   ├── components/         # Componentes reutilizáveis
│   ├── pages/              # Páginas da aplicação
│   ├── lib/                # Utilitários e API client
│   └── hooks/              # Custom hooks
├── backend/                # Backend FastAPI
│   ├── app/
│   │   ├── auth/           # Autenticação JWT
│   │   ├── bots/           # Sistema de robôs
│   │   ├── analytics/      # Analytics e métricas
│   │   └── core/           # Configurações core
│   ├── alembic/            # Migrations
│   └── requirements.txt
├── public/                 # Assets estáticos
└── README.md
```

## 🔒 Segurança

- ⚠️ **Nunca commite o arquivo `.env`** com secrets reais
- 🔐 Gere uma `SECRET_KEY` forte para produção:
  ```python
  python -c "import secrets; print(secrets.token_hex(32))"
  ```
- 🌐 Configure `ALLOWED_ORIGINS` apenas com domínios autorizados
- 🔑 Nunca exponha API keys no frontend

## 🧪 Testes

```bash
# Frontend
npm run test

# Backend
cd backend
pytest
```

## 📖 API Endpoints

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| POST | `/auth/login` | Autenticação de usuário |
| POST | `/auth/register` | Registro de novo usuário |
| POST | `/auth/login-temp` | Login temporário (dev) |
| GET | `/analytics/dashboard/summary` | Resumo do dashboard |
| GET | `/bots` | Lista de robôs |
| GET | `/health` | Health check |

Documentação completa disponível em `/docs` quando o backend está rodando.

## 🤝 Contribuindo

1. Fork o projeto
2. Crie sua branch (`git checkout -b feature/AmazingFeature`)
3. Commit suas mudanças (`git commit -m 'Add some AmazingFeature'`)
4. Push para a branch (`git push origin feature/AmazingFeature`)
5. Abra um Pull Request

## 📄 Licença

Este projeto está sob a licença MIT. Veja o arquivo [LICENSE](LICENSE) para mais detalhes.

---

Desenvolvido com ❤️ para a comunidade crypto
