"""
OrderReconciliationWorker — Task 2.1

Background worker que sincroniza ordens PENDING com KuCoin a cada minuto.

Responsabilidades:
✓ Detectar ordens que perderam sincronização
✓ Corrigir status de ordens preenchidas
✓ Alertar em caso de divergências críticas
✓ Rodar sem bloquear execução de novas ordens

Fluxo:
1. A cada 60 segundos:
   ├─ Busca todos os usuários com credenciais KuCoin
   ├─ Para cada usuário:
   │  ├─ Busca ordens PENDING no banco
   │  ├─ Busca ordens reais na KuCoin
   │  ├─ Compara pelo client_oid
   │  └─ Sincroniza divergências
   └─ Loga resultados

Author: Crypto Trade Hub — Task 2.1
Date: March 2026
"""

from __future__ import annotations

import asyncio
import logging
from decimal import Decimal
from datetime import datetime
from typing import Dict, List, Optional, Any

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from app.core.database import get_db
from app.trading.credentials_repository import CredentialsRepository, ExchangeType
from app.exchanges.kucoin.client import KuCoinRawClient, KuCoinAPIError
from app.exchanges.kucoin.normalizer import OrderStatus, NormalizedOrder

logger = logging.getLogger(__name__)


class ReconciliationResult:
    """Resultado de uma reconciliação de usuário."""
    
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.timestamp = datetime.utcnow()
        self.pending_orders_db: int = 0
        self.orders_synced: int = 0
        self.orders_missing: int = 0
        self.orders_diverged: int = 0
        self.errors: List[str] = []
    
    def __repr__(self) -> str:
        return (
            f"ReconciliationResult(user={self.user_id} | "
            f"pending={self.pending_orders_db} | "
            f"synced={self.orders_synced} | "
            f"missing={self.orders_missing} | "
            f"diverged={self.orders_diverged} | "
            f"errors={len(self.errors)})"
        )


