# DOC 06 — Sistema de Ranking com Dados Reais

> **Nível:** Produção | **Escopo:** Leaderboard multi-critério, atualização periódica, exibição frontend  
> **Prioridade:** Alta — gamificação central da plataforma, erro aqui destrói competitividade

---

## 1. PROBLEMA ATUAL

O ranking exibe dados mockados. A API em `/api/gamification/leaderboard` não passa o token de autenticação e retorna dados estáticos. O usuário não vê sua posição real nem compara com outros.

---

## 2. ARQUITETURA DO SISTEMA DE RANKING

```
[bot_trades] ──── Aggregation Pipeline ────► [leaderboard_cache]
    │                    (15 min)                      │
    │                                                  ▼
[user_bot_instances] ────────────────► /api/gamification/leaderboard
                                              │
                                         [Redis Cache]
                                         (TTL 5 min)
```

---

## 3. CRITÉRIOS DE CLASSIFICAÇÃO

```python
# Ranking é multi-critério com pesos configuráveis

RANKING_WEIGHTS = {
    "roi_pct": 0.35,           # Retorno sobre investimento — competitividade
    "win_rate": 0.25,          # Consistência — qualidade de sinal
    "total_pnl_usdt": 0.20,    # Volume absoluto de lucro — relevância
    "profit_factor": 0.15,     # Fator de lucro — discipline (>1.5 é bom)
    "total_trades": 0.05       # Atividade — não premiar quem não opera
}

# Score composto = soma ponderada normalizada [0-100]
# Cada métrica é normalizada pelo max do período
```

---

## 4. PIPELINE DE CÁLCULO DO RANKING

