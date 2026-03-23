"""
Kill Switch Router - Bot?o de P?nico para Emerg?ncias

Endpoints de emerg?ncia para:
1. Parar TODOS os rob?s do usu?rio
2. (Opcional) Fechar todas as posi??es abertas a mercado

?? USE COM CUIDADO! Fechar posi??es a mercado pode resultar em slippage.

Author: Crypto Trade Hub
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

from app.auth.dependencies import get_current_user
from app.core.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/emergency", tags=["?? Admin"])


# ============== SCHEMAS ==============

class KillSwitchRequest(BaseModel):
    """Requisi??o do Kill Switch."""
    close_positions: bool = Field(
        default=False,
        description="Se True, fecha todas as posi??es abertas a mercado. ?? PODE CAUSAR SLIPPAGE!"
    )
    confirm: bool = Field(
        default=False,
        description="Confirma??o obrigat?ria. Deve ser True para executar."
    )
    reason: Optional[str] = Field(
        default=None,
        description="Motivo da emerg?ncia (ser? registrado no log)",
        examples=["Queda repentina do mercado", "Problema t?cnico detectado"]
    )
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "close_positions": False,
                    "confirm": True,
                    "reason": "Teste de emerg?ncia"
                },
                {
                    "close_positions": True,
                    "confirm": True,
                    "reason": "Flash crash detectado - fechar tudo!"
                }
            ]
        }
    }


class KillSwitchResponse(BaseModel):
    """Resposta do Kill Switch."""
    success: bool = Field(description="Se a opera??o foi bem sucedida")
    message: str = Field(description="Mensagem descritiva do resultado")
    bots_stopped: int = Field(description="N?mero de rob?s que foram parados")
    positions_closed: int = Field(description="N?mero de posi??es fechadas (se solicitado)")
    errors: List[str] = Field(default=[], description="Lista de erros encontrados durante a execu??o")
    executed_at: str = Field(description="Timestamp da execu??o em ISO format")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "success": True,
                "message": "Kill Switch executado com sucesso",
                "bots_stopped": 5,
                "positions_closed": 3,
                "errors": [],
                "executed_at": "2024-01-15T10:30:00Z"
            }
        }
    }


class EmergencyStatusResponse(BaseModel):
    """Status do sistema de emerg?ncia."""
    active_bots: int = Field(description="N?mero de rob?s atualmente em execu??o")
    open_positions: int = Field(description="N?mero de posi??es abertas")
    kill_switch_available: bool = Field(description="Se o kill switch est? dispon?vel")
    last_emergency: Optional[str] = Field(
        default=None,
        description="Timestamp do ?ltimo uso do kill switch"
    )
    # DOC-K07: Detailed breakdown of open positions
    positions_detail: Optional[dict] = Field(
        default=None,
        description="Breakdown detalhado das posições abertas por fonte",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "active_bots": 3,
                "open_positions": 7,
                "kill_switch_available": True,
                "last_emergency": "2024-01-14T15:45:00Z",
                "positions_detail": {
                    "active_bot_instances": 3,
                    "local_open_trades": 7,
                    "bots_with_tracked_position": 3,
                    "estimated_open_positions": 7,
                },
            }
        }
    }


# ============== ENDPOINTS ==============

async def _count_real_open_positions(user_id: str, db) -> dict:
    """
    DOC-K07: Count real open positions combining two sources:
    1. bot_trades collection (status='open')
    2. user_bot_instances with a tracked open position (current_position is set)
    """
    local_open_count = await db["bot_trades"].count_documents({
        "user_id": user_id,
        "status": "open",
    })

    active_bots_cursor = db["user_bot_instances"].find(
        {"user_id": user_id, "status": {"$in": ["running", "paused"]}},
        {"_id": 1, "current_position": 1},
    )
    active_bots = await active_bots_cursor.to_list(length=200)
    bots_with_position = [b for b in active_bots if b.get("current_position") is not None]

    return {
        "active_bot_instances": len(active_bots),
        "local_open_trades": local_open_count,
        "bots_with_tracked_position": len(bots_with_position),
        "estimated_open_positions": max(local_open_count, len(bots_with_position)),
    }


@router.get(
    "/status",
    response_model=EmergencyStatusResponse,
    summary="? Status de Emerg?ncia",
    description="""
