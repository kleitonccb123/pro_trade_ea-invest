# 🔧 VS Code AI Prompt para Migração SQLAlchemy → Motor

Use este prompt no VS Code Chat (Ctrl+L ou Ctrl+I) para refatorar automaticamente seus arquivos de banco de dados.

## ✅ Prerequisitos

- Motor instalado: `pip install motor`
- Database.py com funções `get_db()` e `get_collection(name)` implementadas
- Arquivo Python aberto no editor que você quer converter

## 📋 Prompt para Copiar e Colar

```
Atue como um Especialista em Python e MongoDB. 
Estamos migrando este projeto de SQLAlchemy para Motor (MongoDB Async).

CONTEXTO:
- Temos uma conexão ativa em backend/app/core/database.py com:
  - get_db() → retorna AsyncIOMotorDatabase
  - get_collection(name) → retorna AsyncIOMotorCollection
  - Motor já está instalado e funcionando

TAREFA:
Refatore o código ABAIXO para remover TODAS as dependências do SQLAlchemy:
- AsyncSession
- db.add()
- db.commit()
- db.query()
- db.execute(select(...))
- db.refresh()

SUBSTITUA POR:
- db = get_db() ou get_collection('nome_colecao')
- await db['colecao'].find_one({'_id': id})
- await db['colecao'].find({'campo': valor}).to_list(None)
- await db['colecao'].insert_one({...})
- await db['colecao'].update_one({'_id': id}, {'$set': {...}})
- await db['colecao'].delete_one({'_id': id})

REGRAS IMPORTANTES:
1. Remova async with AsyncSessionLocal() as db
2. Use ObjectId quando precisar converter string para ObjectId de MongoDB: from bson import ObjectId
3. Mantenha o comportamento assíncrono (async/await)
4. Não remova db.commit() ou db.refresh() silenciosamente - eles não existem em MongoDB
5. Converta operações ORM para queries MongoDB:
   - db.query(User).filter(User.id == id).first() → await db['users'].find_one({'_id': id})
   - db.query(User).all() → await db['users'].find({}).to_list(None)
6. Se houver conversão de ObjectId, adicione: from bson import ObjectId
7. Manter toda a lógica de negócio intacta

FORMATO DE RESPOSTA:
1. Mostre a versão refatorada do código
2. Destaque as mudanças principais (use ##)
3. Se houver problemas, sugira soluções específicas
4. Lista final de imports necessários

Aqui está o código para refatorar:
```

## 🎯 Como Usar

### Opção 1: Refatorar Arquivo Individual
1. Abra o arquivo em VS Code (ex: `backend/app/bots/service.py`)
2. Pressione `Ctrl+L` (ou `Ctrl+I`)
3. Cole o prompt acima seguido do seu código
4. O AI refatorará automaticamente

### Opção 2: Refatorar com Seleção
1. Abra o arquivo
2. Selecione o trecho de código que quer refatorar
3. Pressione `Ctrl+L`
4. Cole o prompt + código selecionado
5. O AI converterá apenas aquela seção

## 📁 Ordem de Refatoração Recomendada

Comece pelos arquivos mais críticos (menos dependências):

```
1. ✅ backend/app/core/scheduler.py (JÁ FEITO)
2. ✅ backend/app/analytics/service.py (JÁ FEITO)
3. ⏭️ backend/app/bots/service.py (13 AsyncSessionLocal)
4. ⏭️ backend/app/notifications/service.py (13 AsyncSessionLocal)
5. ⏭️ backend/app/users/repository.py
6. ⏭️ backend/app/strategies/repository.py
7. ⏭️ backend/app/bots/repository.py
8. ⏭️ backend/app/trading/repository.py
```

## 🔍 Padrões de Conversão Rápida

### Padrão 1: Consulta Simples
```python
# ❌ ANTES (SQLAlchemy)
async with AsyncSessionLocal() as db:
    user = await db.query(User).filter(User.id == user_id).first()

# ✅ DEPOIS (Motor)
db = get_db()
user = await db['users'].find_one({'_id': user_id})
```

