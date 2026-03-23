# DOC 03 — Endpoint de Ativação de Robô

> **Nível:** Produção | **Endpoint:** `POST /api/trading/bots/start`  
> **Prioridade:** Crítica — ponto de entrada para todo o fluxo de trading real

---

## 1. OBJETIVO

Implementar o endpoint completo de ativação de um robô de trading, com:
- Validação de todos os pré-requisitos (saldo KuCoin, robô desbloqueado, limite do plano)
- Criação segura da instância no banco com idempotência
- Envio do comando para a engine de execução
- Resposta imediata ao frontend com status de inicialização

---

## 2. PROBLEMA ATUAL

O botão "Ativar" no `RobotMarketplaceCard.tsx` tem apenas:
```tsx
onClick={(e) => { e.stopPropagation(); }}
```
Não existe endpoint nem lógica de ativação. O usuário desbloqueia um robô e não consegue ativá-lo.

---

## 3. FLUXO COMPLETO DE ATIVAÇÃO

```
Frontend                    API                       Engine / KuCoin
    │                        │                              │
    │── POST /bots/start ───►│                              │
    │   {robot_id,           │                              │
    │    capital, pair...}   │                              │
    │                        │── 1. Validar JWT ────────────│
    │                        │── 2. Verificar robô          │
    │                        │      desbloqueado            │
    │                        │── 3. Verificar limite plano  │
    │                        │── 4. Descriptografar creds   │
    │                        │── 5. Verificar saldo KuCoin──►│
    │                        │◄─ saldo OK ─────────────────│
    │                        │── 6. Criar instância (DB)    │
    │                        │── 7. LPUSH bot:commands ─────►│
    │◄── {bot_id, "starting"}│                              │
    │                        │                   BotOrchestrator
    │                        │                        │── criar BotWorker
    │                        │                        │── conectar KuCoin WS
    │                        │                        │── iniciar loop
    │                        │                              │
    │◄── WS update: "running"│◄── MongoDB change stream ───│
```

---

## 4. IMPLEMENTAÇÃO DO ENDPOINT

### 4.1 Schema de Request/Response

```python
# backend/app/trading/schemas.py

from pydantic import BaseModel, Field, validator
from typing import Optional


class StartBotRequest(BaseModel):
    robot_id: str = Field(..., description="ID do robô do marketplace")
    pair: str = Field(..., pattern=r"^[A-Z]+-[A-Z]+$", example="BTC-USDT")
    capital_usdt: float = Field(..., gt=10.0, le=50000.0, description="Capital em USDT")
    timeframe: str = Field("1h", pattern=r"^(1m|5m|15m|1h|4h|1d)$")
    stop_loss_pct: float = Field(5.0, ge=0.5, le=30.0)
    take_profit_pct: float = Field(15.0, ge=1.0, le=100.0)
    max_daily_loss_usdt: Optional[float] = Field(None, gt=0)
    strategy_params: Optional[dict] = Field(default_factory=dict)

    @validator("capital_usdt")
    def validate_capital(cls, v, values):
        # Capital mínimo por estratégia pode variar
        return v

    @validator("take_profit_pct")
    def tp_must_exceed_sl(cls, v, values):
        sl = values.get("stop_loss_pct", 0)
        if v <= sl:
            raise ValueError("Take profit deve ser maior que stop loss")
        return v


class StartBotResponse(BaseModel):
    bot_instance_id: str
    status: str = "starting"
    message: str = "Robô sendo iniciado..."
    estimated_start_seconds: int = 5


class BotStatusResponse(BaseModel):
    bot_instance_id: str
    robot_id: str
    robot_name: str
    status: str
    pair: str
    capital_usdt: float
    total_pnl_usdt: float
    win_rate: float
    total_trades: int
    started_at: Optional[str]
    last_heartbeat: Optional[str]
```

### 4.2 Endpoint Principal