Retorna o status atual do sistema de emerg?ncia.

**Informa??es retornadas:**
- Quantidade de rob?s ativos
- Posi??es abertas (quando dispon?vel)
- Disponibilidade do kill switch
- ?ltimo uso do kill switch

Este endpoint deve ser consultado antes de acionar o kill switch para
confirmar a quantidade de rob?s que ser?o afetados.
    """,
    responses={
        200: {"description": "Status obtido com sucesso"},
        401: {"description": "N?o autenticado"},
        500: {"description": "Erro interno do servidor"}
    }
)
async def get_emergency_status(current_user: dict = Depends(get_current_user)):
    """
    Retorna status atual para o bot?o de p?nico.

    Mostra:
    - Quantos rob?s est?o ativos
    - Quantas posi??es abertas (contagem real)
    - Se o kill switch est? dispon?vel
    """
    try:
        db = get_db()
        user_id = str(current_user["_id"])

        # Contar instâncias de bot ativas (engine collection)
        active_bots = await db["user_bot_instances"].count_documents({
            "user_id": user_id,
            "status": {"$in": ["running", "paused"]},
        })
        # Also count legacy bots collection (older records)
        active_bots_legacy = await db["bots"].count_documents({
            "user_id": user_id,
            "status": {"$in": ["running", "active"]},
        })
        total_active = active_bots + active_bots_legacy

        # DOC-K07: Real position count — query both sources
        positions_info = await _count_real_open_positions(user_id, db)

        # Último uso do kill switch
        last_emergency = await db["emergency_logs"].find_one(
            {"user_id": user_id},
            sort=[("executed_at", -1)],
        )

        return EmergencyStatusResponse(
            active_bots=total_active,
            open_positions=positions_info["estimated_open_positions"],
            kill_switch_available=True,
            last_emergency=last_emergency["executed_at"].isoformat() if last_emergency else None,
            positions_detail=positions_info,
        )

    except Exception as e:
        logger.error(f"? Erro ao obter status de emerg?ncia: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/kill-switch",
    response_model=KillSwitchResponse,
    summary="? KILL SWITCH - Parada de Emerg?ncia",
    description="""
# ?? ATEN??O: OPERA??O CR?TICA!

Este endpoint **para TODOS os rob?s** do usu?rio imediatamente.

## Comportamento

1. **Sem `close_positions`**: Apenas para os rob?s, mantendo posi??es abertas
2. **Com `close_positions=true`**: Para rob?s E fecha todas as posi??es a mercado

## ?? Riscos

- **Slippage**: Fechar posi??es a mercado pode resultar em pre?os desfavor?veis
- **Irrevers?vel**: Uma vez executado, n?o pode ser desfeito automaticamente
- **Todas as exchanges**: Afeta rob?s em TODAS as exchanges configuradas

## Confirma??o

O campo `confirm` DEVE ser `true` para executar. Isso evita acionamentos acidentais.

## Quando usar

