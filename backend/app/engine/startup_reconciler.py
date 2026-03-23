"""
StartupReconciler -- DOC-K09: Reconciliacao de estado ao iniciar a engine.

Executado UMA VEZ durante o startup do BotOrchestrator, antes de
iniciar qualquer BotWorker.

Responsabilidades:
1. Detectar order_intents no estado "sent" (ordens em transito no crash anterior)
2. Verificar via REST se essas ordens foram preenchidas ou canceladas
3. Atualizar bot_trades de acordo
4. Restaurar posicao nos instances que tem trade aberto
5. Cancelar stop orders nativas orfas
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from bson import ObjectId

logger = logging.getLogger("engine.startup_reconciler")


class StartupReconciler:
    """
    DOC-K09: Pre-flight reconciliation between MongoDB and KuCoin REST.

    Usage (in BotOrchestrator.start, BEFORE _restore_active_bots):
        reconciler = StartupReconciler(db, rest_client_factory)
        report = await reconciler.run()
    """

    def __init__(self, db, rest_client_factory=None, exchange_factory=None):
        """
        Args:
            db: Motor async database.
            rest_client_factory: Optional async callable(user_id: str) -> KuCoinRESTClient.
                                 If None, REST verification is skipped (DB-only mode).
            exchange_factory: Alias for rest_client_factory (backwards compat).
        """
        self._db      = db
        self._factory = rest_client_factory or exchange_factory

    async def run(self) -> dict:
        """
        Executa reconciliacao completa.
        Retorna relatorio com o que foi encontrado e corrigido.
        """
        logger.info("[DOC-K09] Iniciando reconciliacao de startup...")

        report = {
            "instances_checked": 0,
            "intents_reconciled": 0,
            "positions_restored": 0,
            "orphan_orders_cancelled": 0,
            "errors": [],
        }

        # Buscar todas as instancias que estavam em execucao antes do crash/restart
        cursor = self._db["user_bot_instances"].find(
            {"status": {"$in": ["running", "paused", "stopped"]}}
        )
        instances = await cursor.to_list(length=500)
        report["instances_checked"] = len(instances)

        for instance in instances:
            try:
                await self._reconcile_instance(instance, report)
            except Exception as exc:
                err = f"Erro reconciliando instance {instance.get('_id')}: {exc}"
                logger.error(err)
                report["errors"].append(err)

        logger.info(
            "[DOC-K09] Reconciliacao concluida: "
            "instances=%d intents=%d positions=%d orphans=%d errors=%d",
            report["instances_checked"],
            report["intents_reconciled"],
            report["positions_restored"],
            report["orphan_orders_cancelled"],
            len(report["errors"]),
        )
        return report

    # -- Instance Reconciliation -----------------------------------------------

    async def _reconcile_instance(self, instance: dict, report: dict) -> None:
        """Reconcilia UMA instancia de bot."""
        instance_id = str(instance["_id"])
        user_id     = instance.get("user_id", "")

        # 1. Verificar se existe trade aberto no banco local
        open_trade = await self._db["bot_trades"].find_one({
            "bot_instance_id": instance_id,
            "status": "open",
        })

        # 2. Verificar order_intents pendentes (write-ahead log)
        pending_intents = await self._db["order_intents"].find({
            "bot_instance_id": instance_id,
            "state": {"$in": ["pending", "sent"]},
        }).to_list(length=10)

        if not open_trade and not pending_intents:
            return  # Instancia sem estado pendente -- OK

        if not self._factory:
            logger.warning(
                "[DOC-K09] Sem rest_client_factory -- reconciliacao de exchange pulada "
                "para instance=%s (trade_aberto=%s, intents=%d)",
                instance_id, open_trade is not None, len(pending_intents),
            )
            return

        # 3. Criar REST client para este usuario
        try:
            rest_client = await self._factory(user_id)
        except Exception as exc:
            logger.warning(
                "[DOC-K09] Nao foi possivel criar REST client para user %s: %s",
                user_id, exc,
            )
            return

        try:
            # 4. Reconciliar order_intents pendentes
            for intent in pending_intents:
                await self._reconcile_intent(intent, rest_client, report)

            # 5. Verificar se trade aberto no banco ainda e real na exchange
            if open_trade:
                await self._reconcile_open_trade(open_trade, instance_id, rest_client, report)

        finally:
            try:
                await rest_client.close()
            except Exception:
                pass

    async def _reconcile_open_trade(
        self,
        open_trade: dict,
        instance_id: str,
        rest_client,
        report: dict,
    ) -> None:
        """Verifica se um trade registrado como open ainda existe na exchange."""
        exchange_order_id = open_trade.get("exchange_order_id", "")
        trade_id          = open_trade["_id"]

        if not exchange_order_id:
            logger.warning(
                "[DOC-K09] Trade %s sem exchange_order_id -- nao pode verificar na exchange",
                trade_id,
            )
            return

        try:
            order_data = await rest_client.get_order(exchange_order_id)
            deal_size  = float(order_data.get("dealSize") or 0)

            if deal_size > 0:
                # Ordem preenchida -- posicao esta realmente aberta
                logger.info(
                    "[DOC-K09] Trade aberto restaurado: instance=%s orderId=%s qty=%.6f",
                    instance_id, exchange_order_id, deal_size,
                )
                report["positions_restored"] += 1

                # Cancelar stop orders nativas orfas (SL/TP)
                await self._cancel_orphan_stop_orders(open_trade, rest_client, report)

            else:
                # Ordem nao foi preenchida ou foi cancelada -- limpar trade local
                await self._db["bot_trades"].update_one(
                    {"_id": trade_id},
                    {"$set": {
                        "status": "cancelled",
                        "exit_reason": "unfilled_on_restart",
                        "exit_timestamp": datetime.now(timezone.utc),
                    }},
                )
                logger.warning(
                    "[DOC-K09] Trade local limpo (nao preenchido na exchange): "
                    "instance=%s orderId=%s",
                    instance_id, exchange_order_id,
                )

        except Exception as exc:
            logger.warning(
                "[DOC-K09] Nao foi possivel verificar ordem %s: %s",
                exchange_order_id, exc,
            )

    async def _cancel_orphan_stop_orders(
        self,
        open_trade: dict,
        rest_client,
        report: dict,
    ) -> None:
        """
        Cancela stop orders nativas (SL/TP) orfas na exchange
        apos um restart, caso tenham sido deixadas abertas durante o crash.
        """
        native_sl_id = open_trade.get("native_sl_order_id")
        native_tp_id = open_trade.get("native_tp_order_id")
        pair         = open_trade.get("pair", "")

        if not pair or (not native_sl_id and not native_tp_id):
            return

        try:
            open_stop_orders = await rest_client.get_open_stop_orders(pair)
            open_stop_ids = {o.get("id") for o in open_stop_orders}

            for label, order_id in (("SL", native_sl_id), ("TP", native_tp_id)):
                if order_id and order_id in open_stop_ids:
                    try:
                        await rest_client.cancel_stop_order(order_id)
                        logger.info(
                            "[DOC-K09] Stop order orfa cancelada: %s=%s pair=%s",
                            label, order_id, pair,
                        )
                        report["orphan_orders_cancelled"] += 1
                    except Exception as exc:
                        logger.warning(
                            "[DOC-K09] Falha ao cancelar stop order orfa %s=%s: %s",
                            label, order_id, exc,
                        )
        except Exception as exc:
            logger.warning("[DOC-K09] Erro ao buscar stop orders abertas em %s: %s", pair, exc)

    # -- Intent Reconciliation -------------------------------------------------

    async def _reconcile_intent(self, intent: dict, rest_client, report: dict) -> None:
        """
        Reconcilia um order_intent pendente verificando seu estado na exchange.

        Estado "pending": ordem nunca enviada (crash antes do envio).
        Estado "sent":    ordem enviada -- verificar se foi preenchida ou nao.
        """
        client_oid        = intent.get("client_oid", "")
        exchange_order_id = intent.get("exchange_order_id")

        if not exchange_order_id:
            # Intent "pending" -- ordem nunca chegou a exchange
            await self._db["order_intents"].update_one(
                {"client_oid": client_oid},
                {"$set": {
                    "state": "error",
                    "error": "never_sent_crash_before_send",
                    "resolved_at": datetime.now(timezone.utc),
                }},
            )
            logger.info(
                "[DOC-K09] Intent %s: NUNCA ENVIADA -> marcada como erro",
                client_oid[:8] if client_oid else "?",
            )
            report["intents_reconciled"] += 1
            return

        # Intent "sent" -- verificar na exchange
        try:
            order_data = await rest_client.get_order(exchange_order_id)
            deal_size  = float(order_data.get("dealSize") or 0)

            if deal_size > 0:
                await self._db["order_intents"].update_one(
                    {"client_oid": client_oid},
                    {"$set": {
                        "state": "filled",
                        "resolved_at": datetime.now(timezone.utc),
                    }},
                )
                logger.info(
                    "[DOC-K09] Intent %s: FILLED (reconciliado, orderId=%s)",
                    client_oid[:8], exchange_order_id,
                )
            else:
                await self._db["order_intents"].update_one(
                    {"client_oid": client_oid},
                    {"$set": {
                        "state": "error",
                        "error": "not_filled_on_restart",
                        "resolved_at": datetime.now(timezone.utc),
                    }},
                )
                logger.warning(
                    "[DOC-K09] Intent %s: NAO PREENCHIDA -- limpa no restart (orderId=%s)",
                    client_oid[:8], exchange_order_id,
                )

            report["intents_reconciled"] += 1

        except Exception as exc:
            logger.error(
                "[DOC-K09] Erro ao reconciliar intent %s (orderId=%s): %s",
                client_oid[:8] if client_oid else "?", exchange_order_id, exc,
            )