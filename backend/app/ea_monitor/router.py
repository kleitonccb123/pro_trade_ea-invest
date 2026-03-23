"""
EA Monitor Router — MetaTrader MT4/MT5 Integration

Protocol:
  1. Frontend calls POST /ea/connect  → gets {account_id, api_key}
  2. User configures the MQL5 EA with the api_key + account_id
  3. MQL5 EA calls POST /ea/{account_id}/update  (passing api_key in X-EA-Key header)
  4. Frontend opens WS /ws/ea/{account_id}?token=JWT
  5. Every EA push is broadcast to all frontend WebSocket subscribers

Security:
  - EA-side routes:      authenticated via X-EA-Key (UUID generated at /connect)
  - Frontend routes:     authenticated via JWT Bearer token
"""

from __future__ import annotations

import asyncio
import json
import logging
import secrets
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from jose import JWTError, jwt
from pydantic import BaseModel, Field

from app.auth.dependencies import get_current_user as _get_current_user
from app.core.config import settings

logger = logging.getLogger(__name__)

# ─── Routers ─────────────────────────────────────────────────────────────────
router = APIRouter(prefix="/ea", tags=["📡 EA Monitor"])
ws_router = APIRouter(tags=["📡 EA Monitor WebSocket"])

# ─── In-memory registry ──────────────────────────────────────────────────────
# addr: account_id  → { owner_user_id, api_key, account_name, server, broker,
#                       created_at, last_seen, telemetry, positions }
_registry: Dict[str, Dict[str, Any]] = {}

# account_id → list of open WebSocket connections (frontend clients)
_subscribers: Dict[str, List[WebSocket]] = {}


# ─── Auth helper (re-usable across this module) ───────────────────────────────
async def _get_user(user: dict = Depends(_get_current_user)):
    """Normalise the user dict/object coming from SQLite auth."""
    from types import SimpleNamespace
    return SimpleNamespace(**user) if isinstance(user, dict) else user


# ─── Pydantic models ─────────────────────────────────────────────────────────

class EAPosition(BaseModel):
    id: str = Field(..., description="ID da posição no MT4/MT5")
    symbol: str = Field(..., description="Par de negociação, ex: EURUSD")
    type: str = Field(..., description="BUY | SELL")
    volume: float = Field(..., ge=0, description="Lote")
    open_price: float
    current_price: float
    sl: float = Field(0.0, description="Stop Loss (0 = sem SL)")
    tp: float = Field(0.0, description="Take Profit (0 = sem TP)")
    profit: float = Field(0.0, description="P&L flutuante em USD")
    magic: int = Field(0, description="Magic number do EA")
    comment: str = Field("", description="Comentário da ordem")
    open_time: str = Field("", description="ISO timestamp de abertura")


class ConnectRequest(BaseModel):
    account_id: str = Field(
        ...,
        min_length=3,
        max_length=20,
        pattern=r"^\d+$",
        description="Número da conta MT4/MT5 (apenas dígitos)",
    )
    account_name: str = Field("", description="Nome amigável para identificação")
    server: str = Field("", description="Servidor da corretora, ex: ICMarkets-Live")
    broker: str = Field("", description="Nome da corretora, ex: IC Markets")


class ConnectResponse(BaseModel):
    account_id: str
    api_key: str
    message: str


class EAUpdatePayload(BaseModel):
    """Payload enviado pelo MQL5 EA periodicamente."""
    balance: float = Field(0.0, description="Saldo da conta")
    equity: float = Field(0.0, description="Equidade da conta")
    margin: float = Field(0.0, description="Margem usada")
    free_margin: float = Field(0.0, description="Margem livre")
    positions: List[EAPosition] = Field(default_factory=list)
    open_orders_count: int = Field(0, description="Ordens pendentes abertas")
    strategy_id: str = Field("", description="Estratégia ativa no EA")
    magic_number: int = Field(0)
    status: str = Field("RUNNING", description="RUNNING | PAUSED | OFFLINE")
    kill_switch_active: bool = False
    permitted: bool = True
    uptime_seconds: float = Field(0.0, description="Tempo em execução (segundos)")
    realized_pnl_today: float = Field(0.0)
    floating_drawdown: float = Field(0.0)
    max_drawdown_today: float = Field(0.0)
    last_trade_open: Optional[str] = None
    last_trade_close: Optional[str] = None


class AccountInfo(BaseModel):
    account_id: str
    account_name: str
    server: str
    broker: str
    connected: bool
    last_seen: Optional[str]
    balance: float
    equity: float
    positions_count: int


class PositionsResponse(BaseModel):
    account_id: str
    last_seen: Optional[str]
    balance: float
    equity: float
    positions: List[EAPosition]


# ─── Helper: broadcast to all WS subscribers ─────────────────────────────────

async def _broadcast(account_id: str, payload: dict) -> None:
    """Send payload to every frontend WebSocket subscribed to account_id."""
    conns = list(_subscribers.get(account_id, []))
    if not conns:
        return
    message = json.dumps(payload)
    dead: List[WebSocket] = []
    for ws in conns:
        try:
            await ws.send_text(message)
        except Exception:
            dead.append(ws)
    for ws in dead:
        _subscribers[account_id] = [c for c in _subscribers[account_id] if c is not ws]


