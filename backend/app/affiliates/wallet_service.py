"""
Serviço de gerenciamento de wallet de afiliados.
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, Tuple, List
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.affiliates.models import (
    AffiliateWallet,
    AffiliateTransaction,
    WithdrawRequest,
    TransactionType,
    TransactionStatus,
    WithdrawalStatus,
    COMMISSION_HOLD_DAYS,
    MINIMUM_WITHDRAWAL_AMOUNT,
    COMMISSION_RATE,
    COMMISSION_TIERS,
)

logger = logging.getLogger(__name__)


class AffiliateWalletService:
    """Serviço de gerenciamento de wallet de afiliados"""

    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.wallet_col = db["affiliate_wallets"]
        self.transaction_col = db["affiliate_transactions"]
        self.withdraw_col = db["affiliate_withdraw_requests"]

    async def get_or_create_wallet(self, user_id: str) -> AffiliateWallet:
        """Busca ou cria wallet para um afiliado."""
        logger.info(f"🏦 Buscando wallet para usuário {user_id}")

        wallet_data = await self.wallet_col.find_one({"user_id": user_id})

        if wallet_data:
            logger.info(f"✅ Wallet encontrado para {user_id}")
            return AffiliateWallet(**wallet_data)

        logger.info(f"📝 Criando novo wallet para {user_id}")
        wallet = AffiliateWallet(user_id=user_id)
        result = await self.wallet_col.insert_one(wallet.dict())
        wallet.id = str(result.inserted_id)

        logger.info(f"✅ Novo wallet criado: {wallet.id}")
        return wallet

    async def save_wallet(self, wallet: AffiliateWallet) -> None:
        """Salva ou atualiza wallet no banco."""
        wallet.updated_at = datetime.utcnow()
        await self.wallet_col.update_one(
            {"user_id": wallet.user_id},
            {"$set": wallet.dict(exclude={"id"})},
            upsert=True,
        )
        logger.info(
            f"💾 Wallet salvo para {wallet.user_id}: "
            f"pending=${wallet.pending_balance}, available=${wallet.available_balance}"
        )

    async def record_commission(
        self,
        affiliate_user_id: str,
        referral_id: str,
        sale_amount_usd: Decimal,
        commission_rate: Optional[Decimal] = None,
        buyer_ip: Optional[str] = None,
        affiliate_ip: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """Registra uma comissão para um afiliado."""
        logger.info(
            f"🤝 Processando comissão: afiliado={affiliate_user_id}, "
            f"referral={referral_id}, venda=${sale_amount_usd}"
        )

        # Validação anti-self-referral
        if buyer_ip and affiliate_ip and buyer_ip == affiliate_ip:
            logger.warning(
                f"🚫 Auto-referência detectada: buyer_ip={buyer_ip} == affiliate_ip={affiliate_ip}"
            )
            return False, "Auto-referência detectada. Comissão rejeitada."

        if sale_amount_usd <= 0:
            return False, "Valor de venda inválido."

        if commission_rate is None:
            commission_rate = COMMISSION_RATE

        # Calcula comissão com Decimal
        commission_amount = (Decimal(str(sale_amount_usd)) * commission_rate).quantize(Decimal("0.01"))

        release_at = datetime.utcnow() + timedelta(days=COMMISSION_HOLD_DAYS)

        logger.info(f"💰 Comissão: ${sale_amount_usd} × {commission_rate*100}% = ${commission_amount}")

        try:
            wallet = await self.get_or_create_wallet(affiliate_user_id)
            wallet.pending_balance += commission_amount
            wallet.total_earned += commission_amount

            await self.save_wallet(wallet)

            transaction = AffiliateTransaction(
                user_id=affiliate_user_id,
                type=TransactionType.COMMISSION,
                status=TransactionStatus.PENDING,
                amount_usd=commission_amount,
                release_at=release_at,
                referral_id=referral_id,
                sale_amount_usd=sale_amount_usd,
                commission_rate=commission_rate,
                notes=f"Comissão de referral {referral_id} (compra ${sale_amount_usd})",
            )

            result = await self.transaction_col.insert_one(transaction.dict())
            transaction.id = str(result.inserted_id)

            logger.info(
                f"✅ Comissão registrada: ID={transaction.id}, Valor=${commission_amount}, Libera em {release_at}"
            )

            return True, f"Comissão de ${commission_amount} registrada. Disponível em 7 dias."

        except Exception as e:
            logger.error(f"❌ Erro ao registrar comissão: {str(e)}")
            return False, f"Erro ao registrar comissão: {str(e)}"

    async def release_pending_balances(self) -> int:
        """Libera saldos pendentes que atingiram a data de release_at."""
        logger.info("⏰ Iniciando job de liberação de saldos pendentes...")
        now = datetime.utcnow()

        pending_transactions = await self.transaction_col.find(
            {
                "status": TransactionStatus.PENDING,
                "release_at": {"$lte": now},
                "type": TransactionType.COMMISSION,
            }
        ).to_list(None)

        logger.info(f"🔍 Encontradas {len(pending_transactions)} transações para liberar")

        released_count = 0

        for transaction in pending_transactions:
            trans_obj = AffiliateTransaction(**transaction)
            user_id = trans_obj.user_id
            amount = trans_obj.amount_usd

            try:
                await self.wallet_col.update_one(
                    {"user_id": user_id},
                    {
                        "$inc": {
                            "pending_balance": -amount,
                            "available_balance": amount,
                        },
                    },
                )

                await self.transaction_col.update_one(
                    {"_id": transaction["_id"]},
                    {
                        "$set": {
                            "status": TransactionStatus.AVAILABLE,
                            "updated_at": datetime.utcnow(),
                        }
                    },
                )

                released_count += 1
                logger.info(
                    f"✅ Saldo liberado para {user_id}: ${amount} (pending → available)"
                )

            except Exception as e:
                logger.error(
                    f"❌ Erro ao liberar saldo para {user_id} "
                    f"(trans_id={trans_obj.id}): {str(e)}"
                )
                continue

        logger.info(f"🎉 Job de liberação concluído: {released_count} saldos liberados")
        return released_count

    async def request_withdrawal(
        self,
        user_id: str,
        amount_usd: Decimal,
        withdrawal_method,
    ) -> Tuple[bool, str, Optional[WithdrawRequest]]:
        """Processa uma requisição de saque."""
        logger.info(f"💸 Requisição de saque: user={user_id}, amount=${amount_usd}")

        try:
            wallet = await self.get_or_create_wallet(user_id)

            # Validações
            if amount_usd < MINIMUM_WITHDRAWAL_AMOUNT:
                return False, f"Mínimo é ${MINIMUM_WITHDRAWAL_AMOUNT}", None

            if wallet.available_balance < amount_usd:
                return False, f"Saldo insuficiente: ${wallet.available_balance}", None

            # Cria requisição
            withdraw_request = WithdrawRequest(
                user_id=user_id,
                amount_usd=amount_usd,
                withdrawal_method=withdrawal_method,
                status=WithdrawalStatus.PENDING,
            )

            result = await self.withdraw_col.insert_one(withdraw_request.dict())
            withdraw_request.id = str(result.inserted_id)

            # Atualiza wallet (debita do available)
            await self.wallet_col.update_one(
                {"user_id": user_id},
                {
                    "$inc": {
                        "available_balance": -amount_usd,
                        "total_withdrawn": amount_usd,
                    },
                },
            )

            logger.info(f"✅ Saque solicitado: ID={withdraw_request.id}, Valor=${amount_usd}")
            return True, "Saque solicitado com sucesso", withdraw_request

        except Exception as e:
            logger.error(f"❌ Erro ao solicitar saque: {str(e)}")
            return False, f"Erro ao solicitar saque: {str(e)}", None

    async def process_withdrawal(
        self,
        user_id: str,
        amount_usd: float,
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Processa um saque para PIX/Crypto/Banco.
        Cria o WithdrawRequest, debita o saldo disponível.
        Retorna (success, message, withdrawal_id).
        """
        logger.info(f"💸 process_withdrawal: user={user_id}, amount=${amount_usd}")
        try:
            amount_dec = Decimal(str(amount_usd))
            wallet = await self.get_or_create_wallet(user_id)

            if amount_dec < MINIMUM_WITHDRAWAL_AMOUNT:
                return False, f"Mínimo de saque é ${MINIMUM_WITHDRAWAL_AMOUNT}", None

            available = Decimal(str(wallet.available_balance))
            if available < amount_dec:
                return False, f"Saldo insuficiente: disponível ${available:.2f}", None

            if not wallet.withdrawal_method:
                return False, "Método de saque não configurado. Configure sua chave PIX primeiro.", None

            withdraw_request = WithdrawRequest(
                user_id=user_id,
                amount_usd=amount_dec,
                withdrawal_method=wallet.withdrawal_method,
                status=WithdrawalStatus.PENDING,
            )
            result = await self.withdraw_col.insert_one(withdraw_request.dict())
            withdrawal_id = str(result.inserted_id)

            await self.wallet_col.update_one(
                {"user_id": user_id},
                {
                    "$inc": {
                        "available_balance": -amount_dec,
                        "total_withdrawn": amount_dec,
                    },
                    "$set": {"last_withdrawal_at": datetime.utcnow()},
                },
            )

            await self.transaction_col.insert_one(
                AffiliateTransaction(
                    user_id=user_id,
                    type=TransactionType.WITHDRAWAL,
                    status=TransactionStatus.COMPLETED,
                    amount_usd=amount_dec,
                    withdrawal_id=withdrawal_id,
                    notes=f"Saque PIX solicitado — ID {withdrawal_id}",
                ).dict()
            )

            logger.info(f"✅ Saque registrado: ID={withdrawal_id}, valor=${amount_dec}")
            return True, f"Saque de ${amount_dec:.2f} solicitado com sucesso!", withdrawal_id

        except Exception as e:
            logger.error(f"❌ Erro em process_withdrawal: {str(e)}")
            return False, f"Erro ao processar saque: {str(e)}", None

    async def get_wallet_stats(self, user_id: str) -> dict:
        """
        Retorna estatísticas completas da wallet para o endpoint GET /affiliates/wallet.
        """
        wallet = await self.get_or_create_wallet(user_id)

        recent_cursor = self.transaction_col.find(
            {"user_id": user_id}
        ).sort("created_at", -1).limit(5)
        recent_txs = await recent_cursor.to_list(5)

        completed_withdrawals = await self.withdraw_col.count_documents(
            {"user_id": user_id, "status": WithdrawalStatus.COMPLETED}
        )

        recent_transactions = [
            {
                "id": str(tx.get("_id", "")),
                "type": tx.get("type"),
                "status": tx.get("status"),
                "amount_usd": float(tx.get("amount_usd", 0)),
                "created_at": tx.get("created_at"),
                "release_at": tx.get("release_at"),
                "notes": tx.get("notes"),
            }
            for tx in recent_txs
        ]

        return {
            "pending_balance": float(wallet.pending_balance),
            "available_balance": float(wallet.available_balance),
            "total_balance": float(wallet.pending_balance + wallet.available_balance),
            "total_earned": float(wallet.total_earned),
            "total_withdrawn": float(wallet.total_withdrawn),
            "withdrawal_method": wallet.withdrawal_method.dict() if wallet.withdrawal_method else None,
            "is_withdrawal_ready": wallet.is_withdrawal_ready,
            "recent_transactions": recent_transactions,
            "completed_withdrawals_count": completed_withdrawals,
            "last_withdrawal_at": wallet.last_withdrawal_at,
        }

    async def _process_gateway_payout(
        self,
        withdrawal_id: str,
        method_type: str,
        key: str,
        amount_usd: float,
        user_id: str,
    ) -> Tuple[bool, str]:
        """
        Process payout via Asaas payment gateway (PIX).
        Falls back to manual approval if Asaas API key is not configured.
        """
        logger.info(
            f"🔄 _process_gateway_payout: withdrawal={withdrawal_id}, "
            f"method={method_type}, amount=${amount_usd}"
        )
        # Mark as processing
        await self.withdraw_col.update_one(
            {"_id": withdrawal_id},
            {
                "$set": {
                    "status": WithdrawalStatus.PROCESSING,
                    "updated_at": datetime.utcnow(),
                }
            },
        )

        # Attempt Asaas API payout if configured
        from app.core.config import settings
        if settings.asaas_api_key and method_type == "pix":
            try:
                import aiohttp
                base_url = (
                    "https://sandbox.asaas.com/api/v3"
                    if settings.asaas_sandbox
                    else "https://api.asaas.com/api/v3"
                )
                headers = {
                    "access_token": settings.asaas_api_key,
                    "Content-Type": "application/json",
                }

                # Convert USD to BRL (simple estimation; in production use a real rate)
                brl_amount = round(amount_usd * 5.0, 2)  # TODO: use real exchange rate API

                # Create PIX transfer via Asaas
                transfer_payload = {
                    "value": brl_amount,
                    "pixAddressKey": key,
                    "pixAddressKeyType": self._detect_pix_key_type(key),
                    "description": f"Affiliate payout #{withdrawal_id}",
                    "scheduleDate": None,  # Immediate
                }

                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        f"{base_url}/transfers",
                        json=transfer_payload,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=30),
                    ) as resp:
                        resp_data = await resp.json()
                        if resp.status in (200, 201):
                            transfer_id = resp_data.get("id", "")
                            await self.withdraw_col.update_one(
                                {"_id": withdrawal_id},
                                {
                                    "$set": {
                                        "gateway_id": transfer_id,
                                        "gateway": "asaas",
                                        "gateway_status": resp_data.get("status", "PENDING"),
                                        "updated_at": datetime.utcnow(),
                                    }
                                },
                            )
                            logger.info(f"✅ Asaas transfer created: {transfer_id}")
                            return True, f"PIX enviado via Asaas (ID: {transfer_id})"
                        else:
                            error_msg = resp_data.get("errors", [{}])[0].get("description", str(resp_data))
                            logger.error(f"❌ Asaas API error: {error_msg}")
                            await self.withdraw_col.update_one(
                                {"_id": withdrawal_id},
                                {
                                    "$set": {
                                        "gateway_error": error_msg,
                                        "updated_at": datetime.utcnow(),
                                    }
                                },
                            )
                            return False, f"Erro no gateway: {error_msg}"

            except Exception as e:
                logger.error(f"❌ Asaas payout exception: {e}")
                return False, f"Erro ao processar pagamento: {str(e)}"

        # Fallback: manual approval when Asaas is not configured
        logger.info(f"⏳ No gateway configured for {method_type}. Awaiting manual approval.")
        return True, "Saque enviado para processamento manual"

    @staticmethod
    def _detect_pix_key_type(key: str) -> str:
        """Detect the PIX key type based on format."""
        import re
        key = key.strip()
        if re.match(r"^\d{11}$", key):
            return "CPF"
        if re.match(r"^\d{14}$", key):
            return "CNPJ"
        if re.match(r"^[\w.+-]+@[\w-]+\.[\w.]+$", key):
            return "EMAIL"
        if re.match(r"^\+?\d{10,13}$", key):
            return "PHONE"
        return "EVP"  # Random key (UUID format)

