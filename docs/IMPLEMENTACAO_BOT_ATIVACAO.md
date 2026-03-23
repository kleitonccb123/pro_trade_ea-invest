# Guia de Implementação — Fluxo de Ativação de Robô

> **Objetivo:** Ao clicar em "Ativar" no card de um robô desbloqueado → fechar modal atual → abrir popup de configuração (par, TP, SL, investimento, timeframe) → ao confirmar, navegar para o Dashboard com banner do robô ativo e gráfico KuCoin em tempo real.

---

## 1. Arquitetura do Fluxo

```
RobotsGameMarketplace
  └── RobotMarketplaceCard
        └── [clique em "Ativar"]
              ↓
        handleActivateRobot(robotId)
              ↓
        fecha modais existentes
              ↓
        abre BotConfigModal
              ↓
        [clique em "Ativar e ir para o Dashboard"]
              ↓
        salva em localStorage('active_bot_config')
              ↓
        navigate('/dashboard')
              ↓
        Dashboard.tsx lê localStorage
              ↓
        passa activeBotConfig para KuCoinDashboard
              ↓
        KuCoinDashboard exibe banner "Robô Ativo"
```

---

## 2. Arquivos Criados

### `src/services/exchangeService.ts`
Serviço frontend que encapsula os endpoints de credenciais de exchange.

**Funções:**
- `saveCredentials(data)` → `POST /user/settings/exchanges`
- `listCredentials()` → `GET /user/settings/exchanges`
- `getCredential(exchange)` → filtra a lista pelo nome da exchange
- `removeCredentials(exchange)` → `DELETE /user/settings/exchanges/{exchange}`

**Por que foi necessário?**
O botão "Salvar Configuração" em `Settings.tsx` apenas exibia um toast e nunca enviava dados ao backend. Este serviço conecta o frontend ao endpoint que já existia.

---

### `src/components/gamification/BotConfigModal.tsx`
Modal de configuração do robô, exibido após clicar em "Ativar".

**Campos do formulário:**
| Campo | Tipo | Validação |
|---|---|---|
| Par de criptomoeda | Select (10 pares) | Obrigatório |
| Investimento (USDT) | Número | Mínimo: $10 |
| Take Profit % | Número | Mínimo: 0.1% |
| Stop Loss % | Número | Mínimo: 0.1%, deve ser < TP |
| Timeframe | Botões (1m/5m/15m/30m/1h/4h/1d) | Obrigatório |
| Máx. trades/dia | Número | Mínimo: 1 |

**Interface `BotConfig` exportada:**
```ts
export interface BotConfig {
  robotId: string;
  robotName: string;
  robotStrategy: string;
  pair: string;
  investmentUsdt: number;
  takeProfitPct: number;
  stopLossPct: number;
  timeframe: string;
  maxTradesPerDay: number;
  activatedAt: string; // ISO timestamp
}
```

---

## 3. Arquivos Modificados

### `src/pages/Settings.tsx`
**Problema:** Passphrase da KuCoin não tinha campo. Dados nunca eram enviados ao backend.

**Alterações:**
- Campo de Passphrase adicionado (obrigatório para KuCoin)
- Ao montar o componente: lê credencial salva via `exchangeService.getCredential('kucoin')`
- Banner de status de conexão (verde = conectado, vermelho = desconectado)
- Botão "Salvar Config" chama `handleSaveExchange()` → POST no backend
- Botão "Testar Conexão" re-verifica o status

---

### `src/components/gamification/RobotMarketplaceCard.tsx`
**Problema:** O botão "Ativar" só chamava `e.stopPropagation()` — não fazia nada de útil.

**Alteração:**
```ts
// Props adicionadas:
onActivate?: (robotId: string) => void;

// Botão agora chama:
onActivate?.(robot.id)
```

---

