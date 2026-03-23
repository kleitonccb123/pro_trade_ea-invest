from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from fastapi import APIRouter, HTTPException, status, WebSocket, WebSocketDisconnect, Depends
from pydantic import BaseModel
from typing import Optional, Dict, List

from app.bots import service as bots_service_module
from app.bots.exceptions import NotFound, InvalidStateTransition
from app.bots.websocket_manager import websocket_manager
from app.bots.repository import BotsRepository
from app.auth.dependencies import get_current_user, get_current_admin_user
from app.auth.subscription import verificar_assinatura_ativa, RequirePlan
from app.core.license_middleware import LicenseService, require_bot_slot
from app.core.database import get_db
from app.services.activation_manager import ActivationManager
from app.services.balance_guard import BalanceGuard
from app.services.kill_switch import KillSwitch
from app.plan_limits import check_bot_quota
from fastapi import Body

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/bots", tags=["bots"])
service = bots_service_module.BotsService()


# WebSocket connection manager for PnL updates
class PnLConnectionManager:
    """Manages WebSocket connections for real-time PnL updates."""
    
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
        self._update_tasks: Dict[str, asyncio.Task] = {}
    
    async def connect(self, websocket: WebSocket, bot_id: str):
        """Connect a client to receive PnL updates for a specific bot."""
        await websocket.accept()
        if bot_id not in self.active_connections:
            self.active_connections[bot_id] = []
        self.active_connections[bot_id].append(websocket)
        logger.info(f"Client connected to PnL stream for bot {bot_id}")
        
        # Start sending updates if not already running
        if bot_id not in self._update_tasks or self._update_tasks[bot_id].done():
            self._update_tasks[bot_id] = asyncio.create_task(
                self._send_pnl_updates(bot_id)
            )
    
    def disconnect(self, websocket: WebSocket, bot_id: str):
        """Disconnect a client from PnL updates."""
        if bot_id in self.active_connections:
            if websocket in self.active_connections[bot_id]:
                self.active_connections[bot_id].remove(websocket)
            if not self.active_connections[bot_id]:
                del self.active_connections[bot_id]
                # Cancel update task if no more clients
                if bot_id in self._update_tasks:
                    self._update_tasks[bot_id].cancel()
                    del self._update_tasks[bot_id]
        logger.info(f"Client disconnected from PnL stream for bot {bot_id}")
    
    async def _send_pnl_updates(self, bot_id: str):
        """Send periodic PnL updates to all connected clients."""
        try:
            while bot_id in self.active_connections and self.active_connections[bot_id]:
                try:
                    # Get latest bot statistics
                    stats = await self._get_bot_pnl(bot_id)
                    
                    # Broadcast to all connected clients
                    disconnected = []
                    for ws in self.active_connections.get(bot_id, []):
                        try:
                            await ws.send_json(stats)
                        except Exception as e:
                            logger.warning(f"Failed to send PnL to client: {e}")
                            disconnected.append(ws)
                    
                    # Clean up disconnected clients
                    for ws in disconnected:
                        self.disconnect(ws, bot_id)
                    
                except Exception as e:
                    logger.error(f"Error in PnL update loop: {e}")
                
                # Wait before next update (2 seconds)
                await asyncio.sleep(2)
                
        except asyncio.CancelledError:
            logger.info(f"PnL update task cancelled for bot {bot_id}")
    
    async def _get_bot_pnl(self, bot_id: str) -> Dict:
        """Get current PnL data for a bot."""
        try:
            # Try to get real data from repository
            instance = await BotsRepository.get_latest_instance(bot_id)
            
            if instance:
                trades = await BotsRepository.get_instance_trades(
                    str(instance.get("_id")),
                    limit=100
                )
                
                # Calculate PnL from trades
                total_pnl = sum(t.get("pnl", 0) for t in trades)
                total_trades = len(trades)
                winning_trades = len([t for t in trades if t.get("pnl", 0) > 0])
                win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
                
                return {
                    "type": "pnl_update",
                    "bot_id": bot_id,
                    "instance_id": str(instance.get("_id")),
                    "timestamp": datetime.utcnow().isoformat(),
                    "data": {
                        "state": instance.get("state", "stopped"),
                        "total_pnl": round(total_pnl, 2),
                        "total_pnl_percent": round(total_pnl / 1000 * 100, 2),  # Assuming 1000 initial
                        "total_trades": total_trades,
                        "winning_trades": winning_trades,
                        "win_rate": round(win_rate, 2),
                        "current_position": instance.get("current_position"),
                        "last_trade": trades[0] if trades else None,
                        "started_at": instance.get("started_at"),
                        "last_heartbeat": instance.get("last_heartbeat"),
                    }
                }
            
            # Return mock data if no real data available
            return {
                "type": "pnl_update",
                "bot_id": bot_id,
                "timestamp": datetime.utcnow().isoformat(),
                "data": {
                    "state": "stopped",
                    "total_pnl": 0,
                    "total_pnl_percent": 0,
                    "total_trades": 0,
                    "winning_trades": 0,
                    "win_rate": 0,
                    "current_position": None,
                    "last_trade": None,
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to get PnL for bot {bot_id}: {e}")
            return {
                "type": "error",
                "bot_id": bot_id,
                "timestamp": datetime.utcnow().isoformat(),
                "error": str(e)
            }


# Global PnL connection manager
pnl_manager = PnLConnectionManager()


class BotCreateRequest(BaseModel):
    name: str
    symbol: str
    config: dict | None = None


class BinanceConfigRequest(BaseModel):
    api_key: str
    api_secret: str
    symbol: str
    testnet: bool = True


class ManualOrderRequest(BaseModel):
    symbol: str
    side: str  # 'BUY' or 'SELL'
    quantity: float
    order_type: str = 'market'  # 'market' or 'limit'
    price: Optional[float] = None


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_bot(
    req: BotCreateRequest,
    current_user: dict = Depends(get_current_user),
    _sub: dict = Depends(verificar_assinatura_ativa),
):
    bot = await service.create_bot(req.name, req.symbol, req.config)
    return {"id": bot.id, "name": bot.name, "symbol": bot.symbol}


@router.post("/{id}/start")
async def start_bot(
    id: str,
    binance_config: Optional[BinanceConfigRequest] = None,
    current_user: dict = Depends(get_current_user),
    _license_check: bool = Depends(require_bot_slot),
    _sub: dict = Depends(verificar_assinatura_ativa),
):
    """
    ? Inicia um bot com valida??es de cr?dito, singleton e saldo.
    
    Valida??es:
    1. **Cr?ditos de Ativa??o**: Verifica se usu?rio tem cr?ditos para ativar bot
    2. **Singleton Rule**: Se outro bot est? rodando, faz graceful_stop autom?tico
    3. **Balance Guard**: Verifica se h? saldo suficiente na exchange
    
    Requires:
    - Valid authentication
    - Active license
    - Available activation credits
    - Sufficient exchange balance (for live trading)
    """
    try:
        user_id = current_user.get("_id")
        user_plan = str(current_user.get("plan", "free")).lower()

        # ===== 0. QUOTA POR PLANO (DOC-09) =====================================
        db = get_db()
        try:
            await check_bot_quota(db, str(user_id), user_plan)
        except ValueError as quota_err:
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "plan_quota_exceeded",
                    "message": str(quota_err),
                    "plan": user_plan,
                },
            )

        # ===== 1. VALIDA??O DE CR?DITOS ========================================
        activation_result = await ActivationManager.validate_activation(user_id, id)
        
        if not activation_result["can_activate"]:
            raise HTTPException(
                status_code=402,  # Payment Required
                detail={
                    "error": "insufficient_credits",
                    "message": activation_result["message"],
                    "credits_remaining": activation_result["credits_remaining"],
                    "required_activation_credits": 1
                }
            )
        
        # ===== 2. VALIDA??O DE SALDO (se live trading) ==========================
        if binance_config and binance_config.api_key:
            try:
                await BalanceGuard.validate_before_start(
                    user_id=user_id,
                    bot_id=id,
                    api_key=binance_config.api_key,
                    api_secret=binance_config.api_secret,
                    exchange=binance_config.exchange or "kucoin"
                )
            except ValueError as e:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "insufficient_balance",
                        "message": str(e),
                        "check": "Balance Guard validation failed"
                    }
                )
        
        # ===== 3. ATIVAR BOT COM GRACEFUL STOP AUTOM?TICO =======================
        activation_info = await ActivationManager.activate_bot(
            user_id=user_id,
            bot_id=id,
            graceful_stop_previous=True
        )
        
        # ===== 4. INICIAR EXECU??O =============================================
        instance = await service.create_instance(id, user_id)
        binance_dict = binance_config.model_dump() if binance_config else None
        await service.start(instance.id, binance_dict)
        
        mode = "live" if binance_config else "simulation"
        
        return {
            "status": "started",
            "instance_id": str(instance.id),
            "bot_id": id,
            "mode": mode,
            "testnet": binance_config.testnet if binance_config else None,
            "user_id": str(user_id),
            "activation": {
                "credits_consumed": activation_info["credits_consumed"],
                "credits_remaining": activation_result["credits_remaining"] - activation_info["credits_consumed"],
                "previous_bot_stopped": activation_info["previous_bot_stopped"]
            }
        }
        
    except HTTPException:
        raise
    except NotFound:
        raise HTTPException(status_code=404, detail="Bot not found")
    except InvalidStateTransition as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"Failed to start bot {id} for user {current_user.get('_id')}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start bot: {str(e)}"
        )


