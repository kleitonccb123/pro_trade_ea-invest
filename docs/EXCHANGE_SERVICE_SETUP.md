# 🛠️ Passo 6: Serviço de Exchange - Configuração da KuCoin

## 📋 Visão Geral

O **Exchange Service** foi criado para permitir que seus robôs executem ordens reais de compra e venda na KuCoin usando a biblioteca CCXT.

## 🔧 Instalação

As dependências já foram instaladas:
- `ccxt` - Biblioteca para integração com exchanges
- `python-dotenv` - Para carregar variáveis de ambiente

## ⚙️ Configuração das Chaves API

### 1. Criar Conta na KuCoin

Para testes seguros, recomendamos começar com uma conta KuCoin real mas com pouco saldo:

1. Acesse [KuCoin](https://www.kucoin.com)
2. Crie uma conta gratuita
3. Deposite uma pequena quantia (ex: $10-20) para testes

### 2. Gerar Chaves API

1. Faça login na sua conta KuCoin
2. Vá em **API Management** (no menu lateral)
3. Clique em **Create API**
4. Configure:
   - **API Name**: `CryptoTradeHub`
   - **Security**: `General` (para começar)
   - **Passphrase**: Crie uma senha segura
   - **IP Restriction**: Deixe vazio por enquanto
5. Anote as credenciais geradas:
   - **API Key**
   - **API Secret**
   - **API Passphrase**

### 3. Configurar no Projeto

Edite o arquivo `backend/.env` e substitua os valores:

```env
KUCOIN_API_KEY=sua_api_key_aqui
KUCOIN_API_SECRET=seu_api_secret_aqui
KUCOIN_API_PASSPHRASE=sua_passphrase_aqui
```

## 🧪 Teste da Configuração

Após configurar as chaves, teste a conexão:

```bash
cd backend
python -c "
import asyncio
from app.services.exchange_service import exchange_service

async def test():
    balance = await exchange_service.get_balance()
    print('Saldo:', balance)
    await exchange_service.close()

asyncio.run(test())
"
```

## 📊 Funcionalidades Disponíveis

### Buscar Saldo
```python
balance = await exchange_service.get_balance()
print(balance['USDT'])  # Saldo em USDT
```

### Criar Ordem de Compra/Venda
```python
# Ordem de mercado (execução imediata)
order = await exchange_service.create_order(
    symbol='BTC/USDT',
    side='buy',  # ou 'sell'
    amount=0.001,  # quantidade em BTC
    type='market'
)

# Ordem limite (preço fixo)
order = await exchange_service.create_order(
    symbol='BTC/USDT',
    side='buy',
    amount=0.001,
    price=50000,  # preço em USDT
    type='limit'
)
```

## ⚠️ Avisos de Segurança

1. **Nunca use chaves de conta real com muito saldo** para testes
2. **Restrinja IPs** nas configurações da API KuCoin quando em produção
3. **Use apenas permissões necessárias** (evite trade permissions desnecessárias)
4. **Guarde as chaves em local seguro** - nunca commite no Git

## 🔄 Próximos Passos

Após configurar e testar:
1. **Passo 7**: Integrar o Exchange Service com os robôs
2. **Passo 8**: Implementar lógica de execução automática
3. **Passo 9**: Adicionar validações e limites de risco

## 🆘 Troubleshooting

### Erro: "kucoin GET https://api.kucoin.com/api/v3/currencies"
- **Causa**: Chaves API inválidas ou não configuradas
- **Solução**: Verifique se as chaves no `.env` estão corretas

### Erro: "API key not found"
- **Causa**: Chave API não existe ou foi deletada
- **Solução**: Gere novas chaves na KuCoin

### Erro: "Permission denied"
- **Causa**: Chave API sem permissões de trading
- **Solução**: Habilite permissões de trade na configuração da API