### `src/pages/RobotsGameMarketplace.tsx`
**Alterações:**
- Import de `useNavigate` e `BotConfigModal`
- Estados: `isBotConfigModalOpen`, `selectedBotForConfig`
- Função `handleActivateRobot(robotId)`:
  1. Busca o robô pelo ID (em `topRobots` ou `mockRobots`)
  2. Fecha `isModalOpen` e `isUnlockModalOpen`
  3. Define `selectedBotForConfig`
  4. Abre `BotConfigModal`
- Prop `onActivate={handleActivateRobot}` em ambas as grids de cards
- `<BotConfigModal>` renderizado ao final do componente

---

### `src/components/kucoin/KuCoinDashboard.tsx`
**Alterações:**
- Import de `BotConfig` e ícones adicionais (`Target`, `ShieldAlert`, `Clock`, `Activity`)
- `KuCoinDashboardProps` agora aceita `activeBotConfig?: BotConfig | null`
- Banner "Robô Ativo" exibido no topo quando `activeBotConfig` está definido:
  - Nome do robô
  - Par operado
  - Take Profit %
  - Stop Loss %
  - Investimento em USDT
  - Timeframe
  - Indicador pulsante "Operando"

---

### `src/pages/Dashboard.tsx`
**Alterações:**
- Import de `BotConfig`
- Estado lazy `activeBotConfig` lido do `localStorage` na montagem:
  ```ts
  const [activeBotConfig, setActiveBotConfig] = useState<BotConfig | null>(() => {
    const saved = localStorage.getItem('active_bot_config');
    return saved ? JSON.parse(saved) : null;
  });
  ```
- `<KuCoinDashboard>` recebe `activeBotConfig={activeBotConfig}`

---

## 4. Erros Possíveis e Soluções

### ❌ Erro 1: Credenciais KuCoin não configuradas ao ativar o robô

**Sintoma:** O Dashboard redireciona para o onboarding da KuCoin em vez de mostrar o dashboard mesmo após ativar o robô.

**Causa:** `localStorage('kucoin_connected')` está ausente ou `false` — o usuário não configurou as credenciais antes de ativar o robô.

**Solução:**
- Verificar se há credenciais em Settings → Exchange antes de ativar um robô
- Opcionalmente: ao clicar em "Ativar", verificar se `kucoin_connected === 'true'` e exibir aviso

---

### ❌ Erro 2: Passphrase da KuCoin ausente (HTTP 422)

**Sintoma:** Ao tentar salvar as credenciais em Settings, a API retorna erro 422.

**Causa:** A KuCoin exige três campos: `api_key`, `api_secret` e `passphrase`. Anteriormente o sistema não tinha campo de passphrase.

**Solução:** O campo foi adicionado. Sempre preencher os três campos ao configurar a exchange.

---

### ❌ Erro 3: TP ≤ SL no formulário de configuração

**Sintoma:** Ao tentar ativar o robô, o formulário mostra erro "Stop Loss deve ser menor que Take Profit".

**Causa:** O `stopLossPct` inserido é maior ou igual ao `takeProfitPct`.

**Solução:** Exemplo válido: TP = 2%, SL = 1%. A validação bloqueia a submissão e exibe mensagem de erro inline.

---

### ❌ Erro 4: Banner "Robô Ativo" não aparece após navegar para o Dashboard

**Sintoma:** A configuração foi salva, a navegação ocorreu, mas o banner não aparece.

**Causas possíveis:**
1. `localStorage.getItem('active_bot_config')` retornou `null` (limpeza de browser data)
2. JSON corrompido no localStorage
3. O import de `BotConfig` falhou (verifique o caminho do import)

**Solução:**
- `Dashboard.tsx` usa try/catch ao fazer o `JSON.parse` — retorna `null` em caso de JSON inválido
- Se o localStorage foi limpo, refaça o fluxo de ativação pelo marketplace

---

### ❌ Erro 5: Erro 401 ao salvar credenciais

**Sintoma:** `handleSaveExchange()` retorna erro 401.

**Causa:** Token JWT expirado ou ausente.

**Solução:** O `apiClient.ts` tenta renovar o token automaticamente. Se persistir, faça logout e login novamente. Verifique que `authService.getAccessToken()` retorna um token válido antes de chamar o serviço.

