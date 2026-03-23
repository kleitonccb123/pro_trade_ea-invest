# 🗄️ Configuração MongoDB Atlas em Nuvem

## 📋 Passo a Passo

### 1. Criar Conta no MongoDB Atlas

1. Visite: https://cloud.mongodb.com/
2. Clique em **"Sign Up"** ou **"Create Account"**
3. Preencha os dados (email, senha, etc)
4. Confirme o email
5. Faça login

### 2. Criar um Cluster

1. No dashboard, clique em **"Create a Deployment"**
2. Escolha **"MongoDB Atlas"** (é a opção padrão)
3. Selecione o plano:
   - ✅ **M0 Sandbox** (Gratuito, 512 MB)
   - **M10** ou superior (Pago)
4. Escolha a região:
   - Recomendado: **US-EAST-1** ou a mais próxima de você
5. Clique em **"Create Deployment"**
6. Aguarde 3-5 minutos para o cluster ser criado

### 3. Criar Usuario de Banco de Dados

1. Após a criação do cluster, clique em **"Database Access"** (no menu esquerdo)
2. Clique em **"Add New Database User"**
3. Preencha:
   - **Username**: `crypto_user` (ou outro nome)
   - **Password**: Gere uma senha forte (copie!)
4. Clique em **"Add User"**

### 4. Liberar IP (Network Access)

1. Clique em **"Network Access"** (no menu esquerdo)
2. Clique em **"Add IP Address"**
3. Opções:
   - **0.0.0.0/0**: Aceita conexões de qualquer IP (menos seguro, mais fácil)
   - Seu IP específico: Mais seguro
4. Clique em **"Confirm"**

### 5. Obter Connection String

1. Volte à **"Overview"** do cluster
2. Clique em **"Connect"**
3. Escolha **"Drivers"**
4. Selecione **"Python"** e versão **3.6 or later**
5. Copie a connection string:

```
mongodb+srv://crypto_user:PASSWORD@cluster.mongodb.net/?retryWrites=true&w=majority
```

**⚠️ Importante**: Substitua `PASSWORD` pela senha do usuário!

### 6. Atualizar .env do Projeto

No arquivo `backend/.env` (ou criar se não existir):

```env
# MongoDB Atlas Configuration
DATABASE_URL=mongodb+srv://crypto_user:SUA_SENHA_AQUI@cluster.mongodb.net/crypto_trade_hub?retryWrites=true&w=majority
DATABASE_NAME=crypto_trade_hub
```

**Exemplo completo com todos os dados**:
```env
DATABASE_URL=mongodb+srv://crypto_user:MySecurePassword123@crypto-cluster.mongodb.net/crypto_trade_hub?retryWrites=true&w=majority
DATABASE_NAME=crypto_trade_hub
SECRET_KEY=seu_secret_key_aqui
ALGORITHM=HS256
```

### 7. Instalar Dependências Python

```bash
cd backend
pip install motor pymongo
```

Ou adicione ao `requirements.txt`:
```
motor==3.3.2
pymongo==4.6.1
```

### 8. Atualizar app/main.py

No arquivo `backend/app/main.py`, atualize o startup:

```python
from app.core.database import connect_db, disconnect_db, init_db

@app.on_event("startup")
async def on_startup():
    await connect_db()      # ← Conectar ao MongoDB
    await init_db()         # ← Criar índices
    # ... resto do código

@app.on_event("shutdown")
async def on_shutdown():
    await disconnect_db()   # ← Desconectar
```

### 9. Teste a Conexão

```bash
cd backend
python -m uvicorn app.main:app --reload
```

Se ver a mensagem:
```
✅ Conectado ao MongoDB com sucesso!
✅ Índices do MongoDB criados com sucesso!
```

Parabéns! Você conectou ao MongoDB! 🎉

---

## 🔐 Dicas de Segurança

### ✅ Boas Práticas

1. **Use variáveis de ambiente** para a senha
   - Nunca commite a senha no GitHub
   - Use `.env` localmente
   - Em produção, configure no servidor/CI-CD

2. **Senha forte**
   - Use senhas com 16+ caracteres
   - Inclua números, letras maiúsculas/minúsculas, símbolos
   - Use geradores de senha

