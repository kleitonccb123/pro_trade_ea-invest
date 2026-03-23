# 🚀 CHECKLIST DE PRODUÇÃO — CRYPTO TRADE HUB
> **Auditoria:** 12 de março de 2026  
> **Objetivo:** Colocar o sistema no ar para operações reais  
> **Estado atual:** Sistema funcional em dev — engine KuCoin real implementada

---

## ⚠️ RESUMO EXECUTIVO

| Categoria | Bloqueadores Críticos | Importantes | Nice to Have |
|---|---|---|---|
| Configuração / Env | 5 | 3 | 2 |
| Infraestrutura / Docker | 3 | 2 | 1 |
| Segurança | 2 | 2 | 1 |
| Trading Engine | 2 | 1 | — |
| Pagamentos | — | 1 | — |
| Monitoramento | — | 1 | 3 |
| **TOTAL** | **12** | **10** | **7** |

**Tempo estimado para resolver os bloqueadores:** 4–8 horas (infra + configuração)

---

## 🔴 BLOQUEADORES CRÍTICOS (sistema NÃO funciona sem estes)

### 1. `APP_MODE=prod` não está definido no docker-compose.prod.yml

**Problema:** `docker-compose.prod.yml` define `ENVIRONMENT: production` mas o backend lê `APP_MODE`, não `ENVIRONMENT`. Sem `APP_MODE=prod`:
- CORS permanece permissivo (modo dev — aceita qualquer origem)
- HSTS não é adicionado
- Validação de `JWT_SECRET_KEY` é ignorada (gera chave aleatória — todos os tokens invalidados a cada restart)

**Correção em `docker-compose.prod.yml`:**
```yaml
environment:
  APP_MODE: prod          # ← ADICIONAR ESTA LINHA
  ENVIRONMENT: production
```

---

### 2. `JWT_SECRET_KEY` e `ENCRYPTION_KEY` não definidos

**Problema:**
- `JWT_SECRET_KEY` — em modo prod, o startup **aborta** se não estiver definido
- `ENCRYPTION_KEY` — usado para criptografar chaves de API dos usuários no banco (Fernet). **Se for perdida, todas as credenciais de exchange dos usuários ficam irrecuperáveis permanentemente.**

**Geração segura:**
```bash
# JWT_SECRET_KEY (64 chars)
python -c "import secrets; print(secrets.token_hex(32))"

# ENCRYPTION_KEY (Fernet — deve ser base64 url-safe 32 bytes)
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

**Armazenar em:** arquivo `.env.prod` (nunca no git) e injetar no docker-compose como variáveis de ambiente.

---

### 3. Certificados SSL não existem

**Problema:** `nginx.prod.conf` referencia:
```
ssl_certificate     /etc/nginx/certs/cert.pem;
ssl_certificate_key /etc/nginx/certs/key.pem;
```
Esses arquivos **não existem no repositório**. Nginx não vai iniciar.

**Correção — opção recomendada (Let's Encrypt + Certbot):**
```bash
certbot certonly --standalone -d seudominio.com.br
# Copiar para: /etc/nginx/certs/cert.pem e key.pem
# OU montar via volume no compose:
volumes:
  - /etc/letsencrypt/live/seudominio.com.br/fullchain.pem:/etc/nginx/certs/cert.pem
  - /etc/letsencrypt/live/seudominio.com.br/privkey.pem:/etc/nginx/certs/key.pem
```

---

### 4. Nginx não está no docker-compose.prod.yml

**Problema:** `nginx.prod.conf` existe e está correto, mas **não há serviço `nginx` no `docker-compose.prod.yml`**. O nginx nunca sobe.

**Correção — adicionar ao `docker-compose.prod.yml`:**
```yaml
nginx:
  image: nginx:alpine
  ports:
    - "80:80"
    - "443:443"
  volumes:
    - ./nginx.prod.conf:/etc/nginx/conf.d/default.conf:ro
    - /etc/letsencrypt/live/seudominio.com.br/fullchain.pem:/etc/nginx/certs/cert.pem:ro
    - /etc/letsencrypt/live/seudominio.com.br/privkey.pem:/etc/nginx/certs/key.pem:ro
  depends_on:
    - backend
  networks:
    - backend_network
  restart: unless-stopped