```python
# backend/app/gamification/ranking_service.py

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
import json

logger = logging.getLogger("ranking.service")

PERIOD_DAYS = 30   # Janela de 30 dias para ranking mensal
CACHE_TTL_SECONDS = 300  # 5 minutos


class RankingService:
    def __init__(self, db: AsyncIOMotorDatabase, redis):
        self.db = db
        self.redis = redis

    async def compute_ranking(self, period_days: int = PERIOD_DAYS) -> List[dict]:
        """
        Agrega dados de todas as trades do período e computa ranking.
        Executado pelo scheduler a cada 15 minutos.
        """
        since = datetime.utcnow() - timedelta(days=period_days)

        # ── Pipeline de Aggregation MongoDB ────────────────────────────────
        pipeline = [
            # Filtrar trades do período e apenas fechadas
            {
                "$match": {
                    "status": "closed",
                    "exit_timestamp": {"$gte": since}
                }
            },
            # Agrupar por usuário + bot
            {
                "$group": {
                    "_id": {
                        "user_id": "$user_id",
                        "bot_instance_id": "$bot_instance_id"
                    },
                    "total_pnl_usdt": {"$sum": "$pnl_net_usdt"},
                    "total_volume_usdt": {"$sum": "$entry_funds"},
                    "total_trades": {"$sum": 1},
                    "winning_trades": {
                        "$sum": {"$cond": [{"$gte": ["$pnl_net_usdt", 0]}, 1, 0]}
                    },
                    "total_positive_pnl": {
                        "$sum": {"$cond": [{"$gte": ["$pnl_net_usdt", 0]}, "$pnl_net_usdt", 0]}
                    },
                    "total_negative_pnl": {
                        "$sum": {"$cond": [{"$lt": ["$pnl_net_usdt", 0]}, "$pnl_net_usdt", 0]}
                    },
                    "total_fees_usdt": {"$sum": {"$add": ["$entry_fee_usdt", "$exit_fee_usdt"]}},
                }
            },
            # Join com user_bot_instances para pegar capital inicial
            {
                "$lookup": {
                    "from": "user_bot_instances",
                    "localField": "_id.bot_instance_id",
                    "foreignField": "_id",
                    "as": "instance"
                }
            },
            {"$unwind": {"path": "$instance", "preserveNullAndEmpty": True}},
            # Join com users para pegar nome/avatar
            {
                "$lookup": {
                    "from": "users",
                    "localField": "_id.user_id",
                    "foreignField": "_id",
                    "as": "user"
                }
            },
            {"$unwind": {"path": "$user", "preserveNullAndEmpty": True}},
            # Calcular métricas derivadas
            {
                "$addFields": {
                    "initial_capital": {
                        "$ifNull": ["$instance.metrics.initial_capital_usdt", 1000]
                    },
                    "win_rate": {
                        "$cond": [
                            {"$gt": ["$total_trades", 0]},
                            {"$multiply": [{"$divide": ["$winning_trades", "$total_trades"]}, 100]},
                            0
                        ]
                    },
                    "profit_factor": {
                        "$cond": [
                            {"$lt": ["$total_negative_pnl", 0]},
                            {"$divide": ["$total_positive_pnl", {"$abs": "$total_negative_pnl"}]},
                            10  # Cap em 10 se não houver perdas
                        ]
                    },
                }
            },
            {
                "$addFields": {
                    "roi_pct": {
                        "$multiply": [
                            {"$divide": ["$total_pnl_usdt", "$initial_capital"]},
                            100
                        ]
                    }
                }
            },
            # Filtrar mínimos de qualidade
            {
                "$match": {
                    "total_trades": {"$gte": 5},     # Mínimo 5 trades
                    "roi_pct": {"$gte": -99},         # Excluir instâncias zeradas
                }
            },
            # Projetar campos finais
            {
                "$project": {
                    "user_id": "$_id.user_id",
                    "bot_instance_id": "$_id.bot_instance_id",
                    "display_name": {"$ifNull": ["$user.display_name", "Trader Anônimo"]},
                    "avatar_url": "$user.avatar_url",
                    "robot_id": "$instance.robot_id",
                    "robot_name": "$instance.robot_name",
                    "pair": "$instance.configuration.pair",
                    "roi_pct": {"$round": ["$roi_pct", 2]},
                    "win_rate": {"$round": ["$win_rate", 1]},
                    "total_pnl_usdt": {"$round": ["$total_pnl_usdt", 4]},
                    "profit_factor": {"$round": ["$profit_factor", 2]},
                    "total_trades": 1,
                    "total_fees_usdt": {"$round": ["$total_fees_usdt", 4]},
                }
            },
            # Sort inicial por ROI
            {"$sort": {"roi_pct": -1}},
            # Limitar ao top 100
            {"$limit": 100}
        ]

        raw_results = await self.db["bot_trades"].aggregate(pipeline).to_list(length=100)

        # ── Calcular Score Composto ─────────────────────────────────────────
        ranked = self._compute_composite_scores(raw_results)

        # ── Salvar no leaderboard_cache ─────────────────────────────────────
        snapshot = {
            "computed_at": datetime.utcnow(),
            "period_days": period_days,
            "entries": ranked,
        }
        await self.db["leaderboard_cache"].replace_one(
            {"period_days": period_days},
            snapshot,
            upsert=True
        )

        # ── Salvar no Redis ─────────────────────────────────────────────────
        await self.redis.setex(
            f"ranking:{period_days}d",
            CACHE_TTL_SECONDS,
            json.dumps(ranked, default=str)
        )

        logger.info(f"✅ Ranking computado: {len(ranked)} entradas")
        return ranked

    def _compute_composite_scores(self, results: list) -> list:
        """Normaliza métricas e calcula score composto para ordenação final."""
        if not results:
            return []

        # Extrair max de cada métrica para normalização
        max_roi = max((r["roi_pct"] for r in results), default=1) or 1
        max_win_rate = max((r["win_rate"] for r in results), default=1) or 1
        max_pnl = max((r["total_pnl_usdt"] for r in results), default=1) or 1
        max_pf = max((r["profit_factor"] for r in results), default=1) or 1
        max_trades = max((r["total_trades"] for r in results), default=1) or 1

        weights = {
            "roi_pct": (0.35, max_roi),
            "win_rate": (0.25, max_win_rate),
            "total_pnl_usdt": (0.20, max_pnl),
            "profit_factor": (0.15, max_pf),
            "total_trades": (0.05, max_trades),
        }

        for r in results:
            score = 0.0
            for metric, (weight, max_val) in weights.items():
                normalized = max(0, r.get(metric, 0)) / max_val
                score += normalized * weight * 100
            r["composite_score"] = round(score, 2)

        # Ordenar por score composto
        results.sort(key=lambda x: x["composite_score"], reverse=True)

        # Atribuir posições
        for i, r in enumerate(results):
            r["rank_position"] = i + 1
            r["_id"] = str(r.get("_id", ""))  # Serializar ObjectId

        return results

    async def get_cached_ranking(self, period_days: int = PERIOD_DAYS) -> Optional[list]:
        """Retorna ranking do Redis (cache) ou MongoDB."""
        # Tentar Redis primeiro
        cached = await self.redis.get(f"ranking:{period_days}d")
        if cached:
            return json.loads(cached)

        # Fallback para MongoDB
        doc = await self.db["leaderboard_cache"].find_one({"period_days": period_days})
        if doc:
            return doc.get("entries", [])

        return None


# ── Scheduler (APScheduler) ────────────────────────────────────────────────
from apscheduler.schedulers.asyncio import AsyncIOScheduler

def setup_ranking_scheduler(ranking_service: RankingService) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        ranking_service.compute_ranking,
        trigger="interval",
        minutes=15,
        id="compute_ranking_30d",
        replace_existing=True,
        max_instances=1,  # Nunca rodar duas instâncias simultâneas
    )
    return scheduler
```

---

## 5. ENDPOINT DA API