```python
# backend/app/trading/router.py (adicionar)

import json
from fastapi import APIRouter, Depends, HTTPException, status
from app.trading.schemas import StartBotRequest, StartBotResponse, BotStatusResponse
from app.engine.models import UserBotInstance, BotConfiguration, BotMetrics, BotStatus
from app.engine.repository import BotInstanceRepository
from app.core.auth import get_current_user
from app.core.encryption import decrypt_kucoin_credentials
from app.shared.redis_client import get_redis
from app.core.database import get_db
from app.plan_limits import check_plan_bot_limit
from kucoin_client_wrapper import KuCoinClientWrapper
import logging

logger = logging.getLogger("api.bots")

ROBOTS_CATALOG = {
    "bot_001": {"name": "Volatility Dragon", "type": "grid"},
    "bot_002": {"name": "Legend Slayer", "type": "combined"},
    "bot_003": {"name": "Grid Precision", "type": "grid"},
    "bot_004": {"name": "Hybrid Flame", "type": "combined"},
    "bot_005": {"name": "RSI Hunter Elite", "type": "rsi"},
    # ... todos os 20 robôs
}


@router.post(
    "/bots/start",
    response_model=StartBotResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ativar robô de trading",
    description="Cria uma instância do robô e envia comando para a engine de execução."
)
async def start_bot(
    request: StartBotRequest,
    current_user: dict = Depends(get_current_user)
):
    user_id = str(current_user.get("_id"))
    db = get_db()

    # ── 1. Verificar se o robô existe no catálogo ──────────────────────────
    robot_info = ROBOTS_CATALOG.get(request.robot_id)
    if not robot_info:
        raise HTTPException(
            status_code=404,
            detail=f"Robô '{request.robot_id}' não encontrado no catálogo"
        )

    # ── 2. Verificar se o robô está desbloqueado pelo usuário ───────────────
    gamification_profile = await db["gamification_profiles"].find_one({"user_id": user_id})
    unlocked_robots = gamification_profile.get("unlocked_robots", []) if gamification_profile else []

    if request.robot_id not in unlocked_robots:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "robot_not_unlocked",
                "message": "Este robô não foi desbloqueado ainda",
                "robot_id": request.robot_id
            }
        )

    # ── 3. Verificar se usuário já tem esse robô ativo (idempotência) ──────
    already_active = await BotInstanceRepository.check_duplicate_robot(user_id, request.robot_id)
    if already_active:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "bot_already_active",
                "message": "Este robô já está ativo. Pare-o antes de reativar.",
            }
        )

    # ── 4. Verificar limite de robôs do plano ──────────────────────────────
    plan_check = await check_plan_bot_limit(user_id, db)
    if not plan_check["allowed"]:
        raise HTTPException(
            status_code=402,
            detail={
                "error": "plan_limit_reached",
                "message": f"Seu plano {plan_check['plan']} permite no máximo {plan_check['limit']} robôs ativos.",
                "current_active": plan_check["current_active"],
                "limit": plan_check["limit"],
            }
        )

    # ── 5. Verificar credenciais KuCoin ────────────────────────────────────
    cred_doc = await db["trading_credentials"].find_one(
        {"user_id": user_id, "is_active": True}
    )
    if not cred_doc:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "kucoin_not_connected",
                "message": "Conecte sua API KuCoin antes de ativar um robô"
            }
        )

    # Descriptografar credenciais
    try:
        decrypted = decrypt_kucoin_credentials(
            api_key_enc=cred_doc["api_key_enc"],
            api_secret_enc=cred_doc["api_secret_enc"],
            api_passphrase_enc=cred_doc["api_passphrase_enc"]
        )
    except Exception as e:
        logger.error(f"Erro ao descriptografar credenciais do usuário {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Erro interno — credenciais inválidas")

    # ── 6. Verificar saldo real na KuCoin ──────────────────────────────────
    try:
        kucoin = KuCoinClientWrapper(
            api_key=decrypted["api_key"],
            api_secret=decrypted["api_secret"],
            api_passphrase=decrypted["api_passphrase"],
        )
        balances = await kucoin.get_account_balances()
        usdt_balance = next(
            (b["available"] for b in balances if b["currency"] == "USDT"),
            0.0
        )

        if float(usdt_balance) < request.capital_usdt:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "insufficient_balance",
                    "message": f"Saldo insuficiente. Disponível: {usdt_balance} USDT. Necessário: {request.capital_usdt} USDT.",
                    "available_usdt": float(usdt_balance),
                    "required_usdt": request.capital_usdt
                }
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao verificar saldo KuCoin do usuário {user_id}: {e}")
        raise HTTPException(
            status_code=502,
            detail={
                "error": "kucoin_api_error",
                "message": "Não foi possível verificar saldo na KuCoin. Tente novamente."
            }
        )

    # ── 7. Criar instância no banco (status: pending) ──────────────────────
    # max_daily_loss padrão = 10% do capital
    max_daily_loss = request.max_daily_loss_usdt or (request.capital_usdt * 0.10)

    instance = UserBotInstance(
        user_id=user_id,
        robot_id=request.robot_id,
        robot_name=robot_info["name"],
        robot_type=robot_info["type"],
        configuration=BotConfiguration(
            pair=request.pair,
            capital_usdt=request.capital_usdt,
            timeframe=request.timeframe,
            stop_loss_pct=request.stop_loss_pct,
            take_profit_pct=request.take_profit_pct,
            max_daily_loss_usdt=max_daily_loss,
            strategy_params=request.strategy_params or {}
        ),
        status=BotStatus.PENDING,
        metrics=BotMetrics(
            initial_capital_usdt=request.capital_usdt,
            current_capital_usdt=request.capital_usdt
        ),
        credentials_id=str(cred_doc["_id"])
    )

    bot_instance_id = await BotInstanceRepository.create(instance)
    logger.info(f"✅ Instância criada: {bot_instance_id} (user={user_id}, robot={request.robot_id})")

    # ── 8. Enviar comando para a engine via Redis ──────────────────────────
    redis = await get_redis()
    command = {
        "action": "start",
        "bot_instance_id": bot_instance_id,
        "user_id": user_id,
        # Credenciais descriptografadas passadas no comando (em memória, não no banco)
        "credentials": {
            "api_key": decrypted["api_key"],
            "api_secret": decrypted["api_secret"],
            "api_passphrase": decrypted["api_passphrase"]
        },
        "timestamp": datetime.utcnow().isoformat()
    }
    await redis.lpush("bot:commands", json.dumps(command))

    logger.info(f"📨 Comando start enviado para engine: bot={bot_instance_id}")

    return StartBotResponse(
        bot_instance_id=bot_instance_id,
        status="starting",
        message=f"Robô '{robot_info['name']}' sendo iniciado. Aguarde alguns segundos.",
        estimated_start_seconds=5
    )
```