```

---

### 5. `ALLOWED_ORIGINS` apontando para localhost

**Problema:** Em modo prod, o backend usa `settings.allowed_origins`. Se não definido via env, cai para lista de localhost — **o frontend de produção vai ter todos os requests bloqueados por CORS.**

**Correção em `.env.prod`:**
```env
ALLOWED_ORIGINS=https://seudominio.com.br,https://www.seudominio.com.br
```

---

### 6. `GOOGLE_REDIRECT_URI` e `FRONTEND_REDIRECT_URI` apontando para localhost

**Problema:** Defaults em `config.py`:
```python
google_redirect_uri:  "http://localhost:8000/auth/google/callback"
frontend_redirect_uri: "http://localhost:8081/auth/callback"
```
Login com Google vai falhar — o OAuth2 Google vai redirecionar para localhost.

**Correção em `.env.prod`:**
```env
GOOGLE_REDIRECT_URI=https://seudominio.com.br/api/auth/google/callback
FRONTEND_REDIRECT_URI=https://seudominio.com.br/auth/callback
```
E registrar esses URLs no [Google Cloud Console](https://console.cloud.google.com) como URIs de redirecionamento autorizados.

---

### 7. Inconsistência na build arg do frontend

**Problema:** `docker-compose.yml` passa `VITE_API_URL` mas o frontend lê `VITE_API_BASE_URL` (nomes diferentes). Em adição, `src/stores/plan-store.ts` lê `VITE_API_BASE` (terceiro nome diferente). O frontend vai chamar `http://localhost:8000` em produção.

**Correção em `docker-compose.prod.yml`:**
```yaml
frontend:
  build:
    args:
      VITE_API_BASE_URL: https://seudominio.com.br/api
      VITE_API_BASE: https://seudominio.com.br/api
      VITE_GOOGLE_CLIENT_ID: ${GOOGLE_CLIENT_ID}
```
**E** criar `.env.production` na raiz do frontend:
```env
VITE_API_BASE_URL=https://seudominio.com.br/api
VITE_API_BASE=https://seudominio.com.br/api
VITE_GOOGLE_CLIENT_ID=seu-client-id.apps.googleusercontent.com
```

---

### 8. Redis sem senha no docker-compose.prod.yml

**Problema:** `REDIS_URL: redis://redis:6379/0` (sem senha) no compose prod, mas `redis.prod.conf` pode exigir autenticação. Backend falhará ao conectar.

**Correção em `docker-compose.prod.yml`:**
```yaml
# Serviço Redis:
command: redis-server /etc/redis/redis.conf --requirepass ${REDIS_PASSWORD}

# Backend env:
REDIS_URL: redis://:${REDIS_PASSWORD}@redis:6379/0
```

---

### 9. Senhas padrão MongoDB e Redis (`changeme`)

**Problema:** `docker-compose.yml` usa `MONGO_ROOT_PASSWORD: changeme` e `REDIS_PASSWORD: changeme`. Exposto ao mundo.

**Correção em `.env.prod`:**
```env
MONGO_ROOT_PASSWORD=<senha_forte_aleatoria_32chars>
REDIS_PASSWORD=<senha_forte_aleatoria_32chars>
```

---

### 10. `GOOGLE_CLIENT_ID` e `GOOGLE_CLIENT_SECRET` não definidos

**Problema:** Sem essas variáveis, o login com Google retorna erro 500 e o botão "Login com Google" não funciona.

