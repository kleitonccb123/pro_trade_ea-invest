# 📄 Documentação Completa — Página `/robots`

> **Rota:** `http://localhost:8081/robots`  
> **Componente principal:** `src/pages/RobotsGameMarketplace.tsx`  
> **Data da análise:** 26 de fevereiro de 2026

---

## 1. VISÃO GERAL

A página `/robots` é a **Arena de Lucros** — um marketplace gamificado de robôs de trading. O conceito central é: o usuário acumula **TradePoints** (pontos internos) por meio de ações no sistema (abrir baú diário, comprar licença, atingir metas) e usa esses pontos para desbloquear robôs estratégicos que operam 24/7 na exchange KuCoin.

### Rota no App.tsx
```
/robots         → RobotsGameMarketplace  ← PÁGINA ANALISADA
/robots/crypto  → CryptoRobots           (rota alternativa, não usada na nav)
```

> ⚠️ Existem 4 arquivos de robôs no projeto (`Robots.tsx`, `RobotsPage.tsx`, `RobotsGameMarketplace.tsx`, `CryptoRobots.tsx`). Apenas `RobotsGameMarketplace.tsx` está ativo na rota `/robots`.

---

## 2. ARQUITETURA DE COMPONENTES

```
RobotsGameMarketplace.tsx (página principal)
│
├── [Background animado] — blobs de gradiente + grid pattern
│
├── Header — título "Arena de Lucros"
│
├── GameProfileWidget.tsx
│   ├── TradePoints (amarelo neon)
│   ├── Level + barra de XP
│   ├── StreakBadge.tsx — streak de baú diário
│   └── DailyChestComponent.tsx — timer regressivo + abrir baú
│
├── DailyChestButton.tsx — atalho rápido para abrir o baú diário
│
├── Banner informativo — "Ranking atualiza a cada 15 dias"
│
├── Painel de Slots — visualização dos 0–20 slots desbloqueados
│
├── Seção "Top 10 Ranking"
│   ├── Seletor de período (24h / Semana / Mês)
│   └── Grid 5 colunas → RobotMarketplaceCard (×10)
│
├── Seção "Todos os 20 Robôs"
│   └── Grid 4–5 colunas → RobotMarketplaceCard (×20)
│
├── Footer — explicação sobre como desbloquear
│
├── LockedRobotModal.tsx — modal de info de robô bloqueado
├── UnlockRobotModal.tsx — modal de confirmação de desbloqueio
├── RankingPeriodSelector.tsx — modal para selecionar período de ranking
└── LevelUpModal.tsx — modal que aparece quando o usuário sobe de nível
```

---

## 3. O QUE JÁ EXISTE E FUNCIONA

### 3.1 Visual / UI

| Componente | Status | Observação |
|---|---|---|
| Background animado (blobs + grid) | ✅ Funciona | Gradientes amarelo/laranja, grid sutil |
| Header gamificado | ✅ Funciona | Título em gradiente, badge "Arena de Lucros" |
| `GameProfileWidget` | ✅ Funciona | Conectado ao backend via `useGamification` |
| TradePoints display | ✅ Funciona | Número animado com `NumberAnimator` |
| Barra de XP / Level | ✅ Funciona | `xp_progress_percent` via API |
| Streak badge | ✅ Funciona | Mostra dias consecutivos de baú |
| `DailyChestButton` | ✅ Funciona | Abre baú → ganha 10–50 pts |
| Timer regressive do baú | ✅ Funciona | Contagem regressiva até próximo baú |
| Banner "Ranking 15 dias" | ✅ Funciona | UI estática, informativo |
| Painel de slots 0/20 | ✅ Funciona | Animação nos quadradinhos |
| Grid "Top 10" | ✅ Funciona | Tenta API, fallback para mock |
| Grid "Todos os 20" | ✅ Funciona | Sempre dados mock |
| `RobotMarketplaceCard` | ✅ Funciona | Cards com lock, on fire, medalhas |
| Animação hover nos cards | ✅ Funciona | `y: -8` no hover |
| `LockedRobotModal` | ✅ Funciona | Exibe info do robô, custo |
| `UnlockRobotModal` | ✅ Funciona | Confirmação + animação de cadeado |
| `RankingPeriodSelector` | ✅ Funciona | Alterna 24h / semana / mês |
| `LevelUpModal` | ✅ Funciona | Aparece ao subir de nível |
| Design responsivo | ⚠️ Parcial | Grid funciona, mas cards muito pequenos no mobile |

### 3.2 Backend / Integração