### Padrão 2: Listar Todos os Registros
```python
# ❌ ANTES
async with AsyncSessionLocal() as db:
    items = await db.query(Item).all()

# ✅ DEPOIS
db = get_db()
items = await db['items'].find({}).to_list(None)
```

### Padrão 3: Inserir Documento
```python
# ❌ ANTES
async with AsyncSessionLocal() as db:
    new_user = User(name="João", email="joao@email.com")
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

# ✅ DEPOIS
db = get_db()
result = await db['users'].insert_one({'name': 'João', 'email': 'joao@email.com'})
user = await db['users'].find_one({'_id': result.inserted_id})
return user
```

### Padrão 4: Atualizar Documento
```python
# ❌ ANTES
async with AsyncSessionLocal() as db:
    user = await db.query(User).filter(User.id == user_id).first()
    user.name = "Novo Nome"
    db.commit()

# ✅ DEPOIS
db = get_db()
await db['users'].update_one(
    {'_id': user_id},
    {'$set': {'name': 'Novo Nome'}}
)
```

### Padrão 5: Deletar Documento
```python
# ❌ ANTES
async with AsyncSessionLocal() as db:
    user = await db.query(User).filter(User.id == user_id).first()
    db.delete(user)
    db.commit()

# ✅ DEPOIS
db = get_db()
await db['users'].delete_one({'_id': user_id})
```

### Padrão 6: Filtro Complexo
```python
# ❌ ANTES
async with AsyncSessionLocal() as db:
    bots = await db.query(Bot).filter(
        Bot.user_id == user_id, 
        Bot.state == 'running'
    ).all()

# ✅ DEPOIS
db = get_db()
bots = await db['bots'].find({
    'user_id': user_id,
    'state': 'running'
}).to_list(None)
```

## 🛠️ Verificação Pós-Refatoração

Após refatorar, verifique:

```bash
# 1. Remova imports não utilizados
grep -r "AsyncSessionLocal" backend/app/

# 2. Remova imports do SQLAlchemy
grep -r "from sqlalchemy" backend/app/

# 3. Teste o servidor
python run_server_no_reload.py

# 4. Verifique os logs por erros de conexão
```

## 📊 Nomes das Coleções MongoDB

Mapeamento de tabelas SQL para coleções MongoDB:

| Tabela SQL | Coleção MongoDB |
|-----------|-----------------|
| users | `db['users']` |
| bots | `db['bots']` |
| bot_instances | `db['bot_instances']` |
| simulated_trades | `db['simulated_trades']` |
| user_strategies | `db['user_strategies']` |
| strategy_bot_instances | `db['strategy_bot_instances']` |
| strategy_trades | `db['strategy_trades']` |
| notifications | `db['notifications']` |
| price_alerts | `db['price_alerts']` |

## 🚨 Erros Comuns e Soluções

| Erro | Causa | Solução |
|------|-------|--------|
| `NameError: name 'AsyncSessionLocal' is not defined` | Ainda usando AsyncSessionLocal | Use `db = get_db()` |
| `AttributeError: 'dict' object has no attribute 'name'` | Acessando MongoDB doc como objeto | Use `doc.get('name')` ou `doc['name']` |
| `bson.errors.InvalidId: invalid ObjectId` | ObjectId string inválida | Use `from bson import ObjectId; ObjectId(string)` |
| `RuntimeError: MongoDB não está conectado` | get_db() chamado antes do startup | Certifique-se de connect_db() no lifespan |

## 📞 Suporte

Se encontrar problemas, use este checklist:

- [ ] Motor está instalado? `pip install motor`
- [ ] database.py tem `get_db()`?
- [ ] MongoDB está conectado? Veja logs no startup
- [ ] Todos os imports foram atualizados?
- [ ] Servidor inicia sem erros?

---

**Versão**: 1.0 | **Data**: Feb 2026 | **Status**: ✅ Pronto para uso