**Correção:** Obter no [Google Cloud Console](https://console.cloud.google.com) → APIs & Services → Credentials → OAuth 2.0 Client IDs. Adicionar ao `.env.prod`:
```env
GOOGLE_CLIENT_ID=xxxxxxxx.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-xxxxxxxx
```

---

### 11. Trading Engine não inicia automaticamente

**Problema:** O engine de trading (`backend/app/engine/main.py`) é um **processo separado** — não é iniciado pelo FastAPI. Se não for iniciado, nenhum bot vai executar ordens.

**Correção:** Adicionar serviço ao `docker-compose.prod.yml`:
```yaml
trading_engine:
  build:
    context: ./backend
    dockerfile: Dockerfile.engine
  environment:
    APP_MODE: prod
    DATABASE_URL: ${DATABASE_URL}
    REDIS_URL: ${REDIS_URL}
    ENCRYPTION_KEY: ${ENCRYPTION_KEY}
    KUCOIN_SANDBOX: "false"   # ← "true" para testar primeiro
  depends_on:
    - backend
    - redis
    - mongo
  networks:
    - backend_network
  restart: unless-stopped
```

---

### 12. `KUCOIN_SANDBOX` — confirmar modo de operação

**Problema:** Se `KUCOIN_SANDBOX` não for definido, o engine opera na **KuCoin real com dinheiro real**. Não há proteção padrão contra isso.

**Recomendação:**
1. Primeiro deploy: `KUCOIN_SANDBOX=true` — testar integração com sandbox
2. Após validação: mudar para `KUCOIN_SANDBOX=false` conscientemente

---

## 🟡 IMPORTANTES (degradam funcionalidade mas não bloqueiam completamente)

### 13. SMTP não configurado — e-mails não são enviados

**Impacto:** Recuperação de senha e OTPs só são logados no stdout, nunca chegam ao usuário.

**Correção em `.env.prod`:**
```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=seu@gmail.com
SMTP_PASS=app_password_aqui       # Use "App Password" do Google, não a senha normal
SMTP_FROM=noreply@seudominio.com.br
```

---

### 14. Perfect Pay não configurado — pagamentos não chegam

**Impacto:** Webhooks de pagamento chegam mas são rejeitados (token inválido). Planos premium não são ativados automaticamente.

**Correção em `.env.prod`:**
```env
PERFECT_PAY_API_KEY=sua_chave_api
PERFECT_PAY_POSTBACK_SECRET=seu_secret
PERFECT_PAY_PLAN_MAP={"plano_mensal": "PRO", "plano_anual": "PRO+"}
```

---

### 15. Swagger UI aberto em produção

**Impacto:** Qualquer pessoa pode acessar `https://seudominio.com.br/api/docs` e ver todos os endpoints, schemas, e testar a API.

**Correção em `backend/app/main.py`:**
```python
# Trocar:
app = FastAPI(title="Crypto Trade Hub API", ...)

# Por:
import os
_docs_url = "/docs" if os.getenv("APP_MODE") != "prod" else None
_redoc_url = "/redoc" if os.getenv("APP_MODE") != "prod" else None
app = FastAPI(title="Crypto Trade Hub API", docs_url=_docs_url, redoc_url=_redoc_url, ...)
```

---

### 16. Dois bancos de dados em paralelo (MongoDB + SQLite)

**Impacto:** `backend/app/core/local_db.py` mantém SQLite em `data/local_users.db` com dados de usuário, plano e subscription — em paralelo ao MongoDB. Se divergirem (ex: falha de rede), o estado do usuário fica inconsistente.

**Ação imediata:** Garantir que o volume Docker para `data/local_users.db` esteja montado de forma persistente:
```yaml
volumes:
  - ./backend/data:/app/data   # ← adicionar ao docker-compose.prod.yml
```

---

### 17. Sem arquivo `.env.prod` documentado

**Ação:** Criar `.env.prod` (nunca comitar) baseado no modelo abaixo. Ver seção **Template de `.env.prod`**.

---

### 18. Prometheus sem alertas e sem Grafana

**Impacto:** `/metrics` está ativo mas nenhum alerta dispara se o sistema cair ou sobrecarregar.

**Mínimo recomendado:** Adicionar regra de alerta se `up == 0` (backend caiu) e uma dashboard básica no Grafana.

---

### 19. `SENTRY_DSN` não configurado

**Impacto:** Erros em produção não são capturados. O código está completamente preparado — falta apenas o DSN.

**Correção em `.env.prod`:**
```env
SENTRY_DSN=https://xxxx@oxx.ingest.sentry.io/xxxx
```

---

### 20. Banco MongoDB sem backup automático

**Ação:** Configurar `mongodump` agendado (cron ou serviço dedicado). Mínimo: backup diário com retenção de 7 dias.
```bash
# Exemplo cron diário às 3h
0 3 * * * docker exec mongo mongodump --out /backup/$(date +%Y%m%d) --gzip
```

---

### 21. Apenas KuCoin suportado

**Estado atual:** Apesar de menções ao contrário em comentários, **somente KuCoin está implementado**. Usuários com credenciais Binance/Bybit não conseguirão usar o engine.

**Ação:** Comunicar claramente na interface que apenas KuCoin é suportado neste momento.

---

### 22. Volume para dados do trading engine

**Ação:** Garantir persistência de logs e estado do engine:
```yaml
trading_engine:
  volumes:
    - ./backend/data:/app/data
    - ./backend/logs:/app/logs
```

---

## 🟢 NICE TO HAVE (pode ir ao ar sem esses, mas melhora experiência)

### A. Chat de suporte (Crisp)
```env
VITE_CRISP_WEBSITE_ID=seu-id-crisp
```

### B. Integração IA (análise de mercado)
```env
GROQ_API_KEY=gsk_xxxxx
GOOGLE_API_KEY=AIzaxxxxx
```

### C. Web Push Notifications
```bash
# Gerar chaves VAPID
python -c "from py_vapid import Vapid; v = Vapid(); v.generate_keys(); print(v.private_key())"
```
```env
VAPID_PRIVATE_KEY=xxxx
VAPID_PUBLIC_KEY=xxxx
VAPID_CONTACT=mailto:admin@seudominio.com.br
```

### D. Testes E2E (pré-deploy)
Antes de cada deploy, rodar testes de fumaça nos fluxos críticos:
- Login → Dashboard → Criar Bot → Ativar Bot
- Cadastro → Verificação de e-mail → Login
- Marketplace → Comprar robô → Ver performance

### E. Load testing (Locust)
Rodar `locust` antes do lançamento público para identificar gargalos.

### F. Relatório fiscal de afiliados
Backlog — não bloqueia operação.

### G. Alertas de preço em tempo real
Backlog — não bloqueia operação.

---

## 📋 TEMPLATE DE `.env.prod`

> Criar este arquivo no servidor (NUNCA versionar no git). Adicionar `.env.prod` ao `.gitignore`.

```env
# ── Modo de operação ─────────────────────────────────────
APP_MODE=prod
ENVIRONMENT=production

# ── Segurança ─────────────────────────────────────────────
JWT_SECRET_KEY=<64_chars_hex_aleatorio>
ENCRYPTION_KEY=<chave_fernet_base64_gerada>
SECRET_KEY=<32_chars_hex_aleatorio>

# ── Banco de dados ────────────────────────────────────────
DATABASE_URL=mongodb://admin:${MONGO_ROOT_PASSWORD}@mongo:27017/crypto_trade?authSource=admin
MONGO_ROOT_USERNAME=admin
MONGO_ROOT_PASSWORD=<senha_forte_aleatoria>

# ── Redis ───────────────────────────────────────────────
REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379/0
REDIS_PASSWORD=<senha_forte_aleatoria>

# ── CORS ────────────────────────────────────────────────
ALLOWED_ORIGINS=https://seudominio.com.br,https://www.seudominio.com.br

# ── Google OAuth ─────────────────────────────────────────
GOOGLE_CLIENT_ID=xxxxxxxx.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-xxxxxxxx
GOOGLE_REDIRECT_URI=https://seudominio.com.br/api/auth/google/callback
FRONTEND_REDIRECT_URI=https://seudominio.com.br/auth/callback

# ── SMTP ─────────────────────────────────────────────────
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=seu@gmail.com
SMTP_PASS=app_password_aqui
SMTP_FROM=noreply@seudominio.com.br

# ── Perfect Pay ──────────────────────────────────────────
PERFECT_PAY_API_KEY=
PERFECT_PAY_POSTBACK_SECRET=
PERFECT_PAY_PLAN_MAP={"plano_mensal": "PRO", "plano_anual": "PRO+"}

# ── KuCoin (engine) ──────────────────────────────────────
KUCOIN_SANDBOX=true            # ← mudar para false quando pronto para live
KUCOIN_API_KEY=                # opcional — chave global de fallback
KUCOIN_API_SECRET=
KUCOIN_API_PASSPHRASE=

# ── Frontend (baked at build time) ───────────────────────
VITE_API_BASE_URL=https://seudominio.com.br/api
VITE_API_BASE=https://seudominio.com.br/api
VITE_GOOGLE_CLIENT_ID=xxxxxxxx.apps.googleusercontent.com

# ── Monitoramento ────────────────────────────────────────
SENTRY_DSN=
INITIAL_BALANCE=10000

# ── Opcional ────────────────────────────────────────────
VITE_CRISP_WEBSITE_ID=
GROQ_API_KEY=
```

---

## 🗺️ ORDEM DE EXECUÇÃO PARA IR AO AR

```
✅ Pré-requisitos:
   1. Servidor VPS/Cloud com Docker + Docker Compose instalados
   2. Domínio apontando para o IP do servidor (DNS propagado)
   3. Certificado SSL (Let's Encrypt recomendado)

Passo 1 — Configuração (30 min)
   ├── Criar .env.prod com todas as variáveis obrigatórias
   ├── Gerar JWT_SECRET_KEY e ENCRYPTION_KEY e guardar OFFLINE
   ├── Registrar URIs de redirecionamento no Google Cloud Console
   └── Criar .env.production no frontend com VITE_API_BASE_URL

Passo 2 — Infraestrutura (60 min)
   ├── Adicionar serviço nginx ao docker-compose.prod.yml
   ├── Provisionar certificado SSL (certbot/Let's Encrypt)
   ├── Adicionar serviço trading_engine ao docker-compose.prod.yml
   ├── Corrigir REDIS_URL (adicionar senha) no docker-compose.prod.yml
   └── Criar volume persistente para data/ (SQLite + logs)

Passo 3 — Segurança (20 min)
   ├── Desabilitar Swagger UI em APP_MODE=prod
   ├── Verificar que MongoDB e Redis NÃO estão expostos na porta pública
   └── Confirmar que APP_MODE=prod está no compose

Passo 4 — Deploy e teste (sandbox) (60 min)
   ├── docker-compose -f docker-compose.prod.yml up -d --build
   ├── Verificar logs: docker-compose logs -f backend
   ├── Testar: curl https://seudominio.com.br/api/health
   ├── Testar login com Google
   ├── Criar conta de teste, adicionar chaves KuCoin sandbox
   ├── Criar bot, ativar, verificar órdenes no sandbox KuCoin
   └── Verificar e-mail de recuperação de senha

Passo 5 — Go Live (quando sandbox OK)
   ├── Mudar KUCOIN_SANDBOX=false no .env.prod
   ├── Reiniciar trading_engine: docker-compose restart trading_engine
   ├── Monitorar logs do engine por 30 minutos
   └── Ativar Sentry DSN para captura de erros

Passo 6 — Monitoramento
   ├── Configurar backup diário do MongoDB
   ├── Configurar Sentry alertas de e-mail para erros críticos
   └── (opcional) Subir Grafana com dashboard de métricas básicas
```

---

## 📊 ESTADO ATUAL DO SISTEMA

| Componente | Estado |
|---|---|
| API Backend (FastAPI) | ✅ Produção-ready com correções do checklist |
| Trading Engine (KuCoin) | ✅ Implementado — ordens reais via HMAC assinado |
| Frontend (React/Vite) | ✅ Produção-ready após correção das env vars |
| MongoDB | ✅ Com indexes, réplica-ready |
| Redis | ✅ Pub/sub, rate limiting, kill switch |
| Nginx | ✅ Config existe — precisa ser adicionado ao compose |
| SSL/TLS | ❌ Certificados não provisionados |
| SMTP | ⚠️ Implementado — falta configurar credenciais |
| Pagamentos (Perfect Pay) | ⚠️ Implementado — falta configurar credenciais |
| Sentry | ⚠️ Wired — falta DSN |
| Prometheus / Grafana | ⚠️ `/metrics` ativo — falta alertas |
| Estratégias (RSI/Grid/DCA/Scalping) | ✅ Implementadas |
| 2FA (TOTP + backup codes) | ✅ Implementado |
| Monte Carlo Simulator | ✅ Implementado |
| EA Monitor (MT4/MT5) | ✅ Implementado |
| Marketplace de Robôs | ✅ Implementado |
| Testes (unit + integration) | ✅ 537+ testes passando |

---

*Gerado em 12 de março de 2026 — Auditoria completa de produção*
