# DOC 10 — Checklist Final para Nível Institucional
## Critérios Objetivos de Aprovação de Produção

> **Versão:** 1.0.0 | **Formato:** Auditoria completa por domínio

---

## Como Usar Este Documento

Este checklist é o **critério final de GO/NO-GO para produção**. Cada item tem:
- **Status:** `[ ]` Pendente | `[x]` Implementado | `[~]` Parcial | `[!]` Crítico
- **DOC de Referência:** Onde implementar
- **Critério de Aprovação:** Teste objetivo que prova que o item está correto

---

## DOMÍNIO 1 — EXECUÇÃO DE ORDENS

| # | Item | DOC Ref | Critério de Aprovação |
|---|---|---|---|
| 1.1 | `clientOid` determinístico (SHA-256 de signalId+botId) | DOC 01 | Hash idêntico para mesmo input em 1000 execuções |
| 1.2 | Idempotência com Redis SET NX | DOC 01 | 1000 sinais duplicados → 1 única ordem enviada |
| 1.3 | Persistência do clientOid ANTES do envio HTTP | DOC 01 | Crash após persist → reconciliação recupera |
| 1.4 | Retry com backoff exponencial (500ms→8000ms, max 5x) | DOC 01 | Erro 429 respondido com backoff correto |
| 1.5 | TERMINAL_ERROR_CODES não sofrem retry | DOC 01 | Código 400100 → falha imediata sem retry |
| 1.6 | ReconciliationService rodando a cada 60s | DOC 01 | PENDING > 2min → comparado via REST |
| 1.7 | TP/SL cancelados atomicamente (Redis Lock) | DOC 02 | Race condition TP+SL simultâneos → apenas 1 executa |
| 1.8 | OrphanGuardian rodando a cada 5min | DOC 02 | TP sem posição → cancelado em < 10min |
| 1.9 | PartialFillHandler redimensiona TP/SL | DOC 02 | Fill parcial → novos TP/SL com size correto |

---

## DOMÍNIO 2 — CONCORRÊNCIA E LOCKS

| # | Item | DOC Ref | Critério de Aprovação |
|---|---|---|---|
| 2.1 | Lua script para release atômico de lock | DOC 04 | Token mismatch → lock NÃO liberado |
| 2.2 | Lock `lock:bot:{botId}` antes do pre-flight | DOC 04 | 100 sinais simultâneos → 0 ordens duplicadas |
| 2.3 | Lock `lock:balance:{userId}` antes da verificação | DOC 04 | N bots simultâneos → saldo virtual correto |
| 2.4 | Reserva de saldo liberada após falha | DOC 04 | Falha de envio → reserva zerada em < 1s |
| 2.5 | Redis Stream com Consumer Group | DOC 04 | Worker crash → mensagem reclamada em < 65s |
| 2.6 | XACK apenas após persistência do orderId | DOC 04 | Crash após XACK impossível → sem perda |

---

## DOMÍNIO 3 — RISK MANAGEMENT

| # | Item | DOC Ref | Critério de Aprovação |
|---|---|---|---|
| 3.1 | `RiskManager.evaluate()` chamado em TODA ordem | DOC 05 | 0 ordens passam sem validação de risco |
| 3.2 | Max Daily Loss bloqueia novas ordens | DOC 05 | PnL = -limite → próxima ordem bloqueada |
| 3.3 | Max Drawdown monitorado em tempo real | DOC 05 | Drawdown > limite → cooldown ativado |
| 3.4 | Cooldown não bloqueia operações de fechamento | DOC 05 | Closing order durante cooldown → aprovada |
| 3.5 | Kill-switch global em Redis (< 2s propagação) | DOC 05 | SET `risk:global:kill_switch` → todas ordens bloqueadas |
| 3.6 | Bot morto após consecutiveLossLimit | DOC 05 | 5 losses consecutivas → bot com flag kill |
| 3.7 | Reset diário de RiskState à meia-noite UTC | DOC 05 | Estado limpo a cada dia |
| 3.8 | Fechamento de posição sempre permitido | DOC 05 | ALL risk blocks → closing side passa |
| 3.9 | Volatility score bloqueia em > 85/100 | DOC 05 | Score artificial 90 → nova entrada bloqueada |
| 3.10 | Reserva de capital virtual para N bots simultâneos | DOC 05 | Soma de posições não excede maxAggregatedPosition |

---

## DOMÍNIO 4 — WEBSOCKET