# ─── JWT auth for WebSocket ───────────────────────────────────────────────────

async def _ws_authenticate(token: str) -> Optional[str]:
    """Decode JWT and return user_id string, or None on failure."""
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.algorithm],
        )
        user_id = payload.get("sub")
        return str(user_id) if user_id else None
    except JWTError as exc:
        logger.warning("[EA WS] Token inválido: %s", exc)
        return None


# ─── EA-side REST endpoints ───────────────────────────────────────────────────

@router.post(
    "/connect",
    response_model=ConnectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar conta MT4/MT5",
)
async def connect_account(
    req: ConnectRequest,
    current_user=Depends(_get_user),
):
    """
    Registra uma conta MetaTrader 4/5 e retorna um `api_key` exclusivo.

    O `api_key` deve ser configurado no EA Expert Advisor (MQL5) para que ele
    possa enviar telemetria a `POST /ea/{account_id}/update`.

    - Retorna 200 se a conta já estava registrada pelo mesmo usuário (idempotente).
    - Retorna 409 se a conta já foi registrada por _outro_ usuário.
    """
    user_id = str(current_user.id)
    account_id = req.account_id

    existing = _registry.get(account_id)
    if existing:
        if existing["owner_user_id"] != user_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Conta {account_id} já registrada por outro usuário.",
            )
        # Idempotent — return existing key
        logger.info("[EA] Re-conexão conta=%s user=%s", account_id, user_id)
        return ConnectResponse(
            account_id=account_id,
            api_key=existing["api_key"],
            message="Conta já registrada. Reutilizando api_key existente.",
        )

    api_key = secrets.token_urlsafe(32)
    _registry[account_id] = {
        "owner_user_id": user_id,
        "api_key": api_key,
        "account_name": req.account_name or f"Conta {account_id}",
        "server": req.server,
        "broker": req.broker,
        "connected_at": datetime.now(timezone.utc).isoformat(),
        "last_seen": None,
        "balance": 0.0,
        "equity": 0.0,
        "positions": [],
        "telemetry": {},
    }

    logger.info("[EA] Nova conta registrada: account_id=%s user=%s", account_id, user_id)
    return ConnectResponse(
        account_id=account_id,
        api_key=api_key,
        message=(
            "✅ Conta registrada! Configure o EA Expert Advisor com "
            f"account_id={account_id} e api_key={api_key}."
        ),
    )


@router.post(
    "/{account_id}/update",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="EA envia telemetria (MT4/MT5 → backend)",
)
async def ea_update(
    account_id: str,
    payload: EAUpdatePayload,
    x_ea_key: str = Header(..., alias="X-EA-Key", description="api_key retornado em /ea/connect"),
):
    """
    Endpoint chamado pelo MQL5 EA periodicamente para enviar telemetria e posições.

    Requer o cabeçalho `X-EA-Key` com o `api_key` retornado em `POST /ea/connect`.

    **Uso no MQL5 (WebRequest):**
    ```mql5
    string url = "http://seu-servidor/ea/" + IntegerToString(AccountInfoInteger(ACCOUNT_LOGIN)) + "/update";
    string headers = "Content-Type: application/json\\r\\nX-EA-Key: " + API_KEY;
    // ... WebRequest(POST, url, headers, json_payload)
    ```
    """
    entry = _registry.get(account_id)
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conta {account_id} não encontrada. Registre primeiro via POST /ea/connect.",
        )
    if not secrets.compare_digest(entry["api_key"], x_ea_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="api_key inválida.",
        )

    now_iso = datetime.now(timezone.utc).isoformat()
    entry["last_seen"] = now_iso
    entry["balance"] = payload.balance
    entry["equity"] = payload.equity
    entry["positions"] = [p.model_dump() for p in payload.positions]
    entry["telemetry"] = {
        "strategy_id": payload.strategy_id,
        "magic_number": payload.magic_number,
        "status": payload.status,
        "kill_switch_active": payload.kill_switch_active,
        "permitted": payload.permitted,
        "open_positions": len(payload.positions),
        "open_orders": payload.open_orders_count,
        "unrealized_pnl": sum(p.profit for p in payload.positions),
        "realized_pnl_today": payload.realized_pnl_today,
        "floating_drawdown": payload.floating_drawdown,
        "max_drawdown_today": payload.max_drawdown_today,
        "account_balance": payload.balance,
        "account_equity": payload.equity,
        "heartbeat": now_iso,
        "uptime_seconds": payload.uptime_seconds,
        "last_trade_open": payload.last_trade_open,
        "last_trade_close": payload.last_trade_close,
        "manager_state_local": "RUNNING" if payload.permitted else "BLOCKED",
    }

    # Broadcast to frontend subscribers
    broadcast_payload = {
        "type": "ea_update",
        "account_id": account_id,
        "timestamp": now_iso,
        "telemetry": entry["telemetry"],
        "positions": entry["positions"],
    }
    asyncio.ensure_future(_broadcast(account_id, broadcast_payload))