---

## 5. ENDPOINTS COMPLEMENTARES

### 5.1 Parar Robô

```python
@router.post("/bots/{bot_instance_id}/stop")
async def stop_bot(
    bot_instance_id: str,
    current_user: dict = Depends(get_current_user)
):
    user_id = str(current_user.get("_id"))

    # Verificar ownership
    instance = await BotInstanceRepository.get_by_id(bot_instance_id)
    if not instance or instance["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="Instância não encontrada")

    if instance["status"] in ["stopped", "error"]:
        raise HTTPException(status_code=400, detail="Robô já está parado")

    # Enviar comando de stop para a engine
    redis = await get_redis()
    await redis.lpush("bot:commands", json.dumps({
        "action": "stop",
        "bot_instance_id": bot_instance_id,
        "user_id": user_id,
        "timestamp": datetime.utcnow().isoformat()
    }))

    return {"message": "Solicitação de parada enviada", "bot_instance_id": bot_instance_id}


@router.get("/bots", response_model=List[BotStatusResponse])
async def list_user_bots(current_user: dict = Depends(get_current_user)):
    user_id = str(current_user.get("_id"))
    instances = await BotInstanceRepository.get_active_by_user(user_id)

    return [
        BotStatusResponse(
            bot_instance_id=str(inst["_id"]),
            robot_id=inst["robot_id"],
            robot_name=inst["robot_name"],
            status=inst["status"],
            pair=inst["configuration"]["pair"],
            capital_usdt=inst["configuration"]["capital_usdt"],
            total_pnl_usdt=inst["metrics"]["total_pnl_usdt"],
            win_rate=inst["metrics"]["win_rate"],
            total_trades=inst["metrics"]["total_trades"],
            started_at=inst.get("started_at", "").isoformat() if inst.get("started_at") else None,
            last_heartbeat=inst.get("last_heartbeat", "").isoformat() if inst.get("last_heartbeat") else None,
        )
        for inst in instances
    ]


@router.get("/bots/{bot_instance_id}/logs")
async def get_bot_logs(
    bot_instance_id: str,
    limit: int = 100,
    level: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    user_id = str(current_user.get("_id"))
    db = get_db()

    # Verificar ownership
    instance = await BotInstanceRepository.get_by_id(bot_instance_id)
    if not instance or instance["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="Instância não encontrada")

    query = {"bot_instance_id": bot_instance_id}
    if level:
        query["level"] = level

    logs = await db["bot_execution_logs"].find(query).sort(
        "timestamp", -1
    ).limit(limit).to_list(length=limit)

    return [
        {
            "level": log["level"],
            "category": log.get("category"),
            "message": log["message"],
            "metadata": log.get("metadata"),
            "timestamp": log["timestamp"].isoformat()
        }
        for log in logs
    ]
```

---

## 6. VERIFICAÇÃO DE LIMITE DE PLANO

```python
# backend/app/plan_limits.py

PLAN_BOT_LIMITS = {
    "free": 0,
    "start": 1,
    "pro": 3,
    "pro_plus": 5,
    "quant": 10,
    "black": 20,
}


async def check_plan_bot_limit(user_id: str, db) -> dict:
    """Verifica se o usuário pode ativar mais um robô com seu plano atual."""

    # Buscar plano do usuário
    user = await db["users"].find_one({"_id": ObjectId(user_id)})
    plan = user.get("plan", "free") if user else "free"
    limit = PLAN_BOT_LIMITS.get(plan, 0)

    if limit == 0:
        return {
            "allowed": False,
            "plan": plan,
            "limit": limit,
            "current_active": 0
        }

    # Contar robôs ativos
    current_active = await db["user_bot_instances"].count_documents({
        "user_id": user_id,
        "status": {"$in": ["running", "paused", "pending"]}
    })

    return {
        "allowed": current_active < limit,
        "plan": plan,
        "limit": limit,
        "current_active": current_active
    }
```