---

### ❌ Erro 6: CCXT valida as credenciais como inválidas (HTTP 400)

**Sintoma:** "Credenciais inválidas" ao salvar na troca.

**Causa:** A chave API, secret ou passphrase não são válidos no sandbox/produção da KuCoin.

**Solução:**
1. Verificar se a API key foi criada no painel da KuCoin com permissões de leitura e trading
2. Verificar se o modo `sandbox` está correto (chaves de sandbox não funcionam em produção e vice-versa)
3. Confirmar a passphrase — é a que foi definida ao criar a API key, não a senha da conta

---

### ❌ Erro 7: `onActivate` não fecha o modal anterior

**Sintoma:** Dois modais abertos ao mesmo tempo (LockedRobotModal + BotConfigModal).

**Causa:** `handleActivateRobot` não fechou todos os estados de modal antes de abrir o novo.

**Solução:** A implementação chama explicitamente:
```ts
setIsModalOpen(false);
setIsUnlockModalOpen(false);
```
antes de `setIsBotConfigModalOpen(true)`. Verifique se há outros estados de modal não tratados.

---

### ❌ Erro 8: localStorage limpo (browser mode privado / política de segurança)

**Sintoma:** Os dados do robô ativo são perdidos ao recarregar a página.

**Causa:** Modo de navegação anônima, política de segurança do browser, ou limpeza manual de dados.

**Solução de longo prazo:** Persistir `active_bot_config` no backend (tabela `active_bots` no MongoDB), carregando via API no `useEffect` do `Dashboard.tsx`. Para a versão atual, o localStorage é suficiente para demonstração.

---

## 5. Passo a Passo para Testar o Fluxo Completo

1. **Configurar credenciais KuCoin:**
   - Acesse Settings → Exchange
   - Preencha API Key, API Secret e Passphrase
   - Clique em "Salvar Config"
   - Aguarde o banner verde "Conectado"

2. **Ativar um robô:**
   - Acesse Marketplace de Robôs
   - Encontre um robô desbloqueado
   - Clique no card para abrir o modal
   - Clique em "Ativar" (botão verde)
   - O modal de configuração abrirá

3. **Configurar o robô:**
   - Selecione o par (ex: BTC-USDT)
   - Defina o investimento (ex: $100 USDT)
   - Defina Take Profit (ex: 2%)
   - Defina Stop Loss (ex: 1%)
   - Selecione o timeframe (ex: 1h)
   - Clique em "Ativar e ir para o Dashboard"

4. **Verificar o Dashboard:**
   - O banner "Robô Ativo" deve aparecer no topo
   - Par, TP, SL, investimento e timeframe devem ser exibidos
   - O indicador pulsante "Operando" deve aparecer

---

## 6. Estrutura de Dados no localStorage

```json
// Chave: "active_bot_config"
{
  "robotId": "scalper-pro",
  "robotName": "Scalper Pro",
  "robotStrategy": "Scalping de alta frequência",
  "pair": "BTC-USDT",
  "investmentUsdt": 100,
  "takeProfitPct": 2,
  "stopLossPct": 1,
  "timeframe": "1h",
  "maxTradesPerDay": 10,
  "activatedAt": "2024-01-15T14:30:00.000Z"
}

// Chave: "kucoin_connected"
"true"
```

---

## 7. Dependências Envolvidas

| Pacote | Uso |
|---|---|
| `framer-motion` | Animações dos modais |
| `shadcn/ui` (Dialog, Input, Button, Label) | Componentes base dos modais |
| `react-router-dom` (useNavigate) | Navegação após ativação |
| `lucide-react` | Ícones (Target, ShieldAlert, Clock, Activity, Bot) |
| `ccxt` (backend Python) | Validação das credenciais de exchange |
| `Motor` (MongoDB async) | Persistência das credenciais no banco |

---

*Documento gerado automaticamente. Última atualização: implementação do fluxo completo de ativação de robô.*