class OrderReconciliationWorker:
    """
    Background worker para sincronização de ordens.
    
    Roda indefinidamente a cada 60 segundos.
    
    Típico para usar:
    ```python
    worker = OrderReconciliationWorker()
    
    # Em main.py ou startup:
    asyncio.create_task(worker.start())
    ```
    """
    
    def __init__(self, interval_seconds: int = 60):
        """
        Args:
            interval_seconds: Intervalo entre reconciliações (default 60s)
        """
        self.interval_seconds = interval_seconds
        self._running = False
        self._creds_repo = CredentialsRepository()
    
    async def start(self) -> None:
        """Inicia worker infinito. Execute como background task."""
        logger.info(f"🔄 OrderReconciliationWorker iniciado (intervalo={self.interval_seconds}s)")
        self._running = True
        
        while self._running:
            try:
                await self.reconcile_all_users()
            except Exception as e:
                logger.error(f"❌ Erro crítico no reconciliation loop: {e}", exc_info=True)
            
            # Aguarda próximo ciclo
            await asyncio.sleep(self.interval_seconds)
    
    def stop(self) -> None:
        """Para o worker gracefully."""
        logger.info("⛔ Parando OrderReconciliationWorker...")
        self._running = False
    
    async def reconcile_all_users(self) -> None:
        """
        Reconcilia ordens de TODOS os usuários com credenciais KuCoin.
        
        Lógica:
        1. Busca usuários com credenciais KuCoin configuradas
        2. Para cada um: chama reconcile_user_orders()
        3. Loga estatísticas gerais
        """
        db = get_db()
        
        # Buscar usuários com credenciais KuCoin
        credentials_col = db["credentials"]
        users_with_kucoin = await credentials_col.find(
            {"exchange": "kucoin", "active": True}
        ).distinct("user_id")
        
        if not users_with_kucoin:
            logger.debug("ℹ️ Nenhum usuário com credenciais KuCoin encontrado")
            return
        
        logger.debug(f"🔄 Reconciliando {len(users_with_kucoin)} usuários...")
        
        total_synced = 0
        total_missing = 0
        total_diverged = 0
        
        # Reconciliar cada usuário
        for user_id in users_with_kucoin:
            try:
                result = await self.reconcile_user_orders(user_id)
                total_synced += result.orders_synced
                total_missing += result.orders_missing
                total_diverged += result.orders_diverged
                
                if result.pending_orders_db > 0:
                    logger.info(f"✅ {result}")
                
            except Exception as e:
                logger.error(f"❌ Erro ao reconciliar user={user_id}: {e}")
        
        # Log resumido
        if total_synced > 0 or total_missing > 0 or total_diverged > 0:
            logger.info(
                f"📊 Reconciliação completa | "
                f"Sincronizadas: {total_synced} | "
                f"Faltando: {total_missing} | "
                f"Divergências: {total_diverged}"
            )
    
    async def reconcile_user_orders(self, user_id: str) -> ReconciliationResult:
        """
        Reconcilia ordens de UM usuário.
        
        Fluxo:
        1. Busca ordens PENDING do banco
        2. Busca ordens reais da KuCoin
        3. Compara pelo client_oid
        4. Sincroniza divergências
        5. Retorna resultado
        
        Args:
            user_id: ID do usuário
            
        Returns:
            ReconciliationResult com estatísticas
        """
        result = ReconciliationResult(user_id)
        db = get_db()
        
        # ─────────────────────────────────────────────────────────────────
        # [1/4] Buscar ordens PENDING do banco
        # ─────────────────────────────────────────────────────────────────
        
        try:
            pending_orders_db = await db["trading_orders"].find({
                "user_id": user_id,
                "status": "pending"
            }).to_list(length=None)
            
            result.pending_orders_db = len(pending_orders_db)
            
            if result.pending_orders_db == 0:
                logger.debug(f"ℹ️ Nenhuma ordem pending para user={user_id}")
                return result
            
            logger.debug(
                f"🔍 Encontradas {result.pending_orders_db} ordens pending "
                f"para user={user_id}"
            )
            
        except Exception as e:
            logger.error(f"❌ Erro ao buscar ordens do banco (user={user_id}): {e}")
            result.errors.append(f"DB_FETCH_ERROR: {str(e)}")
            return result
        
        # ─────────────────────────────────────────────────────────────────
        # [2/4] Conectar à KuCoin e buscar ordens reais
        # ─────────────────────────────────────────────────────────────────
        
        try:
            creds = await self._creds_repo.get_credentials(user_id, ExchangeType.KUCOIN)
            
            if not creds:
                logger.warning(f"⚠️ Credenciais não encontradas para user={user_id}")
                result.errors.append("NO_CREDENTIALS")
                return result
            
            client = KuCoinRawClient(
                api_key=creds["api_key"],
                api_secret=creds["api_secret"],
                passphrase=creds.get("api_passphrase", "")
            )
            
            # Buscar ordens ativas da KuCoin
            real_orders = await client.get_orders(
                status="active",  # Apenas ordens não preenchidas
                limit=500
            )
            
            logger.debug(
                f"📡 Buscadas {len(real_orders)} ordens ativas da KuCoin "
                f"(user={user_id})"
            )
            
        except KuCoinAPIError as e:
            logger.error(f"❌ Erro KuCoin API (user={user_id}): {e}")
            result.errors.append(f"KUCOIN_API_ERROR: {str(e)}")
            return result
        except Exception as e:
            logger.error(f"❌ Erro ao conectar KuCoin (user={user_id}): {e}")
            result.errors.append(f"CONNECTION_ERROR: {str(e)}")
            return result
        
        # ─────────────────────────────────────────────────────────────────
        # [3/4] Comparar e sincronizar
        # ─────────────────────────────────────────────────────────────────
        
        for db_order in pending_orders_db:
            client_oid = db_order.get("client_oid")
            
            if not client_oid:
                logger.warning(
                    f"⚠️ Ordem sem client_oid no banco (ordem_id={db_order.get('_id')})"
                )
                result.errors.append(f"NO_CLIENT_OID: {db_order.get('_id')}")
                continue
            
            # Procurar ordem na KuCoin pelo client_oid
            real_order = await self._find_order_by_client_oid(real_orders, client_oid)
            
            if not real_order:
                # ❌ Ordem não encontrada em KuCoin
                logger.warning(
                    f"⚠️  Ordem não encontrada em KuCoin! "
                    f"(client_oid={client_oid} | order_id={db_order.get('_id')})"
                )
                result.orders_missing += 1
                
                # Registrar em audit log
                await self._log_divergence(
                    db_order=db_order,
                    divergence_type="MISSING_IN_EXCHANGE",
                    exchange_order=None
                )
                
                continue
            
            # ✅ Ordem encontrada, verificar se status divergiu
            db_status = db_order.get("status", "pending")
            exchange_status = real_order.get("status", "").lower()
            
            # Normalizar status
            if exchange_status == "filled" and db_status != "filled":
                # Ordem foi preenchida na exchange, sincronizar no banco
                logger.info(
                    f"✅ Sincronizando ordem FILLED: "
                    f"client_oid={client_oid}"
                )
                
                try:
                    await self._sync_filled_order(
                        db_order=db_order,
                        exchange_order=real_order,
                        db=db
                    )
                    result.orders_synced += 1
                    
                except Exception as e:
                    logger.error(
                        f"❌ Erro ao sincronizar ordem (client_oid={client_oid}): {e}"
                    )
                    result.errors.append(f"SYNC_ERROR: {str(e)}")
            
            elif exchange_status == "canceled" and db_status != "canceled":
                # Ordem foi cancelada na exchange, atualizar banco
                logger.info(
                    f"🛑 Ordem foi cancelada na exchange: "
                    f"client_oid={client_oid}"
                )
                
                try:
                    await db["trading_orders"].update_one(
                        {"_id": db_order["_id"]},
                        {
                            "$set": {
                                "status": "canceled",
                                "canceled_at": datetime.utcnow(),
                                "reconciled_at": datetime.utcnow()
                            }
                        }
                    )
                    result.orders_diverged += 1
                    
                except Exception as e:
                    logger.error(
                        f"❌ Erro ao atualizar ordem cancelada (client_oid={client_oid}): {e}"
                    )
                    result.errors.append(f"UPDATE_ERROR: {str(e)}")
        
        return result
    
    async def _find_order_by_client_oid(
        self,
        exchange_orders: List[Dict[str, Any]],
        client_oid: str
    ) -> Optional[Dict[str, Any]]:
        """
        Procura ordem na lista retornada pela KuCoin pelo client_oid.
        
        Args:
            exchange_orders: Lista de ordens da KuCoin
            client_oid: client_oid a procurar
            
        Returns:
            Dicionário da ordem ou None
        """
        for order in exchange_orders:
            if order.get("clientOid") == client_oid or order.get("client_oid") == client_oid:
                return order
        return None
    
    async def _sync_filled_order(
        self,
        db_order: Dict[str, Any],
        exchange_order: Dict[str, Any],
        db: AsyncIOMotorDatabase
    ) -> None:
        """
        Sincroniza ordem preenchida da KuCoin para o banco.
        
        Args:
            db_order: Ordem no banco
            exchange_order: Ordem na KuCoin
            db: Instância do banco
        """
        filled_price = Decimal(str(exchange_order.get("averagePrice", 0)))
        filled_quantity = Decimal(str(exchange_order.get("filledSize", 0)))
        
        # Calcular valor total preenchido
        filled_value = filled_price * filled_quantity if filled_price > 0 else Decimal("0")
        
        await db["trading_orders"].update_one(
            {"_id": db_order["_id"]},
            {
                "$set": {
                    "status": "filled",
                    "exchange_order_id": exchange_order.get("id"),
                    "filled_price": filled_price,
                    "filled_quantity": filled_quantity,
                    "filled_value": filled_value,
                    "filled_at": datetime.utcnow(),
                    "reconciled_at": datetime.utcnow(),
                }
            }
        )
        
        logger.debug(
            f"✅ Ordem atualizada no banco: "
            f"qty={filled_quantity} @ ${filled_price}"
        )
    
    async def _log_divergence(
        self,
        db_order: Dict[str, Any],
        divergence_type: str,
        exchange_order: Optional[Dict[str, Any]]
    ) -> None:
        """
        Registra divergência em audit log.
        
        Args:
            db_order: Ordem no banco
            divergence_type: Tipo de divergência (ex: "MISSING_IN_EXCHANGE")
            exchange_order: Ordem na exchange (se houver)
        """
        db = get_db()
        
        audit_entry = {
            "timestamp": datetime.utcnow(),
            "type": "ORDER_DIVERGENCE",
            "divergence_type": divergence_type,
            "user_id": db_order.get("user_id"),
            "order_id": db_order.get("_id"),
            "client_oid": db_order.get("client_oid"),
            "db_status": db_order.get("status"),
            "exchange_status": exchange_order.get("status") if exchange_order else None,
            "details": {
                "db_order": {
                    "id": str(db_order.get("_id")),
                    "status": db_order.get("status"),
                    "created_at": db_order.get("created_at")
                },
                "exchange_order": {
                    "id": exchange_order.get("id") if exchange_order else None,
                    "status": exchange_order.get("status") if exchange_order else None
                }
            }
        }
        
        try:
            await db["audit_divergences"].insert_one(audit_entry)
        except Exception as e:
            logger.error(f"❌ Erro ao registrar divergência em audit: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# Inicialização e gerenciamento do worker
# ─────────────────────────────────────────────────────────────────────────────

_worker_instance: Optional[OrderReconciliationWorker] = None
_worker_task: Optional[asyncio.Task] = None


async def start_reconciliation_worker(interval_seconds: int = 60) -> None:
    """
    Inicia o worker de reconciliação como background task.
    
    Chamar em main.py:
    ```python
    @app.on_event("startup")
    async def startup():
        await start_reconciliation_worker()
    ```
    
    Args:
        interval_seconds: Intervalo entre reconciliações
    """
    global _worker_instance, _worker_task
    
    if _worker_task and not _worker_task.done():
        logger.warning("⚠️ OrderReconciliationWorker já está rodando")
        return
    
    _worker_instance = OrderReconciliationWorker(interval_seconds=interval_seconds)
    _worker_task = asyncio.create_task(_worker_instance.start())
    
    logger.info("✅ OrderReconciliationWorker iniciado como background task")


async def stop_reconciliation_worker() -> None:
    """
    Para o worker gracefully.
    
    Chamar em main.py:
    ```python
    @app.on_event("shutdown")
    async def shutdown():
        await stop_reconciliation_worker()
    ```
    """
    global _worker_instance, _worker_task
    
    if _worker_instance:
        _worker_instance.stop()
    
    if _worker_task:
        try:
            await asyncio.wait_for(_worker_task, timeout=5.0)
        except asyncio.TimeoutError:
            logger.warning("⚠️ Timeout ao esperar worker parar")
            _worker_task.cancel()
    
    logger.info("✅ OrderReconciliationWorker parado")


def get_reconciliation_worker() -> Optional[OrderReconciliationWorker]:
    """Retorna instância global do worker."""
    return _worker_instance