| Endpoint | Status | Uso |
|---|---|---|
| `GET /api/gamification/profile` | ✅ Implementado | Carrega dados do perfil (pontos, XP, level) |
| `POST /api/gamification/daily-chest/open` | ✅ Implementado | Abre baú diário |
| `POST /api/gamification/robots/{id}/unlock` | ✅ Implementado | Debita pontos e desbloqueia robô |
| `GET /api/gamification/robots/ranking-by-period` | ✅ Implementado | Ranking dinâmico com fallback mock |
| `GET /api/gamification/leaderboard` | ✅ Implementado | Placar global de usuários |

### 3.3 Gamificação (sistema de pontos)

- **TradePoints** são convertíveis em robôs desbloqueados
- Custo dos robôs: 360–600 pts (robôs comuns) | 1.500 pts (robôs elite)
- Baú diário: 10–50 pontos por abertura
- XP por ações: cada trade, abertura de baú, desbloqueio gera XP
- Levels: incrementam com XP, desbloqueiam badges e conquistas

---

## 4. O QUE ESTÁ FALTANDO / QUEBRADO

### 4.1 🔴 Crítico — Não Funciona

#### 4.1.1 Botão "Ativar" não faz nada
```tsx
// RobotMarketplaceCard.tsx — botão do robô desbloqueado:
<motion.button
  onClick={(e) => {
    e.stopPropagation(); // ← apenas bloqueia propagação, SEM ação
  }}
>
  <Zap /> Ativar
</motion.button>
```
**Impacto:** O usuário desbloqueia um robô gastando pontos, clica em "Ativar" e **nada acontece**. Esse é o fluxo mais crítico da página.

**Correção necessária:** O botão deve navegar para uma tela de configuração do robô (pares, capital, stop loss) ou chamar a API para ativar o bot na KuCoin.

#### 4.1.2 Ranking API sem token de autenticação
```tsx
// RobotsGameMarketplace.tsx — linha ~418:
const response = await fetch(
  `/api/gamification/robots/ranking-by-period?period=${period}&limit=10`,
  {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
      // ← Authorization: `Bearer ${token}` AUSENTE
    },
  }
);
```
**Impacto:** O backend protege a rota com `get_current_user`, então a chamada retorna 401 e o sistema sempre cai no fallback de dados mock. O Top 10 **nunca mostra dados reais**.

#### 4.1.3 Todos os 20 robôs são 100% hardcoded (mock)
```tsx
// RobotsGameMarketplace.tsx — linha ~800:
{mockRobots.map((robot, i) => { ... })}
```
Os dados de lucro (`profit_15d`, `win_rate`, `total_trades`) são valores fictícios fixos no código. Não há bot real executando na KuCoin gerando esses números.

#### 4.1.4 `LockedRobotModal` não tem `onUnlockWithPoints` conectado
```tsx
// RobotsGameMarketplace.tsx:
<LockedRobotModal
  robot={selectedRobot}
  isOpen={isModalOpen}
  onClose={() => setIsModalOpen(false)}
  userTradePoints={profile?.trade_points || 0}
  onUpgradePlan={() => { console.log('Ir para planos'); }} // ← apenas console.log
  // onUnlockWithPoints ← NÃO ESTÁ PASSADO
/>
```
O modal tem o botão "Desbloquear com Pontos" mas o handler não está conectado à função de unlock.

---

### 4.2 🟡 Importante — Incompleto

#### 4.2.1 Prop `planLimitReached` nunca é passada para os cards
```tsx
// RobotMarketplaceCard.tsx:
interface RobotMarketplaceCardProps {
  planLimitReached?: boolean;  // ← definida na interface
}
// Em RobotsGameMarketplace.tsx:
<RobotMarketplaceCard
  robot={{ ...robot, is_locked: !isUnlocked }}
  onUnlock={() => handleUnlockClick(robot.id)}
  onInfo={handleRobotInfo}
  // planLimitReached ← NUNCA PASSADO
/>
```
O badge "Limite Atingido" que deveria aparecer quando o plano do usuário atingiu o limite de robôs ativos nunca é exibido.

#### 4.2.2 "Ir para planos" não navega
```tsx
onUpgradePlan={() => {
  // TODO: Navegar para página de planos
  console.log('Ir para planos');
}}
```
Deveria usar `useNavigate()` para ir para `/plans` ou `/subscription`.

#### 4.2.3 Falta busca e filtro no grid completo
O grid de "Todos os 20 Robôs" não tem:
- Campo de busca por nome
- Filtro por estratégia (Grid, RSI, MACD, DCA, Combined)
- Ordenação por lucro, win rate, custo

