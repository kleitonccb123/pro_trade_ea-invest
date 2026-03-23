# KuCoin Onboarding Flow

## Visão Geral

O sistema Crypto Trade Hub agora exibe uma tela de onboarding para usuários que ainda não configuraram suas credenciais da KuCoin API.

## Fluxo do Usuário

### 1. **Tutorial Inicial**
- Exibe um aviso destacado: **"Este sistema funciona exclusivamente com KuCoin"**
- Mostra benefícios da plataforma
- Exibe um placeholder para tutorial em vídeo
- Passos rápidos para obter as credenciais

### 2. **Verificação de Conta**
- Pergunta ao usuário: "*Você já tem uma conta KuCoin?*"
- **Se SIM**: Abre formulário para inserir credenciais
- **Se NÃO**: Redireciona para `https://www.kucoin.com/ucenter/signup`

### 3. **Formulário de Credenciais**
Campos para preenchimento:
- **API Key**: Sua chave de acesso
- **API Secret**: Seu código secreto
- **API Passphrase**: Sua senha de API (exclusiva do KuCoin)
- **Modo Sandbox**: Toggle para ativar testes (padrão: ativado)

#### Segurança
- Dados são encriptados no backend antes de armazenar
- Utilizamos Fernet encryption (Python)
- Token JWT obrigatório para todas as requisições

### 4. **Após Sucesso**
- Credenciais salvas no banco de dados
- Dashboard carrega com dados reais da KuCoin
- Componente de onboarding desaparece

## Componentes

### `KuCoinOnboarding.tsx`
- Local: `src/components/KuCoinOnboarding.tsx`
- Gerencia todo o fluxo de onboarding
- Comunica com endpoint: `POST /api/trading/credentials`
- Verifica status com: `GET /api/trading/kucoin/status`

### `Dashboard.tsx`
- Atualizado para verificar credenciais ao carregar
- Exibe onboarding se `has_kucoin_credentials === false`
- Callback `onCredentialsAdded()` para atualizar estado

## Backend Integration

### Verificar Status
```bash
GET /api/trading/kucoin/status
Authorization: Bearer {token}
```

Resposta (sem credenciais):
```json
{
  "connected": false,
  "status": "not_configured",
  "error": "Credenciais não configuradas"
}
```

### Criar Credenciais
```bash
POST /api/trading/credentials
Content-Type: application/json
Authorization: Bearer {token}

{
  "exchange": "kucoin",
  "api_key": "...",
  "api_secret": "...",
  "api_passphrase": "...",
  "is_sandbox": true
}
```

## Próximas Melhorias

- [ ] Integrar vídeo real do YouTube no tutorial
- [ ] Adicionar teste de conexão antes de salvar
- [ ] Mostrar histórico de tentativas de conexão
- [ ] Suporte para múltiplas exchanges (Binance, Bybit, etc.)
- [ ] Cache de status para reduzir requisições