```python
# backend/app/gamification/router.py

from app.gamification.ranking_service import RankingService

@router.get("/leaderboard")
async def get_leaderboard(
    period: int = Query(30, ge=7, le=90),
    limit: int = Query(50, ge=10, le=100),
    current_user: dict = Depends(get_current_user)   # ← auth obrigatório
):
    """
    Retorna o ranking dos melhores traders do período.
    Responde do cache (Redis → MongoDB) para minimizar latência.
    """
    user_id = str(current_user.get("_id"))
    service = RankingService(db=get_db(), redis=await get_redis())

    entries = await service.get_cached_ranking(period_days=period)

    if not entries:
        # Primeiro cálculo — iniciar em background
        asyncio.create_task(service.compute_ranking(period))
        return {
            "entries": [],
            "total": 0,
            "computed_at": None,
            "user_rank": None,
            "message": "Ranking sendo calculado. Disponível em ~60 segundos."
        }

    # Encontrar posição do usuário atual
    user_rank = next(
        (e for e in entries if e.get("user_id") == user_id),
        None
    )

    return {
        "entries": entries[:limit],
        "total": len(entries),
        "computed_at": entries[0].get("computed_at") if entries else None,
        "user_rank": user_rank,
        "period_days": period,
    }


@router.get("/leaderboard/my-position")
async def get_my_ranking_position(current_user: dict = Depends(get_current_user)):
    """Retorna apenas a posição e métricas do usuário logado."""
    user_id = str(current_user.get("_id"))
    service = RankingService(db=get_db(), redis=await get_redis())

    entries = await service.get_cached_ranking()
    user_rank = next((e for e in (entries or []) if e.get("user_id") == user_id), None)

    if not user_rank:
        return {"ranked": False, "message": "Você ainda não tem trades suficientes para entrar no ranking (mínimo: 5 trades)."}

    return {"ranked": True, **user_rank}
```

---

## 6. FRONTEND — LEADERBOARD REAL

```tsx
// src/hooks/use-leaderboard.ts

import { useQuery } from '@tanstack/react-query';
import { API_BASE_URL } from '@/config/constants';
import { useAuthStore } from '@/context/AuthContext';

export function useLeaderboard(periodDays: number = 30) {
  const { accessToken } = useAuthStore();

  return useQuery({
    queryKey: ['leaderboard', periodDays],
    queryFn: async () => {
      const res = await fetch(`${API_BASE_URL}/api/gamification/leaderboard?period=${periodDays}`, {
        headers: { Authorization: `Bearer ${accessToken}` }
      });
      if (!res.ok) throw new Error('Falha ao carregar ranking');
      return res.json();
    },
    staleTime: 5 * 60 * 1000,  // Cache local de 5 minutos
    refetchInterval: 5 * 60 * 1000,  // Auto-refresh a cada 5 min
    enabled: !!accessToken,
  });
}
```

```tsx
// src/pages/Ranking.tsx — substituir mocks por dados reais

const { data, isLoading } = useLeaderboard(30);

{isLoading ? <SkeletonTable rows={10} /> : (
  data?.entries.map((entry, idx) => (
    <LeaderboardRow
      key={entry.bot_instance_id}
      position={entry.rank_position}
      displayName={entry.display_name}
      robotName={entry.robot_name}
      roi={entry.roi_pct}
      winRate={entry.win_rate}
      totalPnl={entry.total_pnl_usdt}
      isCurrentUser={entry.user_id === currentUser?.id}
    />
  ))
)}
```

---

## 7. PRIVACIDADE E SEGURANÇA

| Campo | Exposto Publicamente? | Lógica |
|---|---|---|
| `user_id` | Não — omitir na resposta pública | Somente para comparação interna |
| `display_name` | Sim | Pode ser nickname escolhido pelo usuário |
| `avatar_url` | Sim | Opcional, pode ser gravatar gerado |
| `email` | **NUNCA** | Excluir do pipeline com `$project: { email: 0 }` |
| `api_key` | **NUNCA** | Nunca entra na aggregation |
| `total_pnl_usdt` | Sim — valor absoluto | Algumas plataformas ocultam, decisão de produto |

---

## 8. ÍNDICES NECESSÁRIOS

```javascript
// Para o pipeline de aggregation ser rápido com milhões de trades
db.bot_trades.createIndex({ "status": 1, "exit_timestamp": -1, "user_id": 1 })
db.bot_trades.createIndex({ "bot_instance_id": 1, "status": 1 })
db.leaderboard_cache.createIndex({ "period_days": 1 }, { unique: true })
```

---

## 9. CHECKLIST

- [ ] `compute_ranking` roda a cada 15 minutos via scheduler
- [ ] Score composto calculado com os 5 critérios ponderados
- [ ] Redis cache com TTL 5 min (sem refazer aggregation a cada request)
- [ ] Endpoint /leaderboard requer autenticação (header Authorization)
- [ ] Endpoint /leaderboard/my-position retorna posição do usuário atual
- [ ] Email e campos sensíveis excluídos da query
- [ ] Mínimo de 5 trades para entrar no ranking (evitar 1 trade sortuda)
- [ ] Frontend usa React Query com refetch automático a cada 5 min
- [ ] Loading skeleton enquanto dados carregam
- [ ] Linha do usuário atual destacada na tabela