#### 4.2.4 Falta página de detalhes do robô
Ao clicar em "Info" de um robô desbloqueado, o `handleRobotInfo` abre o `LockedRobotModal` (modal genérico). Não existe uma página dedicada com:
- Histórico de operações do robô
- Gráfico de performance
- Configurações de ativação

#### 4.2.5 Dados do painel de slots desatualizam após desbloqueio
O painel "X de 20 slots" mostra `profile?.unlocked_robots?.length` mas após desbloquear, o `profile` só é atualizado quando o hook refaz a chamada à API. Não há atualização otimista imediata.

#### 4.2.6 Robôs do Top 10 duplicam o grid completo
A página mostra primeiro "Top 10" (com os mesmos de bot_001–bot_010) e depois "Todos os 20 Robôs" (list completa incluindo os mesmos 10). O usuário vê os primeiros cards duas vezes.

---

### 4.3 🟠 Visual / UX — Pode Melhorar

#### 4.3.1 Idioma misto no footer
```tsx
// RobotsGameMarketplace.tsx — rodapé:
<li><strong>Option 1:</strong> Ganhe TradePoints...</li>
<li><strong>Option 2:</strong> Faça upgrade...</li>
<li><strong>Ganhe Automaticamente:</strong>...</li>
```
"Option 1", "Option 2" estão em inglês numa interface em português.

#### 4.3.2 Cards muito compactos em mobile
No breakpoint `sm` (640px) o grid usa 2 colunas e em `lg` usa 4–5 colunas. Em celulares os cards ficam com 165px de largura, cortando textos e tornando os botões pequenos.

#### 4.3.3 Ausência de estado vazio para "todos desbloqueados"
Se o usuário desbloquear todos os 20 robôs, não há tela comemorativa nem estado visual diferenciado. Os cards continuam mostrando botão verde "Ativar" como se fossem novos.

#### 4.3.4 Sem feedback de toast após desbloqueio bem-sucedido
Após desbloquear um robô, o `UnlockRobotModal` fecha mas não há nenhuma notificação toast confirmando "Robô X desbloqueado com sucesso!". O sistema de toast (`useToast`) já existe no projeto.

#### 4.3.5 Sem skeleton loader nos cards durante fetch
Enquanto `isLoadingRobots` é `true`, a área do Top 10 mostra apenas um spinner. Não há skeleton de cards que preserve o layout.

#### 4.3.6 Animações muito pesadas em mobile
Cada card tem `motion.div` com `staggerChildren` e animações `willChange: 'opacity'`. Com 20 cards simultâneos em dispositivos lentos isso causa jank visual.

#### 4.3.7 Botão "Desbloquear" não indica saldo insuficiente no card
No `RobotMarketplaceCard`, o botão "Desbloquear (500⭐)" tem sempre a mesma cor âmbar independente de o usuário ter pontos suficientes. Quando saldo é insuficiente o botão deveria ficar cinza/desabilitado.

#### 4.3.8 Status ON FIRE só para robôs bloqueados
O badge "ON FIRE" com animação só aparece quando `is_on_fire && !is_locked`. Quando o robô é desbloqueado e está em fire, o badge desaparece. Deveria aparecer independente do estado de lock.

---

## 5. ARQUIVOS EXISTENTES MAS NÃO USADOS

Estes arquivos existem no projeto mas **não são renderizados** na rota `/robots`:

| Arquivo | Conteúdo | Status |
|---|---|---|
| `src/pages/Robots.tsx` | Versão antiga com hero section, stats cards, RobotTypeModal | ❌ Não usado |
| `src/pages/RobotsPage.tsx` | Versão intermediária | ❌ Não usado |
| `src/components/robots/RobotCard.tsx` | Card de robô user-owned | ❌ Não usado |
| `src/components/robots/RobotCardNew.tsx` | Versão nova do card | ❌ Não usado |
| `src/components/robots/RobotCardGrid.tsx` | Grid de cards | ❌ Não usado |
| `src/components/robots/CreateRobotModal.tsx` | Modal criação | ❌ Não usado |
| `src/components/robots/RobotConfigModal.tsx` | Config modal | ❌ Não usado |
| `src/components/robots/RobotsChat.tsx` | Chat sobre robôs | ❌ Não usado |
| `src/components/modals/ActiveRobotModal.tsx` | Modal de robô ativo | ❌ Não usado |
| `src/components/modals/RobotTypeModal.tsx` | Seleção de tipo | ❌ Não usado |
| `src/components/ui/robot-strategy-cards.tsx` | Cards de estratégia | ❌ Não usado |
| `src/components/ui/robot-glow-grid.tsx` | Grid com glow | ❌ Não usado |
| `src/components/gamification/RobotSlotLimitModal.tsx` | Modal de limite | ❌ Não importado na página |
| `src/components/dashboard/ActiveRobots.tsx` | Widget de robôs ativos | ❌ Não mostrado em /robots |