- ? Flash crash ou queda abrupta do mercado
- ? Comportamento an?malo detectado nos rob?s
- ? Emerg?ncia financeira pessoal
- ? Suspeita de comprometimento da conta
    """,
    responses={
        200: {"description": "Kill switch executado com sucesso"},
        400: {"description": "Confirma??o n?o fornecida"},
        401: {"description": "N?o autenticado"},
        500: {"description": "Erro durante execu??o"}
    }
)
async def execute_kill_switch(
    request: KillSwitchRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    """
    ? BOT?O DE P?NICO - Para todos os rob?s imediatamente.
    
    A??es:
    1. Para TODOS os rob?s ativos do usu?rio
    2. (Opcional) Fecha todas as posi??es abertas a mercado
    
    ?? ATEN??O:
    - Esta a??o ? IRREVERS?VEL
    - Fechar posi??es a mercado pode causar slippage
    - Requer confirma??o expl?cita (confirm: true)
    """
    # Validar confirma??o
    if not request.confirm:
        raise HTTPException(
            status_code=400,
            detail="Confirma??o obrigat?ria. Envie confirm: true para executar."
        )
    
    user_id = str(current_user["_id"])
    user_email = current_user.get("email", "unknown")
    
    logger.warning(f"? KILL SWITCH ATIVADO por {user_email} - Motivo: {request.reason or 'N?o informado'}")
    
    bots_stopped = 0
    positions_closed = 0
    errors = []
    
    try:
        db = get_db()
        
        # 1. PARAR TODOS OS ROB?S (both legacy and engine collections)
        # Engine collection (user_bot_instances)
        _reason = request.reason or "Emergência"
        await db["user_bot_instances"].update_many(
            {"user_id": user_id, "status": {"$in": ["running", "paused", "pending"]}},
            {"$set": {
                "status": "stopped",
                "stop_reason": f"Kill Switch: {_reason}",
                "emergency_stop": True,
                "stopped_at": datetime.utcnow(),
            }},
        )
        # Legacy bots collection
        bots_cursor = db["bots"].find({
            "user_id": user_id,
            "status": {"$in": ["running", "active", "starting"]}
        })
        
        async for bot in bots_cursor:
            try:
                # Atualizar status para stopped
                await db["bots"].update_one(
                    {"_id": bot["_id"]},
                    {
                        "$set": {
                            "status": "stopped",
                            "stopped_at": datetime.utcnow(),
                            "stop_reason": f"Kill Switch: {request.reason or 'Emerg?ncia'}",
                            "emergency_stop": True
                        }
                    }
                )
                bots_stopped += 1
                logger.info(f"? Rob? {bot.get('name', bot['_id'])} parado via Kill Switch")
                
            except Exception as e:
                error_msg = f"Erro ao parar rob? {bot.get('name', bot['_id'])}: {e}"
                errors.append(error_msg)
                logger.error(f"? {error_msg}")

        # DOC-K07: Notify orchestrator via Redis pub/sub to stop in-process workers
        try:
            from app.shared.redis_client import get_redis
            r = await get_redis()
            await r.publish(f"kill_switch:{user_id}", "emergency")
            logger.info("Kill switch Redis pub/sub notificado para user %s", user_id)
        except Exception as redis_exc:
            logger.warning("Falha ao notificar Redis kill switch: %s", redis_exc)
            errors.append(f"Redis notification failed: {redis_exc}")

        # DOC-K07: Cancel ALL open orders on KuCoin exchange (spot + native stops)
        cancelled_order_ids = []
        try:
            creds_doc = await db["exchange_credentials"].find_one(
                {"user_id": user_id, "exchange": "kucoin"}
            )
            if creds_doc:
                from app.security.cipher_singleton import get_cipher
                import os
                cipher = get_cipher()
                decrypted = cipher.decrypt_credentials(
                    creds_doc.get("api_key_enc", ""),
                    creds_doc.get("api_secret_enc", ""),
                    creds_doc.get("passphrase_enc", ""),
                )
                from app.integrations.kucoin.rest_client import KuCoinRESTClient
                kucoin_client = KuCoinRESTClient(
                    api_key=decrypted["api_key"],
                    api_secret=decrypted["api_secret"],
                    api_passphrase=decrypted["passphrase"],
                    sandbox=os.getenv("KUCOIN_SANDBOX", "false").lower() == "true",
                )
                try:
                    # Cancel all regular (spot) open orders
                    result = await kucoin_client.cancel_all_orders()
                    ids = result.get("cancelledOrderIds") or []
                    cancelled_order_ids.extend(ids)
                    # Also cancel all native stop orders
                    stop_cancel = await kucoin_client.get_open_stop_orders()
                    for stop_ord in stop_cancel:
                        stop_id = stop_ord.get("id") or stop_ord.get("orderId", "")
                        if stop_id:
                            try:
                                await kucoin_client.cancel_stop_order(stop_id)
                                cancelled_order_ids.append(stop_id)
                            except Exception:
                                pass
                    logger.critical(
                        "\ud83d\udea8 Kill Switch: %d ordens canceladas na KuCoin para user %s",
                        len(cancelled_order_ids), user_id,
                    )
                except Exception as kucoin_exc:
                    logger.error("Erro ao cancelar ordens KuCoin no kill switch: %s", kucoin_exc)
                    errors.append(f"KuCoin order cancel failed: {kucoin_exc}")
        except Exception as cred_exc:
            logger.warning("Credenciais KuCoin n\u00e3o encontradas para kill switch: %s", cred_exc)

        # 2. FECHAR POSI??ES (se solicitado)
        if request.close_positions:
            positions_closed = await _close_all_positions(user_id, db, errors)

        # DOC-K07: Mark open local trades as emergency-closed
        await db["bot_trades"].update_many(
            {"user_id": user_id, "status": "open"},
            {"$set": {"status": "emergency_closed", "exit_reason": "emergency_kill"}},
        )
        
        # 3. REGISTRAR LOG DE EMERG?NCIA
        await db["emergency_logs"].insert_one({
            "user_id": user_id,
            "user_email": user_email,
            "action": "kill_switch",
            "reason": request.reason,
            "close_positions": request.close_positions,
            "bots_stopped": bots_stopped,
            "positions_closed": positions_closed,
            "errors": errors,
            "executed_at": datetime.utcnow()
        })
        
        # 4. Enviar notifica??o (em background)
        background_tasks.add_task(
            _send_emergency_notification,
            user_id,
            user_email,
            bots_stopped,
            positions_closed
        )
        
        message = f"Kill Switch executado: {bots_stopped} rob?(s) parado(s)"
        if request.close_positions:
            message += f", {positions_closed} posi??o(?es) fechada(s)"
        
        return KillSwitchResponse(
            success=len(errors) == 0,
            message=message,
            bots_stopped=bots_stopped,
            positions_closed=positions_closed,
            errors=errors,
            executed_at=datetime.utcnow().isoformat()
        )
        
    except Exception as e:
        logger.error(f"? Erro cr?tico no Kill Switch: {e}")
        raise HTTPException(status_code=500, detail=f"Erro no Kill Switch: {e}")


@router.post("/stop-bot/{bot_id}")
async def emergency_stop_bot(
    bot_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Para um rob? espec?fico em emerg?ncia.
    """
    try:
        db = get_db()
        user_id = str(current_user["_id"])
        
        from bson import ObjectId
        
        result = await db["bots"].update_one(
            {
                "_id": ObjectId(bot_id),
                "user_id": user_id
            },
            {
                "$set": {
                    "status": "stopped",
                    "stopped_at": datetime.utcnow(),
                    "stop_reason": "Parada de emerg?ncia manual",
                    "emergency_stop": True
                }
            }
        )
        
        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="Rob? n?o encontrado ou j? parado")
        
        logger.info(f"? Rob? {bot_id} parado via emerg?ncia por {current_user.get('email')}")
        
        return {"success": True, "message": "Rob? parado com sucesso"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"? Erro ao parar rob? {bot_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============== ADMIN KILL SWITCH ENDPOINTS ==============
# Todos exigem is_admin=True (verificação inline — não há require_admin dependency).


@router.post(
    "/admin/global-kill",
    summary="🔴 [ADMIN] Ativar Kill Switch Global",
    tags=["🔴 Admin"],
)
async def admin_activate_global_kill(
    current_user: dict = Depends(get_current_user),
):
    """
    Ativa o kill switch global da plataforma.
    Bloqueia TODOS os bots de TODOS os usuários.
    Requer privilégio de administrador.
    """
    if not current_user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Apenas administradores podem usar este endpoint.")

    from app.risk.kill_switch import KillSwitchService
    svc = await KillSwitchService.from_app_redis()
    ok = await svc.trigger_global_kill_switch()
    if not ok:
        raise HTTPException(status_code=503, detail="Redis indisponível — kill switch não pôde ser ativado.")

    logger.critical(
        "ADMIN KILL SWITCH GLOBAL ativado por %s", current_user.get("email", "?")
    )
    return {
        "success": True,
        "message": "Kill switch global ativado. Todos os bots serão parados.",
        "activated_by": current_user.get("email"),
        "activated_at": datetime.utcnow().isoformat(),
    }


@router.delete(
    "/admin/global-kill",
    summary="🟢 [ADMIN] Desativar Kill Switch Global",
    tags=["🔴 Admin"],
)
async def admin_deactivate_global_kill(
    current_user: dict = Depends(get_current_user),
):
    """
    Desativa o kill switch global, permitindo que os bots operem novamente.
    Requer privilégio de administrador.
    """
    if not current_user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Apenas administradores podem usar este endpoint.")

    from app.risk.kill_switch import KillSwitchService
    svc = await KillSwitchService.from_app_redis()
    ok = await svc.clear_global_kill_switch()

    logger.warning(
        "ADMIN KILL SWITCH GLOBAL desativado por %s", current_user.get("email", "?")
    )
    return {
        "success": ok,
        "message": "Kill switch global desativado." if ok else "Redis indisponível.",
        "deactivated_by": current_user.get("email"),
        "deactivated_at": datetime.utcnow().isoformat(),
    }


@router.post(
    "/admin/user-kill/{target_user_id}",
    summary="🔴 [ADMIN] Ativar Kill Switch de Usuário",
    tags=["🔴 Admin"],
)
async def admin_activate_user_kill(
    target_user_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Ativa o kill switch para um usuário específico.
    Para todos os bots deste usuário.
    Requer privilégio de administrador.
    """
    if not current_user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Apenas administradores podem usar este endpoint.")

    from app.risk.kill_switch import KillSwitchService
    svc = await KillSwitchService.from_app_redis()
    ok = await svc.trigger_user_kill_switch(target_user_id)
    if not ok:
        raise HTTPException(status_code=503, detail="Redis indisponível — kill switch não pôde ser ativado.")

    logger.warning(
        "ADMIN KILL SWITCH USER ativado para user=%s por admin=%s",
        target_user_id, current_user.get("email", "?")
    )
    return {
        "success": True,
        "message": f"Kill switch ativado para o usuário {target_user_id}.",
        "target_user_id": target_user_id,
        "activated_by": current_user.get("email"),
        "activated_at": datetime.utcnow().isoformat(),
    }


@router.delete(
    "/admin/user-kill/{target_user_id}",
    summary="🟢 [ADMIN] Desativar Kill Switch de Usuário",
    tags=["🔴 Admin"],
)
async def admin_deactivate_user_kill(
    target_user_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Desativa o kill switch de um usuário específico.
    Requer privilégio de administrador.
    """
    if not current_user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Apenas administradores podem usar este endpoint.")

    from app.risk.kill_switch import KillSwitchService
    svc = await KillSwitchService.from_app_redis()
    ok = await svc.clear_user_kill_switch(target_user_id)

    logger.warning(
        "ADMIN KILL SWITCH USER desativado para user=%s por admin=%s",
        target_user_id, current_user.get("email", "?")
    )
    return {
        "success": ok,
        "message": f"Kill switch desativado para o usuário {target_user_id}." if ok else "Redis indisponível.",
        "target_user_id": target_user_id,
        "deactivated_by": current_user.get("email"),
        "deactivated_at": datetime.utcnow().isoformat(),
    }


@router.get(
    "/admin/kill-switch-status",
    summary="📊 [ADMIN] Status dos Kill Switches",
    tags=["🔴 Admin"],
)
async def admin_kill_switch_status(
    user_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    """
    Retorna o status atual de todos os kill switches.
    Parâmetro opcional `user_id` para verificar kill switch de usuário específico.
    Requer privilégio de administrador.
    """
    if not current_user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Apenas administradores podem usar este endpoint.")

    from app.risk.kill_switch import KillSwitchService
    svc = await KillSwitchService.from_app_redis()
    status = await svc.get_status(user_id=user_id)
    return {
        "kill_switch_status": status,
        "queried_user_id": user_id,
        "queried_at": datetime.utcnow().isoformat(),
    }


# ============== HELPER FUNCTIONS ==============

async def _close_all_positions(user_id: str, db, errors: List[str]) -> int:
    """
    Fecha todas as posi??es abertas do usu?rio a mercado.
    
    ?? CUIDADO: Pode causar slippage significativo em mercados vol?teis!
    """
    positions_closed = 0
    
    try:
        # Buscar credenciais do usu?rio
        credentials_cursor = db["api_credentials"].find({"user_id": user_id})
        
        async for cred in credentials_cursor:
            try:
                from app.trading.ccxt_exchange_service import CCXTExchangeService
                from app.core.encryption import decrypt_credential
                
                # Criar cliente da exchange
                exchange_service = CCXTExchangeService(
                    exchange_id=cred["exchange"],
                    api_key=decrypt_credential(cred["api_key_encrypted"]),
                    api_secret=decrypt_credential(cred["api_secret_encrypted"]),
                    passphrase=decrypt_credential(cred["passphrase_encrypted"]) if cred.get("passphrase_encrypted") else None,
                    sandbox=cred.get("sandbox", False)
                )
                
                # Obter posi??es abertas
                try:
                    positions = await exchange_service.exchange.fetch_positions()
                except:
                    # Nem todas exchanges suportam fetch_positions
                    positions = []
                
                for position in positions:
                    if position.get("contracts", 0) > 0 or position.get("notional", 0) > 0:
                        try:
                            symbol = position.get("symbol")
                            side = "sell" if position.get("side") == "long" else "buy"
                            amount = abs(float(position.get("contracts", 0)))
                            
                            if amount > 0:
                                await exchange_service.exchange.create_market_order(
                                    symbol=symbol,
                                    side=side,
                                    amount=amount
                                )
                                positions_closed += 1
                                logger.info(f"? Posi??o {symbol} fechada a mercado")
                                
                        except Exception as e:
                            error_msg = f"Erro ao fechar posi??o {position.get('symbol')}: {e}"
                            errors.append(error_msg)
                            logger.error(f"? {error_msg}")
                            
            except Exception as e:
                error_msg = f"Erro ao processar exchange {cred.get('exchange')}: {e}"
                errors.append(error_msg)
                logger.error(f"? {error_msg}")
                
    except Exception as e:
        error_msg = f"Erro ao fechar posi??es: {e}"
        errors.append(error_msg)
        logger.error(f"? {error_msg}")
    
    return positions_closed


async def _send_emergency_notification(
    user_id: str,
    user_email: str,
    bots_stopped: int,
    positions_closed: int
):
    """
    Envia notifica??o de emerg?ncia para o usu?rio.
    """
    try:
        db = get_db()
        
        # Criar notifica??o no banco
        await db["notifications"].insert_one({
            "user_id": user_id,
            "type": "emergency",
            "title": "? Kill Switch Ativado",
            "message": f"{bots_stopped} rob?(s) parado(s). {positions_closed} posi??o(?es) fechada(s).",
            "severity": "critical",
            "read": False,
            "created_at": datetime.utcnow()
        })
        
        # TODO: Enviar email/telegram/discord se configurado
        logger.info(f"? Notifica??o de emerg?ncia enviada para {user_email}")
        
    except Exception as e:
        logger.error(f"? Erro ao enviar notifica??o de emerg?ncia: {e}")