@router.delete(
    "/{account_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Desconectar conta MT4/MT5",
)
async def disconnect_account(
    account_id: str,
    x_ea_key: str = Header(..., alias="X-EA-Key"),
):
    """Remove o registro da conta. O api_key se torna inválido."""
    entry = _registry.get(account_id)
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Conta não encontrada.")
    if not secrets.compare_digest(entry["api_key"], x_ea_key):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="api_key inválida.")
    del _registry[account_id]
    # Close all subscriber connections for this account
    for ws in _subscribers.pop(account_id, []):
        try:
            await ws.close(code=1000, reason="Conta desconectada")
        except Exception:
            pass
    logger.info("[EA] Conta desconectada: %s", account_id)


# ─── Frontend REST endpoints ──────────────────────────────────────────────────

@router.get(
    "/accounts",
    response_model=List[AccountInfo],
    summary="Listar contas conectadas do usuário",
)
async def list_accounts(current_user=Depends(_get_user)):
    """Retorna todas as contas MT4/MT5 registradas pelo usuário autenticado."""
    user_id = str(current_user.id)
    result = []
    for account_id, entry in _registry.items():
        if entry["owner_user_id"] != user_id:
            continue
        result.append(
            AccountInfo(
                account_id=account_id,
                account_name=entry["account_name"],
                server=entry["server"],
                broker=entry["broker"],
                connected=entry["last_seen"] is not None,
                last_seen=entry["last_seen"],
                balance=entry["balance"],
                equity=entry["equity"],
                positions_count=len(entry["positions"]),
            )
        )
    return result


@router.get(
    "/{account_id}/positions",
    response_model=PositionsResponse,
    summary="Posições abertas em tempo real",
)
async def get_positions(account_id: str, current_user=Depends(_get_user)):
    """
    Retorna o último snapshot de posições abertas recebido do EA.

    Os dados são atualizados a cada vez que o EA chama `POST /ea/{account_id}/update`.
    Para receber atualizações em tempo real, conecte-se ao WebSocket `/ws/ea/{account_id}`.
    """
    user_id = str(current_user.id)
    entry = _registry.get(account_id)
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Conta não encontrada.")
    if entry["owner_user_id"] != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Sem permissão para acessar esta conta.")

    return PositionsResponse(
        account_id=account_id,
        last_seen=entry["last_seen"],
        balance=entry["balance"],
        equity=entry["equity"],
        positions=[EAPosition(**p) for p in entry["positions"]],
    )


# ─── WebSocket endpoint ───────────────────────────────────────────────────────

@ws_router.websocket("/ws/ea/{account_id}")
async def websocket_ea(
    websocket: WebSocket,
    account_id: str,
    token: str = Query(None),
):
    """
    WebSocket em tempo real para monitorar uma conta MT4/MT5.

    Autenticação: `?token=JWT_TOKEN`

    Mensagens enviadas pelo servidor:
    ```json
    {
      "type": "ea_update",
      "account_id": "12345",
      "timestamp": "2026-03-12T10:00:00Z",
      "telemetry": { ... },
      "positions": [ ... ]
    }
    ```
    Mensagens de controle:
    - `{"type": "ping"}` → `{"type": "pong"}`
    - `{"type": "snapshot"}` → estado atual completo
    """
    if not token:
        await websocket.close(code=4001, reason="Token obrigatório")
        return

    user_id = await _ws_authenticate(token)
    if not user_id:
        await websocket.close(code=4002, reason="Token inválido")
        return

    entry = _registry.get(account_id)
    if not entry:
        await websocket.close(code=4004, reason="Conta não encontrada")
        return
    if entry["owner_user_id"] != user_id:
        await websocket.close(code=4003, reason="Sem permissão")
        return

    await websocket.accept()
    logger.info("[EA WS] Cliente conectado: account=%s user=%s", account_id, user_id)

    # Register subscriber
    _subscribers.setdefault(account_id, []).append(websocket)

    # Send current snapshot immediately
    if entry["telemetry"]:
        await websocket.send_json({
            "type": "ea_snapshot",
            "account_id": account_id,
            "timestamp": entry["last_seen"],
            "telemetry": entry["telemetry"],
            "positions": entry["positions"],
        })
    else:
        await websocket.send_json({
            "type": "ea_waiting",
            "account_id": account_id,
            "message": "Aguardando dados do EA…",
        })

    try:
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                msg = json.loads(data)
                if msg.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
                elif msg.get("type") == "snapshot":
                    await websocket.send_json({
                        "type": "ea_snapshot",
                        "account_id": account_id,
                        "timestamp": entry["last_seen"],
                        "telemetry": entry["telemetry"],
                        "positions": entry["positions"],
                    })
            except asyncio.TimeoutError:
                # Send keepalive ping
                await websocket.send_json({"type": "ping"})
    except WebSocketDisconnect:
        logger.info("[EA WS] Cliente desconectado: account=%s", account_id)
    except Exception as exc:
        logger.warning("[EA WS] Erro: account=%s %s", account_id, exc)
    finally:
        subs = _subscribers.get(account_id, [])
        _subscribers[account_id] = [c for c in subs if c is not websocket]