| # | Item | DOC Ref | Critério de Aprovação |
|---|---|---|---|
| 4.1 | Token renovado 5min antes de expirar | DOC 03 | Zero desconexão por token expirado em 7 dias |
| 4.2 | Backoff exponencial 1s→30s em reconexão | DOC 03 | Queda de rede → reconecta dentro de 10 tentativas |
| 4.3 | Heartbeat a cada 18s | DOC 03 | Sem mensagem por 20s → PING enviado |
| 4.4 | Gap de sequência detectado e corrigido | DOC 03 | Gap artificial → snapshot REST executado |
| 4.5 | Fan-out via Redis Pub/Sub | DOC 03 | 1 WS message → N subscribers notificados |
| 4.6 | Fallback REST após 10s sem WS | DOC 03 | WS desconectado → REST polling ativado |
| 4.7 | Zero polling em operação normal | DOC 03 | WS operacional → 0 chamadas REST de polling |

---

## DOMÍNIO 5 — MONITORAMENTO

| # | Item | DOC Ref | Critério de Aprovação |
|---|---|---|---|
| 5.1 | Todos logs com campo `event` estruturado | DOC 06 | 0 `console.log` ou strings não estruturadas |
| 5.2 | Logs com `redact` para dados sensíveis | DOC 06 | apiKey/apiSecret nunca aparece em logs |
| 5.3 | Endpoint `/metrics` em formato Prometheus | DOC 06 | Prometheus scrape a cada 15s sem erro |
| 5.4 | Latência de ordens em Histogram | DOC 06 | P99 disponível no Grafana |
| 5.5 | Circuit breaker state como Gauge | DOC 06 | Estado visível e alertado quando OPEN |
| 5.6 | Health check ponderado (score 0-100) | DOC 06 | Redis offline → status `unhealthy`, não 200 OK |
| 5.7 | Alertas configurados no AlertManager | DOC 06 | Kill-switch ativado → Slack alerta em < 1min |
| 5.8 | MTTD < 30 segundos | DOC 06 | Falha simulada → alerta em < 30s |
| 5.9 | `requestId` propagado por toda a stack | DOC 06 | Todo log de uma request tem mesmo requestId |

---

## DOMÍNIO 6 — LICENCIAMENTO E PAGAMENTO

| # | Item | DOC Ref | Critério de Aprovação |
|---|---|---|---|
| 6.1 | **Dev bypass REMOVIDO** de `licensing/service.py` | DOC 07 | Exception em DB → erro 503, nunca Premium |
| 6.2 | Webhook valida assinatura HMAC-SHA256 | DOC 07 | Assinatura inválida → 400, nunca processado |
| 6.3 | Webhook idempotente (stripe_event_id único) | DOC 07 | Mesmo webhook 2x → processado apenas 1x |
| 6.4 | Grace period de 3 dias após falha de pagamento | DOC 07 | Pagamento falhou → acesso por exatamente 3 dias |
| 6.5 | Downgrade automático após grace | DOC 07 | Grace expirado → plan = "free" automático |
| 6.6 | Cache Redis de licença com TTL=30min | DOC 07 | Licença atualizada → refletida em < 30min |
| 6.7 | Feature gate em todas as rotas protegidas | DOC 07 | Free user requisita feature Pro → 403 |
| 6.8 | Zero feature Pro acessível sem pagamento | DOC 07 | Auditoria de todos os endpoints com plano |

---

## DOMÍNIO 7 — SEGURANÇA

| # | Item | DOC Ref | Critério de Aprovação |
|---|---|---|---|
| 7.1 | API Keys encriptadas em repouso (AES-256) | — | Keys nunca em plaintext no MongoDB |
| 7.2 | JWT com TTL curto (15min) + refresh token | — | Token expirado → 401, refresh válido |
| 7.3 | Rate limiting por userId em todas as rotas | — | 100 req/min → 429 para excess |
| 7.4 | CORS configurado para domínio específico | — | Origem não autorizada → bloqueada |
| 7.5 | Sem secrets em variáveis de ambiente no frontend | — | `VITE_` nunca contém keys sensíveis |
| 7.6 | Input validation em todos os endpoints | — | SQL injection / NoSQL injection testados |
| 7.7 | Dependency scanning no CI (Dependabot) | — | 0 vulnerabilidades críticas conhecidas |
| 7.8 | Logs de auditoria imutáveis (hash encadeado) | DOC 01 | Alteração de log → hash quebrado detectado |

---

## DOMÍNIO 8 — QUALIDADE DE CÓDIGO

| # | Item | DOC Ref | Critério de Aprovação |
|---|---|---|---|
| 8.1 | Cobertura de testes ≥ 80% (backend) | Todos DOCs | `pytest --cov` → coverage.xml gerado |
| 8.2 | Cobertura de testes ≥ 70% (frontend) | — | Vitest coverage report |
| 8.3 | CI pipeline verde em toda PR | — | GitHub Actions obrigatório para merge |
| 8.4 | Linting sem erros (ESLint + Pylint) | — | 0 erros em CI |
| 8.5 | Type checking estrito (TypeScript strict: true) | — | 0 erros de tipo em build |
| 8.6 | Testes de concorrência (race condition) | DOC 04 | 1000 sinais simultâneos → 0 duplicatas |
| 8.7 | Testes de falha de rede (chaos) | DOC 01 | Kucoin timeout → retry correto + log |
| 8.8 | Migration scripts para MongoDB | — | Deploy sem downtime via migrations |