3. **IP Whitelist**
   - Se em produção, libere apenas IPs específicos
   - Não use `0.0.0.0/0` em produção

4. **Backups**
   - MongoDB Atlas faz backups automáticos (plano pago)
   - Para M0 free: configure backups manualmente

### ❌ Não Faça

```python
# ❌ NUNCA FAÇA ISSO
DATABASE_URL = "mongodb+srv://user:senha123@cluster.mongodb.net/db"

# ✅ SEMPRE USE VARIÁVEIS DE AMBIENTE
DATABASE_URL = os.getenv("DATABASE_URL")
```

---

## 📊 Tipos de Cluster (Preços)

| Plano | Preço | Storage | Vantagens |
|-------|-------|---------|-----------|
| **M0 (Sandbox)** | GRÁTIS | 512 MB | Para teste/desenvolvimento |
| **M2** | $9/mês | 2 GB | Pequeno projeto |
| **M5** | $57/mês | 10 GB | Projeto médio |
| **M10** | $99/mês | 10 GB | Projeto profissional |
| **M30+** | Variável | 30+ GB | Enterprise |

Para este projeto, recomendo:
- **Desenvolvimento**: M0 (GRÁTIS)
- **Produção**: M10 ou superior

---

## 🆘 Troubleshooting

### Erro: "Connection refused"
**Problema**: Não consegue conectar ao MongoDB
**Solução**:
1. Verifique se o IP está liberado (Network Access)
2. Verifique a senha no `.env`
3. Verifique se o cluster está "Running" (não parado)

### Erro: "Authentication failed"
**Problema**: Senha incorreta
**Solução**:
1. Clique em "Database Access"
2. Copie exatamente a senha (use "Copy")
3. Substitua no `.env`

### Erro: "Invalid connection string"
**Problema**: Connection string malformada
**Solução**:
1. Copie novamente de MongoDB Atlas
2. Verifique se substitui PASSWORD corretamente
3. Não adicione espaços extras

### Erro: "Database does not exist"
**Problema**: MongoDB criará automaticamente
**Solução**: Não precisa fazer nada, é normal!

---

## 📈 Monitorar Seu Cluster

### No Dashboard MongoDB Atlas

1. **Métricas**
   - Vá para "Metrics"
   - Veja CPU, memória, conexões

2. **Logs**
   - Vá para "Logs"
   - Veja erros e warnings

3. **Backups**
   - Vá para "Backup" (plano pago)
   - Configure backup automático

---

## 🔄 Migrar Dados de PostgreSQL para MongoDB

Se tinha dados em PostgreSQL, pode migrar:

```python
# Exemplo: Exportar de PostgreSQL para MongoDB
import json
import asyncio
from sqlalchemy import create_engine
from motor.motor_asyncio import AsyncClient

async def migrate_data():
    # Conectar ao MongoDB
    client = AsyncClient("mongodb+srv://user:pass@cluster.mongodb.net/db")
    db = client['crypto_trade_hub']
    
    # Exportar dados (você pode fazer com CSV também)
    # Aqui é um exemplo simplificado
    
    await db['users'].insert_many([...])  # Inserir dados
    
    client.close()

asyncio.run(migrate_data())
```

Para dados grandes, use:
- **MongoDB Compass**: GUI para gerenciar dados
- **mongoexport/mongoimport**: Ferramentas CLI
- **Custom Python script**: Para transformações complexas

---

## 🎯 Próximos Passos

1. ✅ Criar conta MongoDB Atlas
2. ✅ Criar cluster
3. ✅ Criar usuário
4. ✅ Liberar IP
5. ✅ Copiar connection string
6. ✅ Atualizar `.env`
7. ✅ Instalar `motor` e `pymongo`
8. ✅ Testar conexão
9. ✅ Pronto para usar!

---

## 📚 Referências

- **MongoDB Atlas**: https://cloud.mongodb.com/
- **Motor (Driver Async)**: https://motor.readthedocs.io/
- **MongoDB Docs**: https://docs.mongodb.com/
- **PyMongo**: https://pymongo.readthedocs.io/

---

**Data**: 2026-02-03  
**Status**: ✅ MongoDB Configurado  
**Próximos**: Migrar repositórios para MongoDB