---

## 7. FRONTEND — INTEGRAÇÃO DO BOTÃO "ATIVAR"

```tsx
// src/components/gamification/ActivateRobotModal.tsx

import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '@/context/AuthContext';
import { API_BASE_URL } from '@/config/constants';
import { useToast } from '@/hooks/use-toast';

interface ActivateRobotModalProps {
  isOpen: boolean;
  robot: { id: string; name: string; strategy: string };
  onClose: () => void;
  onActivated: (botInstanceId: string) => void;
}

export const ActivateRobotModal: React.FC<ActivateRobotModalProps> = ({
  isOpen, robot, onClose, onActivated
}) => {
  const { accessToken } = useAuthStore();
  const { toast } = useToast();

  const [config, setConfig] = useState({
    pair: 'BTC-USDT',
    capital_usdt: 100,
    timeframe: '1h',
    stop_loss_pct: 5,
    take_profit_pct: 15,
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleActivate = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE_URL}/api/trading/bots/start`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${accessToken}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ robot_id: robot.id, ...config }),
      });

      const data = await res.json();

      if (!res.ok) {
        const detail = data.detail;
        if (typeof detail === 'object' && detail.error === 'insufficient_balance') {
          setError(`Saldo insuficiente: ${detail.available_usdt} USDT disponível.`);
        } else if (typeof detail === 'object' && detail.error === 'plan_limit_reached') {
          setError(`Limite de robôs atingido. Faça upgrade do plano.`);
        } else {
          setError(detail?.message || 'Erro ao ativar robô');
        }
        return;
      }

      toast({
        title: '🚀 Robô ativado!',
        description: `${robot.name} está iniciando. Acompanhe no Dashboard.`,
      });
      onActivated(data.bot_instance_id);
      onClose();
    } catch (err) {
      setError('Erro de conexão. Tente novamente.');
    } finally {
      setLoading(false);
    }
  };

  // ... JSX do modal com campos pair, capital, timeframe, stop_loss, take_profit
};
```

---

## 8. TRATAMENTO DE ERROS

| Cenário | HTTP Status | Error Code | Mensagem |
|---|---|---|---|
| Robô não no catálogo | 404 | - | "Robô não encontrado" |
| Robô não desbloqueado | 403 | `robot_not_unlocked` | "Desbloqueie o robô primeiro" |
| Robô já ativo | 409 | `bot_already_active` | "Robô já está ativo" |
| Limite do plano | 402 | `plan_limit_reached` | "Fazer upgrade" |
| KuCoin não conectada | 400 | `kucoin_not_connected` | "Conecte API KuCoin" |
| Saldo insuficiente | 400 | `insufficient_balance` | Mostra saldo disponível |
| KuCoin API offline | 502 | `kucoin_api_error` | "Tente novamente" |
| Erro interno | 500 | - | "Erro interno" |

---

## 9. IDEMPOTÊNCIA

Se o mesmo request for enviado duas vezes (duplicate click, retry do browser):
1. Segundo request vai no item 3 (check_duplicate_robot) → retorna 409 imediatamente
2. Nenhum segundo bot é criado
3. Nenhum segundo comando vai para a engine

---

## 10. CHECKLIST

- [ ] Endpoint `POST /bots/start` implementado e testado
- [ ] Validação de saldo KuCoin antes de criar instância
- [ ] Limite de plano verificado e retornando mensagem clara
- [ ] Comando Redis enviado apenas após instância criada no banco
- [ ] Endpoint `POST /bots/{id}/stop` implementado
- [ ] Endpoint `GET /bots` retorna lista com métricas
- [ ] `ActivateRobotModal.tsx` integrado no botão "Ativar" do card
- [ ] Tratamento de todos os error codes no frontend
- [ ] Testes: cenário feliz, saldo insuficiente, limite de plano

---

## 11. CRITÉRIOS DE ACEITE

- [ ] Usuário com KuCoin conectada, robô desbloqueado e saldo suficiente ativa com sucesso
- [ ] Duplo clique em "Ativar" não cria duas instâncias
- [ ] Mensagem de erro específica para cada caso (não "Erro genérico")
- [ ] Bot visível no Dashboard com status "Iniciando..." em até 3s
- [ ] Status muda para "Running" em até 10s após ativação
- [ ] Stop funciona e cancela ordens abertas antes de confirmar