**Recomendação:** Avaliar se esses componentes devem ser integrados ou removidos para não acumular dead code.

---

## 6. O QUE FALTA PARA DEIXAR 100%

### Prioridade Alta 🔴

1. **Fluxo pós-desbloqueio — conectar o robô à KuCoin**
   - Ao clicar "Ativar", abrir um modal/página com:
     - Par de trading (BTC/USDT, ETH/USDT, etc.)
     - Capital a alocar (USDT)
     - Stop loss / Take profit
     - Confirmar → chamar `POST /api/trading/bots/start`
   - Mostrar robôs ativos com seus status (lucrando/pausado/operando)

2. **Corrigir autenticação no fetch do ranking**
   - Adicionar `Authorization: Bearer ${accessToken}` no `fetchTopRobotsByPeriod`
   - O Top 10 deve mostrar dados reais do backend

3. **Conectar `onUnlockWithPoints` no `LockedRobotModal`**
   - Passar `onUnlockWithPoints={handleConfirmUnlock}` para o modal

4. **Dados reais dos robôs**
   - Criar no backend um scheduler que executa estratégias (grid, RSI, etc.) na KuCoin sandbox
   - Atualizar `profit_15d`, `win_rate`, `total_trades` com dados reais
   - Expor via `GET /api/gamification/robots/ranking-by-period`

5. **Corrigir navegação "Ir para Planos"**
   - Substituir `console.log('Ir para planos')` por `navigate('/plans')`

---

### Prioridade Média 🟡

6. **Filtro/busca no grid de 20 robôs**
   - Input de busca por nome do robô
   - Filtro dropdown por estratégia
   - Ordenação por: Lucro 15d ↓, Win Rate ↓, Custo ↑

7. **Indicador de saldo insuficiente no card**
   - Se `profile.trade_points < robot.unlock_cost` → botão cinza + tooltip "Pontos insuficientes"

8. **Integrar `planLimitReached`**
   - Comparar `profile.bots_unlocked` com o limite do plano do usuário
   - Passar a prop para os cards

9. **Toast de confirmação pós-desbloqueio**
   ```tsx
   toast({ title: "🎉 Robô desbloqueado!", description: `${robot.name} está pronto para ativar.` })
   ```

10. **Skeleton loader para o grid Top 10**
    - Em vez de spinner, mostrar 10 cards "cinza pulsante" enquanto carrega

11. **Eliminar duplicação Top 10 / Todos os 20**
    - Opção A: Remover a seção "Top 10" e usar apenas o grid completo com filtro de posição
    - Opção B: Na seção "Todos os 20", remover os 10 já exibidos no Top e mostrar apenas os restantes

12. **Atualização otimista após desbloqueio**
    - Ao desbloquear, imediatamente atualizar o estado local antes de esperar o refetch da API

---

### Prioridade Baixa 🟢

13. **Traduzir strings em inglês no footer**
    - "Option 1" → "Opção 1", "Option 2" → "Opção 2"

14. **Estado vazio "Todos desbloqueados"**
    - Quando `unlocked_robots.length === 20`, mostrar uma tela especial de parabéns

15. **Badge ON FIRE independente do lock**
    - Remover a condição `!is_locked` do badge ON FIRE

16. **Otimização de animações em mobile**
    - Usar `useReducedMotion()` do Framer Motion para respeitar preferências do sistema
    - Reduzir stagger em dispositivos com < 8GB RAM

17. **Página de detalhe do robô (`/robots/:id`)**
    - Gráfico de performance histórica (30 dias)
    - Histórico de trades com PnL individual
    - Configurações do robô (se ativo)

18. **Remover ou integrar arquivos mortos**
    - Limpar os 14 arquivos sem uso listados na seção 5

---

## 7. ESTADO VISUAL ATUAL — ANÁLISE DETALHADA

### 7.1 Pontos Fortes do Design

| Aspecto | Avaliação |
|---|---|
| Paleta visual | ✅ Excelente — amarelo neon, slate escuro, gradientes dourados |
| Hierarquia visual | ✅ Boa — título > widget > grid > footer |
| Animações | ✅ Fluidas — Framer Motion bem configurado |
| Cards de robôs | ✅ Bonitos — lock badge animado, medalhas visíveis |
| Glassmorphism no GameProfileWidget | ✅ Premium — blur + borda dourada |
| Contraste de texto | ✅ Adequado — slate-300/400 no fundo slate-950 |