---

## DOMÍNIO 9 — PERFORMANCE E ESCALABILIDADE

| # | Item | DOC Ref | Critério de Aprovação |
|---|---|---|---|
| 9.1 | Latência de envio de ordem P99 < 500ms | DOC 06 | Histograma confirma |
| 9.2 | Latência de risk evaluation P99 < 50ms | DOC 05 | Summary confirma |
| 9.3 | Redis com conexão pool (não nova conexão por request) | — | Max 20 conexões ao pool |
| 9.4 | MongoDB queries com índices adequados | — | explain() → 0 COLLSCAN em queries hot |
| 9.5 | Paginação em todos os list endpoints | — | GET /orders sem paginação → 400 |
| 9.6 | N+1 query eliminado | — | 0 loops com query dentro em hot paths |
| 9.7 | Workers horizontalmente escaláveis | — | 3 workers simultâneos sem conflito |
| 9.8 | Load test: 100 bots simultâneos | — | K6 test: 0 erros em 10min de carga |

---

## DOMÍNIO 10 — OPERAÇÕES E DEPLOY

| # | Item | DOC Ref | Critério de Aprovação |
|---|---|---|---|
| 10.1 | `docker-compose.prod.yml` validado | — | Deploy em VM limpa sem intervenção manual |
| 10.2 | Backup automático MongoDB | — | Backup diário comprovado + restore testado |
| 10.3 | Variáveis de ambiente documentadas | — | `.env.example` com todos os campos |
| 10.4 | Rollback documentado e testado | — | Rollback de versão em < 5min |
| 10.5 | Graceful shutdown | — | SIGTERM → drena conexões em < 30s |
| 10.6 | Health check no Docker Compose | — | Container unhealthy → restart automático |
| 10.7 | Secrets gerenciados (nunca em git) | — | `.env` em `.gitignore`, secrets em vault |
| 10.8 | SSL/TLS em todas as conexões externas | — | Nginx com TLS 1.3, A+ no ssllabs.com |

---

## SCORE FINAL

```
DOMÍNIO 1 — Execução:          ___/9   itens aprovados
DOMÍNIO 2 — Concorrência:      ___/6   itens aprovados
DOMÍNIO 3 — Risk:              ___/10  itens aprovados
DOMÍNIO 4 — WebSocket:         ___/7   itens aprovados
DOMÍNIO 5 — Monitoramento:     ___/9   itens aprovados
DOMÍNIO 6 — Licenciamento:     ___/8   itens aprovados
DOMÍNIO 7 — Segurança:         ___/8   itens aprovados
DOMÍNIO 8 — Código:            ___/8   itens aprovados
DOMÍNIO 9 — Performance:       ___/8   itens aprovados
DOMÍNIO 10 — Operações:        ___/8   itens aprovados

TOTAL:                          ___/81  itens aprovados

CRITÉRIO DE APROVAÇÃO PARA PRODUÇÃO: ≥ 90% (73/81)
ITENS CRÍTICOS [!] NÃO APROVADOS: 0 (bloqueadores absolutos)
```

---

## BLOQUEADORES ABSOLUTOS (Impede deploy em qualquer condição)

```
❌ 6.1 — Dev bypass de licenciamento não removido
❌ 7.1 — API Keys em plaintext no banco de dados  
❌ 2.1 — Ausência de distributed lock (duplicatas possíveis)
❌ 3.1 — RiskManager não chamado em todas as ordens
❌ 6.2 — Webhook sem validação de assinatura Stripe
```

---

## PLANO DE SPRINT SUGERIDO

| Sprint | Foco | Documentos |
|---|---|---|
| Sprint 1 (2 semanas) | Execução Real + Locks | DOC 01 + DOC 04 |
| Sprint 2 (2 semanas) | Risk Manager + TP/SL | DOC 02 + DOC 05 |
| Sprint 3 (2 semanas) | WebSocket + Monitoramento | DOC 03 + DOC 06 |
| Sprint 4 (2 semanas) | Pagamento + Licenciamento | DOC 07 |
| Sprint 5 (2 semanas) | Marketplace | DOC 08 |
| Sprint 6 (2 semanas) | Multi-Exchange + Auditoria Final | DOC 09 + DOC 10 |

**Total estimado:** 12 semanas para nível institucional completo.

---

## ASSINATURA DE APROVAÇÃO

```
Aprovado por: ______________________  Data: __/__/____
Cargo: _____________________________

Score Final: ___/81  (___%)
Bloqueadores pendentes: ___

Status: [ ] APROVADO PARA PRODUÇÃO  [ ] RETORNAR PARA CORREÇÃO
```