@router.post("/{instance_id}/manual-order")
async def place_manual_order(instance_id: int, order: ManualOrderRequest):
    """Place manual order for live trading instance."""
    try:
        result = await service.place_manual_order(
            instance_id=instance_id,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            order_type=order.order_type,
            price=order.price
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Order failed: {str(e)}")


@router.get("/{instance_id}/balance")
async def get_account_balance(instance_id: int):
    """Get account balance for live trading instance."""
    try:
        balance = await service.get_account_balance(instance_id)
        return {"balances": balance}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get balance: {str(e)}")


@router.post("/{id}/pause")
async def pause_bot(id: int):
    try:
        await service.pause(id)
    except NotFound:
        raise HTTPException(status_code=404, detail="Instance not found")
    return {"status": "paused"}


@router.post("/{id}/stop")
async def stop_bot(id: int):
    try:
        await service.stop(id)
    except NotFound:
        raise HTTPException(status_code=404, detail="Instance not found")
    return {"status": "stopped"}


# ============ ? KILL SWITCH - SEGURAN?A EMERGENCIAL ========================

@router.post("/admin/kill-switch/activate/{user_id}")
async def activate_kill_switch(
    user_id: str,
    reason: str = "Security incident",
    current_user: dict = Depends(get_current_admin_user)
):
    """
    ? EMERG?NCIA: Desativa TODOS os bots de um usu?rio instantaneamente.
    
    ?? REQUER: Admin ou autoriza??o de seguran?a
    
    Casos de uso:
    - Suspeita de hack (API Key comprometida)
    - Erro cr?tico no sistema
    - Viola??o de pol?tica
    - Investiga??o de fraude
    
    O Kill Switch:
    1. Para todos os bots em execu??o
    2. Remove-os de slots ativos
    3. Registra evento na auditoria (severity=critical)
    
    Exemplo:
    ```bash
    curl -X POST \\
      http://localhost:8000/bots/admin/kill-switch/activate/user123 \\
      -H "Authorization: Bearer TOKEN" \\
      -d '{"reason": "API key compromise suspected"}'
    ```
    """
    try:
        result = await KillSwitch.activate_for_user(
            user_id=user_id,
            reason=reason,
            triggered_by=current_user.get("email", "unknown")
        )
        
        return {
            "status": "activated",
            "kill_switch": result,
            "message": f"? Kill Switch activated for user {user_id}. All bots stopped."
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"Kill switch activation failed for user {user_id}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/admin/kill-switch/deactivate/{user_id}")
async def deactivate_kill_switch(
    user_id: str,
    current_user: dict = Depends(get_current_admin_user)
):
    """
    ? Desativa o Kill Switch e permite que o usu?rio volte a usar bots.
    
    ?? REQUER: Admin ou autoriza??o de seguran?a
    
    Nota: N?o reinicia bots automaticamente, apenas remove restri??o.
    O usu?rio pode fazer start manualmente ap?s isso.
    """
    try:
        result = await KillSwitch.deactivate_for_user(
            user_id=user_id,
            reason=f"Deactivated by {current_user.get('email')}"
        )
        
        return {
            "status": "deactivated",
            "message": f"? Kill Switch deactivated for user {user_id}. User can now start bots again."
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"Kill switch deactivation failed for user {user_id}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/admin/kill-switch/status/{user_id}")
async def get_kill_switch_status(
    user_id: str,
    current_user: dict = Depends(get_current_admin_user)
):
    """
    Verifica status do Kill Switch para um usu?rio.
    
    Returns status atual e hist?rico de ativa??es.
    """
    try:
        is_active = await KillSwitch.is_active(user_id)
        history = await KillSwitch.get_history(user_id, limit=5)
        
        return {
            "user_id": user_id,
            "kill_switch_active": is_active,
            "recent_activations": [
                {
                    "timestamp": e.get("timestamp"),
                    "reason": e.get("reason"),
                    "triggered_by": e.get("triggered_by"),
                    "bots_affected": e.get("bots_affected")
                }
                for e in history
            ]
        }
        
    except Exception as e:
        logger.exception(f"Failed to get kill switch status for {user_id}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("")
async def get_bots(limit: int = 100):
    bots = await service.get_bots(limit)
    return [{"id": bot.id, "name": bot.name, "symbol": bot.symbol} for bot in bots]


# ========== ? SWAP CONFIGURATION WITH CREDIT LIMITS ========================

@router.put("/{bot_id}/config")
async def update_bot_config(
    bot_id: str,
    new_config: dict = Body(...),
    current_user: dict = Depends(get_current_user)
):
    """
    ? Atualiza a configura??o de um bot com valida??o de Swap Limit.
    
    Swap Limit Rules:
    - 0-2 swaps (altera??es): GR?TIS
    - 3+ swaps: Custa 1 cr?dito de ativa??o por swap
    
    Response:
    ```json
    {
        "updated": true,
        "swap_info": {
            "swap_number": 3,
            "was_free": false,
            "credits_consumed": 1,
            "credits_remaining": 4
        }
    }
    ```
    
    Erros poss?veis:
    - 400: Insuficientes cr?ditos para swap pago
    - 404: Bot n?o encontrado
    - 403: Bot n?o pertence ao usu?rio
    """
    try:
        user_id = current_user.get("_id")
        
        # Validar swap
        swap_validation = await ActivationManager.validate_swap(user_id, bot_id)
        
        if not swap_validation["can_swap"]:
            raise HTTPException(
                status_code=402,  # Payment Required
                detail={
                    "error": "swap_limit_exceeded",
                    "message": swap_validation["message"],
                    "is_free": swap_validation["is_free"],
                    "will_consume_credits": swap_validation["will_consume_credits"]
                }
            )
        
        # Buscar configura??o antiga do bot
        bot = await bots_repo.find_bot_by_id(bot_id)
        if not bot:
            raise HTTPException(status_code=404, detail="Bot not found")
        
        # Verificar propriedade
        if str(bot.get("user_id")) != str(user_id):
            raise HTTPException(status_code=403, detail="Bot does not belong to you")
        
        old_config = bot.get("config", {})
        
        # Registrar swap no hist?rico
        swap_record = await ActivationManager.record_swap(
            user_id=user_id,
            bot_id=bot_id,
            old_config=old_config,
            new_config=new_config,
            change_type="config_update"
        )
        
        # Atualizar config do bot no banco
        await bots_repo.update_bot(
            bot_id,
            {
                "config": new_config,
                "last_updated": datetime.utcnow()
            }
        )
        
        # Obter cr?ditos atualizados
        user = await user_repo.find_by_id(user_id)
        credits_remaining = (
            user.get("activation_credits", 1) - 
            user.get("activation_credits_used", 0)
        )
        
        return {
            "updated": True,
            "bot_id": bot_id,
            "swap_info": {
                "swap_number": swap_record["swap_number"],
                "was_free": swap_record["was_free"],
                "credits_consumed": swap_record["credits_consumed"],
                "credits_remaining": credits_remaining
            },
            "message": f"? Config updated. "
                      f"Swap #{swap_record['swap_number']} "
                      f"({'FREE' if swap_record['was_free'] else 'PAID'})"
        }
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"Failed to update config for bot {bot_id}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{bot_id}/swap-status")
async def get_bot_swap_status(
    bot_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Retorna status de swaps/reconfigs de um bot.
    
    Mostra:
    - N?mero de swaps realizados
    - Hist?rico de swaps
    - Custo do pr?ximo swap (se aplic?vel)
    """
    try:
        user_id = current_user.get("_id")
        bot = await bots_repo.find_bot_by_id(bot_id)
        
        if not bot:
            raise HTTPException(status_code=404, detail="Bot not found")
        
        if str(bot.get("user_id")) != str(user_id):
            raise HTTPException(status_code=403, detail="Bot does not belong to you")
        
        swap_count = bot.get("swap_count", 0)
        swap_history = bot.get("swap_history", [])
        
        swap_validation = await ActivationManager.validate_swap(user_id, bot_id)
        
        return {
            "bot_id": bot_id,
            "swap_count": swap_count,
            "free_swaps_used": min(swap_count, ActivationManager.FREE_SWAPS_LIMIT),
            "free_swaps_remaining": max(
                0,
                ActivationManager.FREE_SWAPS_LIMIT - swap_count
            ),
            "next_swap": {
                "is_free": swap_validation["is_free"],
                "will_cost_credits": swap_validation["will_consume_credits"]
            },
            "swap_history": [
                {
                    "timestamp": s.get("timestamp"),
                    "change_type": s.get("change_type"),
                    "credit_charged": s.get("credit_charged")
                }
                for s in swap_history[-5:]  # ?ltimos 5 swaps
            ]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to get swap status for bot {bot_id}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/instances")
async def get_instances(limit: int = 100):
    instances = await service.get_instances(limit)
    return [
        {
            "id": inst.id,
            "bot_id": inst.bot_id,
            "state": inst.state,
            "started_at": inst.started_at,
            "last_heartbeat": inst.last_heartbeat,
        }
        for inst in instances
    ]


# WebSocket endpoint for real-time data
@router.websocket("/ws/{client_type}")
async def websocket_endpoint(websocket: WebSocket, client_type: str = "dashboard"):
    """WebSocket endpoint for real-time trading data.
    
    Requires authentication via Bearer token in query parameter or headers.
    client_type can be: 'dashboard', 'robots', 'trades'
    
    Usage:
        ws = new WebSocket('ws://localhost:8000/bots/ws/dashboard?token=YOUR_JWT_TOKEN')
    """
    
    # 🔐 Extract token from query parameter or Authorization header
    token = websocket.query_params.get("token") if websocket.query_params else None
    
    if not token:
        # Try to get from headers (if frontend sends it there)
        auth_header = websocket.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
    
    if not token:
        # No token provided - close connection
        logger.warning(f"❌ WebSocket connection attempt without authentication from {websocket.client}")
        await websocket.close(code=4001, reason="Authentication required. Provide token as ?token=JWT_TOKEN")
        return
    
    # ✓ Validate token using auth service
    try:
        from app.auth import service as auth_service
        payload = auth_service.decode_token(token)
        user_id = payload.get("sub")
        
        if not user_id:
            logger.warning(f"❌ Invalid WebSocket token (no sub claim) from {websocket.client}")
            await websocket.close(code=4002, reason="Invalid token")
            return
            
        logger.info(f"✓ WebSocket authenticated for user: {user_id}, client_type: {client_type}")
    except Exception as e:
        logger.warning(f"❌ WebSocket authentication failed: {e}")
        await websocket.close(code=4003, reason="Token validation failed")
        return
    
    # ✓ Connection authorized - proceed
    await websocket_manager.connect(websocket, client_type)
    try:
        while True:
            # Keep connection alive and handle any incoming messages
            data = await websocket.receive_text()
            # You can handle client messages here if needed
            # For example, client requesting specific symbol data
    except WebSocketDisconnect:
        websocket_manager.disconnect(websocket, client_type)
        logger.info(f"WebSocket disconnected for user: {user_id}, client_type: {client_type}")
async def stop_bot(id: int):
    try:
        await service.stop(id)
    except NotFound:
        raise HTTPException(status_code=404, detail="Instance not found")
    return {"status": "stopped"}


@router.get("")
async def list_bots():
    bots = await service.list_bots()
    return bots


@router.get("/{bot_id}/detail")
async def get_bot_detail(bot_id: str, current_user: dict = Depends(get_current_user)):
    """Get a specific bot by ID for the authenticated user."""
    db = get_db()
    from bson import ObjectId
    try:
        query = {"user_id": str(current_user.get("_id"))}
        # Support both ObjectId and string IDs
        try:
            query["_id"] = ObjectId(bot_id)
        except Exception:
            query["_id"] = bot_id

        bot = await db["bots"].find_one(query)
        if not bot:
            raise HTTPException(status_code=404, detail="Bot not found")
        bot["_id"] = str(bot["_id"])
        return bot
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to get bot {bot_id}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{bot_id}/update")
async def update_bot_fields(bot_id: str, payload: dict = Body(...), current_user: dict = Depends(get_current_user)):
    """Update a bot's fields (name, symbol, etc.)."""
    db = get_db()
    from bson import ObjectId
    try:
        # Sanitize: only allow safe fields to be updated
        allowed_fields = {"name", "symbol", "config", "status", "description"}
        safe_payload = {k: v for k, v in payload.items() if k in allowed_fields}
        if not safe_payload:
            raise HTTPException(status_code=400, detail="No valid fields to update")

        safe_payload["updated_at"] = datetime.utcnow()

        try:
            obj_id = ObjectId(bot_id)
        except Exception:
            obj_id = bot_id

        result = await db["bots"].update_one(
            {"_id": obj_id, "user_id": str(current_user.get("_id"))},
            {"$set": safe_payload}
        )
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Bot not found or not owned by you")
        return {"status": "updated", "bot_id": bot_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to update bot {bot_id}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{bot_id}/remove")
async def delete_bot_by_id(bot_id: str, current_user: dict = Depends(get_current_user)):
    """Delete a bot. Stops it first if running."""
    db = get_db()
    from bson import ObjectId
    try:
        try:
            obj_id = ObjectId(bot_id)
        except Exception:
            obj_id = bot_id

        user_id = str(current_user.get("_id"))

        # Stop the bot if running
        await db["bots"].update_one(
            {"_id": obj_id, "user_id": user_id, "status": {"$in": ["running", "paused"]}},
            {"$set": {"status": "stopped", "stopped_at": datetime.utcnow()}}
        )

        result = await db["bots"].delete_one({"_id": obj_id, "user_id": user_id})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Bot not found or not owned by you")
        return {"status": "deleted", "bot_id": bot_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to delete bot {bot_id}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/user/instances")
async def list_user_instances(current_user: dict = Depends(get_current_user), limit: int = 100):
    """List all bot instances for the authenticated user."""
    db = get_db()
    try:
        user_id = str(current_user.get("_id"))
        cursor = db["bot_instances"].find({"user_id": user_id}).sort("started_at", -1).limit(limit)
        instances = []
        async for inst in cursor:
            inst["_id"] = str(inst["_id"])
            instances.append(inst)
        return instances
    except Exception as e:
        logger.exception("Failed to list instances")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{id}/trades")
async def list_trades(id: int):
    try:
        trades = await service.list_trades(id)
    except NotFound:
        raise HTTPException(status_code=404, detail="Instance not found")
    # shallow serialization
    return [
        {
            "id": t.id,
            "entry_price": t.entry_price,
            "exit_price": t.exit_price,
            "quantity": t.quantity,
            "pnl": t.pnl,
            "pnl_percent": t.pnl_percent,
            "timestamp": t.timestamp,
            "side": t.side,
        }
        for t in trades
    ]


@router.get("/analytics/most-used")
async def get_most_used_bots(days: int = 7):
    """Get top 10 most used bots in the last N days (7, 30, 90)."""
    if days not in [7, 30, 90]:
        raise HTTPException(status_code=400, detail="Days must be 7, 30, or 90")
    
    try:
        bots = await service.get_most_used_bots(days)
        return {"days": days, "bots": bots}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch analytics: {str(e)}")


@router.get("/analytics/most-profitable")
async def get_most_profitable_bots(days: int = 7):
    """Get top 10 most profitable bots in the last N days (7, 30, 90)."""
    if days not in [7, 30, 90]:
        raise HTTPException(status_code=400, detail="Days must be 7, 30, or 90")
    
    try:
        bots = await service.get_most_profitable_bots(days)
        return {"days": days, "bots": bots}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch analytics: {str(e)}")


# ==================== PnL WebSocket Endpoint ====================

@router.websocket("/ws/pnl/{bot_id}")
async def websocket_pnl_endpoint(websocket: WebSocket, bot_id: str):
    """
    WebSocket endpoint for real-time PnL updates.
    
    Sends updates every 2 seconds with:
    - Current P&L
    - Total trades
    - Win rate
    - Current position
    - Last trade info
    
    Example client connection:
        ws = new WebSocket('ws://localhost:8000/bots/ws/pnl/123');
        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            console.log('PnL Update:', data);
        };
    """
    await pnl_manager.connect(websocket, bot_id)
    try:
        # Send initial data immediately
        initial_data = await pnl_manager._get_bot_pnl(bot_id)
        await websocket.send_json(initial_data)
        
        # Keep connection alive and handle client messages
        while True:
            try:
                # Wait for any client message (ping/pong or commands)
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=30.0  # Heartbeat timeout
                )
                
                # Handle client commands
                try:
                    msg = json.loads(data)
                    if msg.get("type") == "ping":
                        await websocket.send_json({"type": "pong", "timestamp": datetime.utcnow().isoformat()})
                    elif msg.get("type") == "request_update":
                        # Send immediate update on request
                        update = await pnl_manager._get_bot_pnl(bot_id)
                        await websocket.send_json(update)
                except json.JSONDecodeError:
                    pass  # Ignore non-JSON messages
                    
            except asyncio.TimeoutError:
                # Send heartbeat
                await websocket.send_json({"type": "heartbeat", "timestamp": datetime.utcnow().isoformat()})
                
    except WebSocketDisconnect:
        pnl_manager.disconnect(websocket, bot_id)
        logger.info(f"WebSocket disconnected for bot {bot_id}")
    except Exception as e:
        logger.error(f"WebSocket error for bot {bot_id}: {e}")
        pnl_manager.disconnect(websocket, bot_id)