### 7.2 Pontos Fracos do Design

| Aspecto | Problema | Solução |
|---|---|---|
| Cards mobile | 2 colunas deixa botões micro | Usar 1 coluna no `xs`, 2 no `sm` |
| Botão "Ativar" | Visualmente idêntico mas sem ação | Adicionar ícone "play" + cor diferente |
| Sem indicador de saldo | Usuário tenta desbloquear → descobre que não tem pontos | Badge vermelho no botão |
| Footer em inglês | "Option 1/2" quebra imersão | Traduzir |
| Grid duplicado | Conteúdo repetido cansa o usuário | Separar por seção clara ou remover duplicata |
| Sem empty state | Após desbloquear tudo, experiência termina abruptamente | Tela de celebração |

---

## 8. FLUXO COMPLETO ESPERADO (QUANDO 100%)

```
Usuário entra em /robots
      ↓
[GameProfileWidget] mostra pontos, level, streak
      ↓
Visualiza grid de 20 robôs (dados reais da KuCoin)
      ↓
Clica em robô bloqueado
      ↓
[UnlockRobotModal] confirma custo em TradePoints
      ↓
API debita pontos → robô marcado como desbloqueado
      ↓
Toast "Robô desbloqueado!" + atualização otimista do grid
      ↓
Clica em "Ativar" no robô desbloqueado
      ↓
[ActivateRobotModal] escolhe par, capital, stop loss
      ↓
API cria bot na KuCoin (POST /api/trading/bots/start)
      ↓
Robô aparece em [ActiveRobots] no Dashboard com P&L real
      ↓
A cada 15 dias, ranking é recalculado com dados reais → melhor performance = destaque "ON FIRE"
```

---

## 9. CHECKLIST DE IMPLEMENTAÇÃO PARA 100%

### Sprint 1 — Crítico (estimar: 2–3 dias)
- [ ] Adicionar `Authorization` header no `fetchTopRobotsByPeriod`
- [ ] Conectar `onUnlockWithPoints` no `LockedRobotModal`
- [ ] Corrigir botão "Ativar" — criar `ActivateRobotModal` ou navegar para `/robots/:id/activate`
- [ ] Corrigir `onUpgradePlan` para usar `navigate('/plans')`

### Sprint 2 — Importante (estimar: 3–4 dias)
- [ ] Criar modal/página de ativação do robô com seleção de par e capital
- [ ] Integrar endpoint de ativação com o backend da KuCoin
- [ ] Adicionar toast pós-desbloqueio
- [ ] Implementar atualização otimista do estado ao desbloquear
- [ ] Calcular e passar `planLimitReached` para os cards

### Sprint 3 — Melhoria UX (estimar: 2 dias)
- [ ] Adicionar busca e filtro no grid de 20 robôs
- [ ] Skeleton loader no Top 10
- [ ] Indicador de saldo insuficiente no botão de desbloqueio
- [ ] Eliminar duplicata Top 10 / Todos
- [ ] Traduzir strings em inglês

### Sprint 4 — Polimento (estimar: 2 dias)
- [ ] Página `/robots/:id` com gráfico de performance
- [ ] Empty state quando todos os robôs estão desbloqueados
- [ ] Corrigir badge ON FIRE para aparecer mesmo desbloqueado
- [ ] `useReducedMotion()` para acessibilidade
- [ ] Limpar arquivos mortos do projeto

---

## 10. RESUMO EXECUTIVO

| Categoria | Status |
|---|---|
| Visual / Design | 🟡 75% — bonito mas tem inconsistências e problemas mobile |
| Gamificação (pontos, XP, baú) | ✅ 90% — sistema completo, minor polishing |
| Desbloqueio de robôs | 🟡 60% — fluxo parcial, LockedModal desconectado |
| Ativação de robôs (trading real) | 🔴 0% — botão "Ativar" não funciona |
| Dados de performance (profit, win rate) | 🔴 10% — 100% mock estático |
| Ranking dinâmico | 🟡 40% — backend feito, mas sem auth token = sempre fallback mock |
| Integração KuCoin real | 🔴 5% — credenciais salvas, mas sem bot executando |

**Estimativa de conclusão total:** 7–9 dias de desenvolvimento focado

---

*Documentação gerada por análise estática dos componentes: `RobotsGameMarketplace.tsx`, `RobotMarketplaceCard.tsx`, `GameProfileWidget.tsx`, `LockedRobotModal.tsx`, `UnlockRobotModal.tsx`, `use-gamification.ts`, `types/robot.ts` e endpoints do backend `app/gamification/router.py`.*
