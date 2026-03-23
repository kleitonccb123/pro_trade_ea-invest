"""
Scheduler jobs para sistema de afiliados

Executa tarefas agendadas:
- Liberação de saldos pendentes (a cada 1 hora)
- Processamento de saques falhados (retry logic)
"""

import logging
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)


def create_affiliate_scheduler(wallet_service) -> AsyncIOScheduler:
    """
    Cria e configura o scheduler para jobs do sistema de afiliados.

    Args:
        wallet_service: Instância de AffiliateWalletService

    Returns:
        AsyncIOScheduler configurado
    """
    scheduler = AsyncIOScheduler()

    # Job 1: Liberar saldos pendentes a cada 1 hora
    scheduler.add_job(
        func=release_pending_balances_job,
        trigger=IntervalTrigger(hours=1),
        args=[wallet_service],
        id="release_pending_balances",
        name="Release Pending Affiliate Balances",
        replace_existing=True,
        max_instances=1,
    )

    # Job 2: Retry de saques falhados a cada 6 horas
    scheduler.add_job(
        func=retry_failed_withdrawals_job,
        trigger=IntervalTrigger(hours=6),
        args=[wallet_service],
        id="retry_failed_withdrawals",
        name="Retry Failed Affiliate Withdrawals",
        replace_existing=True,
        max_instances=1,
    )

    return scheduler


async def release_pending_balances_job(wallet_service):
    """
    Job que libera saldos pendentes quando atingem a data de release_at.
    Executado a cada 1 hora.
    """
    logger.info("=" * 60)
    logger.info("AFFILIATE JOB: Iniciando verificacao de liberacao de saldos")
    logger.info("=" * 60)

    try:
        released_count = await wallet_service.release_pending_balances()
        logger.info(f"JOB COMPLETO: {released_count} saldos foram liberados")

    except Exception as e:
        logger.error(f"ERRO NO JOB: {str(e)}", exc_info=True)


async def retry_failed_withdrawals_job(wallet_service):
    """
    Job que tenta reprocessar saques que falharam.
    Executado a cada 6 horas com limite de 3 tentativas.
    """
    logger.info("=" * 60)
    logger.info("AFFILIATE JOB: Iniciando retry de saques falhados")
    logger.info("=" * 60)

    try:
        db = wallet_service.db
        withdraw_col = db["affiliate_withdraw_requests"]

        # Busca saques falhados com menos de 3 tentativas
        failed_withdrawals = await withdraw_col.find(
            {
                "status": "failed",
                "retry_count": {"$lt": 3},
            }
        ).to_list(None)

        logger.info(f"Encontrados {len(failed_withdrawals)} saques para retry")

        retried_count = 0
        for withdrawal in failed_withdrawals:
            try:
                # Incrementa retry_count
                new_retry_count = (withdrawal.get("retry_count", 0) or 0) + 1

                # Tenta reprocessar via gateway
                success, message, txn_id = await wallet_service._process_gateway_payout(
                    withdrawal_data={
                        "user_id": withdrawal["user_id"],
                        "amount_usd": withdrawal["amount_usd"],
                        "withdrawal_method": withdrawal["withdrawal_method"],
                    }
                )

                if success:
                    # Atualiza para COMPLETED
                    await withdraw_col.update_one(
                        {"_id": withdrawal["_id"]},
                        {
                            "$set": {
                                "status": "completed",
                                "transaction_id": txn_id,
                                "processed_at": datetime.utcnow(),
                                "retry_count": new_retry_count,
                            }
                        },
                    )

                    logger.info(
                        f"Retry bem-sucedido para {withdrawal['user_id']}: "
                        f"${withdrawal['amount_usd']}"
                    )
                    retried_count += 1

                else:
                    # Apenas incrementa retry count
                    await withdraw_col.update_one(
                        {"_id": withdrawal["_id"]},
                        {
                            "$set": {
                                "retry_count": new_retry_count,
                                "last_retry_at": datetime.utcnow(),
                            }
                        },
                    )

                    logger.warning(
                        f"Retry falhou novamente (tentativa {new_retry_count}): "
                        f"{withdrawal['user_id']} - {message}"
                    )

            except Exception as e:
                logger.error(
                    f"Erro ao fazer retry para {withdrawal['user_id']}: {str(e)}",
                    exc_info=True,
                )
                continue

        logger.info(
            f"JOB COMPLETO: {retried_count} saques reprocessados com sucesso"
        )

    except Exception as e:
        logger.error(f"ERRO NO JOB: {str(e)}", exc_info=True)
