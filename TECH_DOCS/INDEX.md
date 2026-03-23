# TECH_DOCS — Índice de Documentações Técnicas

> **Gerado em:** Sessão de planejamento arquitetural  
> **Objetivo:** Transformar o CryptoTradeHub de MVP com dados mock em plataforma real de trading automatizado  
> **Stack:** FastAPI + Python | React + TypeScript | MongoDB | Redis | KuCoin API

---

## ARQUIVOS CRIADOS

| Doc | Arquivo | Escopo | Prioridade |
|---|---|---|---|
| 01 | [DOC_01_ENGINE_TRADING.md](DOC_01_ENGINE_TRADING.md) | Arquitetura da Engine de Trading (BotOrchestrator, BotWorker, asyncio) | 🔴 Crítica |
| 02 | [DOC_02_MODELO_BANCO.md](DOC_02_MODELO_BANCO.md) | Modelo MongoDB (5 coleções, índices, Pydantic, Repository pattern) | 🔴 Crítica |
| 03 | [DOC_03_ENDPOINT_ATIVACAO.md](DOC_03_ENDPOINT_ATIVACAO.md) | POST /api/trading/bots/start (validação, saldo, idempotência) | 🔴 Crítica |
| 04 | [DOC_04_INTEGRACAO_KUCOIN.md](DOC_04_INTEGRACAO_KUCOIN.md) | HMAC signing, rate limit, WebSocket reconexão automática | 🔴 Crítica |
| 05 | [DOC_05_CALCULO_PNL.md](DOC_05_CALCULO_PNL.md) | PnL realizado vs não-realizado, fees, slippage, curva de capital | 🟠 Alta |
| 06 | [DOC_06_RANKING_REAL.md](DOC_06_RANKING_REAL.md) | Leaderboard real (aggregation pipeline, Redis cache, scheduler) | 🟠 Alta |
| 07 | [DOC_07_RISK_MANAGEMENT.md](DOC_07_RISK_MANAGEMENT.md) | Stop loss, trailing stop, drawdown diário, kill switch global | 🔴 Crítica |
| 08 | [DOC_08_MONITORAMENTO_LOGS.md](DOC_08_MONITORAMENTO_LOGS.md) | JSON logging, Prometheus metrics, alertas Telegram, health checks | 🟠 Alta |
| 09 | [DOC_09_ESCALABILIDADE_SAAS.md](DOC_09_ESCALABILIDADE_SAAS.md) | Multi-engine, Docker Compose prod, zero-downtime deploy, quotas | 🟡 Média |
| 10 | [DOC_10_FLUXO_END_TO_END.md](DOC_10_FLUXO_END_TO_END.md) | Fluxo completo usuário + testes e2e + checklist produção | 🟠 Alta |

---

## ORDEM DE IMPLEMENTAÇÃO RECOMENDADA

### Sprint 1 — Base (2 semanas)
1. **DOC 02** — Criar coleções MongoDB e índices
2. **DOC 04** — Wrapper KuCoin com signing e WebSocket
3. **DOC 01** — Engine de execução (BotOrchestrator + BotWorker)

### Sprint 2 — Ativação (1 semana)
4. **DOC 03** — Endpoint POST /bots/start + botão Ativar no frontend
5. **DOC 07** — Risk management (stop loss, drawdown, kill switch)

### Sprint 3 — Dados Reais (1 semana)
6. **DOC 05** — Cálculo de PnL correto com fees e slippage
7. **DOC 06** — Ranking com dados reais (substituir mocks)

### Sprint 4 — Produção (1 semana)
8. **DOC 08** — Monitoramento, logs e alertas
9. **DOC 09** — Docker prod + scaling + zero-downtime deploy
10. **DOC 10** — Testes e2e + validação final

---

## DEPENDÊNCIAS ENTRE DOCUMENTOS

```
DOC_04 (KuCoin Client)
    └── DOC_01 (Engine usa o client)
            └── DOC_02 (Engine persiste nas coleções)
                    └── DOC_03 (Endpoint cria instâncias e envia para engine)
                            └── DOC_07 (Risk manager dentro do BotWorker)
                                    └── DOC_05 (PnL calculado ao fechar trade)
                                            └── DOC_06 (Ranking usa bot_trades)
                                                    └── DOC_08 (Logs em tudo)
                                                            └── DOC_09 (Deploy do sistema todo)
                                                                    └── DOC_10 (Valida tudo)
```

---

## ESTIMATIVA TOTAL

| Sprint | Duração | Resultado |
|---|---|---|
| Sprint 1 | 2 semanas | Engine básica rodando no sandbox |
| Sprint 2 | 1 semana | Usuário consegue ativar o primeiro bot real |
| Sprint 3 | 1 semana | Dados de PnL e ranking confiáveis |
| Sprint 4 | 1 semana | Plataforma pronta para produção |
| **Total** | **~5 semanas** | **Platform production-ready** |

---

## NOTAS IMPORTANTES

- **Sandbox first:** Toda a implementação deve ser testada com `KUCOIN_SANDBOX=true` antes de ir à produção
- **Sem simplificações:** Cada doc especifica a solução de produção, não MVP
- **Credenciais:** Nunca armazenar em plain text — sempre Fernet enc
- **Idempotência:** Todo endpoint que cria recursos deve ter proteção contra duplicate request
- **Graceful shutdown:** Engine sempre fecha posições abertas antes de reiniciar
