# 🚀 Guia de Configuração do CI/CD

Este documento explica como configurar o pipeline de CI/CD do Crypto Trade Hub.

## 📋 Pré-requisitos

1. Repositório no GitHub
2. Servidor de produção com Docker instalado
3. Acesso SSH ao servidor
4. (Opcional) Domínio configurado

## 🔐 Secrets Necessários

Configure os seguintes secrets em: **Settings > Secrets and variables > Actions**

### Obrigatórios

| Secret | Descrição | Exemplo |
|--------|-----------|---------|
| `SSH_HOST` | IP ou hostname do servidor | `123.456.789.10` |
| `SSH_USER` | Usuário SSH | `deploy` |
| `SSH_PRIVATE_KEY` | Chave privada SSH (inteira) | `-----BEGIN OPENSSH...` |
| `DEPLOY_PATH` | Caminho do projeto no servidor | `/opt/crypto-trade-hub` |

### Opcionais (Recomendados)

| Secret | Descrição | Exemplo |
|--------|-----------|---------|
| `SSH_PORT` | Porta SSH (default: 22) | `22` |
| `NOTIFICATION_WEBHOOK_URL` | URL para notificações | `https://api.exemplo.com/webhook` |
| `MONGODB_URL` | URL do MongoDB em produção | `mongodb://user:pass@host:27017` |
| `ENCRYPTION_KEY` | Chave Fernet (32 bytes base64) | `abc123...` |

## 🔑 Gerando a Chave SSH

### No servidor de produção:

```bash
# Criar usuário de deploy (se não existir)
sudo adduser deploy
sudo usermod -aG docker deploy

# Gerar par de chaves
su - deploy
ssh-keygen -t ed25519 -C "github-actions-deploy"

# Autorizar a chave pública
cat ~/.ssh/id_ed25519.pub >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys

# Copiar a chave privada (para o GitHub Secret)
cat ~/.ssh/id_ed25519
```

### No GitHub:
1. Vá em **Settings > Secrets > New repository secret**
2. Nome: `SSH_PRIVATE_KEY`
3. Valor: Cole a chave privada COMPLETA (incluindo `-----BEGIN...` e `-----END...`)

## 📁 Estrutura no Servidor

```bash
# Criar diretório do projeto
sudo mkdir -p /opt/crypto-trade-hub
sudo chown deploy:deploy /opt/crypto-trade-hub

# Clonar repositório
cd /opt/crypto-trade-hub
git clone https://github.com/SEU_USUARIO/crypto-trade-hub.git .

# Configurar .env de produção
cp backend/.env.example backend/.env
nano backend/.env  # Editar com valores reais

# Primeiro deploy manual
docker-compose up -d
```

## 🔄 Fluxo do Pipeline

```
┌─────────────────────────────────────────────────────────────┐
│                    Push para main                            │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  🧪 JOB 1: Testes                                           │
│  - Lint Python (Ruff)                                        │
│  - Testes unitários                                          │
│  - Build do frontend (validação)                             │
│  - Verifica .env.example                                     │
└──────────────────────────┬──────────────────────────────────┘
                           │ ✅ Passou
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  🐳 JOB 2: Build Docker                                     │
│  - Build imagem backend                                      │
│  - Build imagem frontend                                     │
│  - Push para GitHub Container Registry                       │
│  - Tag: latest + sha + data                                  │
└──────────────────────────┬──────────────────────────────────┘
                           │ ✅ Sucesso
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  🚀 JOB 3: Deploy                                           │
│  - SSH para servidor                                         │
│  - git pull                                                  │
│  - docker pull (novas imagens)                               │
│  - docker-compose up -d                                      │
│  - Health check                                              │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  📢 JOB 4: Notificação                                      │
│  - Envia webhook com status                                  │
│  - Gera resumo no GitHub Actions                             │
└─────────────────────────────────────────────────────────────┘
```

## 🐳 docker-compose.yml para Produção

Certifique-se de ter este arquivo no servidor:

```yaml
# docker-compose.yml
version: '3.8'

services:
  backend:
    image: ghcr.io/SEU_USUARIO/crypto-trade-hub/backend:latest
    container_name: crypto-backend
    restart: unless-stopped
    ports:
      - "8000:8000"
    env_file:
      - backend/.env
    environment:
      - APP_MODE=production
    depends_on:
      - mongodb
    networks:
      - crypto-network

  frontend:
    image: ghcr.io/SEU_USUARIO/crypto-trade-hub/frontend:latest
    container_name: crypto-frontend
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    depends_on:
      - backend
    networks:
      - crypto-network

  mongodb:
    image: mongo:7.0
    container_name: crypto-mongodb
    restart: unless-stopped
    volumes:
      - mongo_data:/data/db
    networks:
      - crypto-network

networks:
  crypto-network:
    driver: bridge

volumes:
  mongo_data:
```

## 🔔 Configurando Notificações

### Usando o router de notificações interno:

O webhook será chamado com este payload:

```json
{
  "type": "deploy",
  "status": "success|failure|skipped",
  "title": "✅ CI/CD Pipeline",
  "message": "Deploy realizado com sucesso!",
  "details": {
    "repository": "user/crypto-trade-hub",
    "branch": "main",
    "commit": "abc123...",
    "author": "username",
    "workflow_run": "https://github.com/.../runs/123",
    "timestamp": "2024-01-15T10:30:00Z"
  }
}
```

### Endpoint receptor (exemplo):

```python
@router.post("/webhook/deploy")
async def receive_deploy_notification(payload: dict):
    if payload["status"] == "success":
        # Enviar notificação para admins
        await notify_admins(f"✅ Deploy concluído: {payload['details']['commit'][:7]}")
    else:
        await notify_admins(f"❌ Deploy FALHOU! Ver: {payload['details']['workflow_run']}")
```

## 🧪 Testando Localmente

```bash
# Simular o workflow localmente com act
# https://github.com/nektos/act

# Instalar act
brew install act  # macOS
# ou
choco install act-cli  # Windows

# Rodar workflow
act push
```

## 🆘 Troubleshooting

### Erro: "Permission denied (publickey)"
- Verifique se a chave SSH está correta
- Certifique-se que o usuário pode fazer docker commands

### Erro: "docker-compose not found"
```bash
# No servidor
sudo apt install docker-compose-plugin
# Ou usar `docker compose` (sem hífen)
```

### Erro: "Cannot connect to MongoDB"
- Verifique se o container do MongoDB está rodando
- Verifique a rede Docker

### Ver logs do deploy
- Acesse: `https://github.com/SEU_USUARIO/REPO/actions`
- Clique no workflow mais recente

## 📊 Monitorando em Produção

Após o deploy, monitore:

1. **Health check**: `curl https://seu-dominio.com/health`
2. **Logs**: `docker logs crypto-backend -f`
3. **Recursos**: `docker stats`

## 🔄 Rollback Manual

Se algo der errado:

```bash
# SSH no servidor
cd /opt/crypto-trade-hub

# Ver versões disponíveis
docker images | grep crypto

# Voltar para versão anterior
docker-compose down
docker tag ghcr.io/.../backend:VERSAO_ANTERIOR ghcr.io/.../backend:latest
docker-compose up -d
```
