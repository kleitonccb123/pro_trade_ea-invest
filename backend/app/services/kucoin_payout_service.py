"""
KuCoin Payout Service - Integração com API de Transferências Internas

Implementa:
- Autenticação com KuCoin API
- Transferências internas (Internal Transfer) via UID
- Validação de saldo
- Logs de todas as operações
- Tratamento de erros e retry
"""

import logging
import os
from datetime import datetime
from decimal import Decimal
from typing import Optional, Tuple, Dict, Any
from motor.motor_asyncio import AsyncIOMotorDatabase
import aiohttp
import asyncio
import hashlib
import hmac
import time
from base64 import b64encode

logger = logging.getLogger(__name__)


class KuCoinPayoutService:
    """Serviço para processar payouts via KuCoin Internal Transfer"""

    # Configurações KuCoin
    API_BASE_URL = "https://api.kucoin.com"
    API_VERSION = "v1"

    def __init__(
        self,
        db: AsyncIOMotorDatabase,
        api_key: str = None,
        api_secret: str = None,
        passphrase: str = None,
        sandbox_mode: bool = False,
    ):
        """
        Inicializa o serviço KuCoin.

        Args:
            db: Database MongoDB
            api_key: Chave de API da KuCoin (env: KUCOIN_API_KEY)
            api_secret: Secret da API (env: KUCOIN_API_SECRET)
            passphrase: Passphrase da API (env: KUCOIN_PASSPHRASE)
            sandbox_mode: Usar ambiente sandbox (desenvolvimento)
        """
        self.db = db
        self.api_key = api_key or os.getenv("KUCOIN_API_KEY")
        self.api_secret = api_secret or os.getenv("KUCOIN_API_SECRET")
        self.passphrase = passphrase or os.getenv("KUCOIN_PASSPHRASE")

        if not all([self.api_key, self.api_secret, self.passphrase]):
            logger.warning("⚠️  Credenciais KuCoin não configuradas completamente")

        self.sandbox_mode = sandbox_mode
        if self.sandbox_mode:
            self.api_base_url = "https://openapi-sandbox.kucoin.com"
        else:
            self.api_base_url = self.API_BASE_URL

        self.withdraw_col = db["affiliate_withdraw_requests"]
        self.transaction_col = db["affiliate_transactions"]

        logger.info(f"✅ KuCoinPayoutService inicializado (sandbox={self.sandbox_mode})")

    # ==================== AUTENTICAÇÃO ====================

    def _generate_signature(self, path: str, method: str, body: str = "", timestamp: str = None) -> Tuple[str, str, str]:
        """
        Gera assinatura para requisições autenticadas da KuCoin.

        Args:
            path: Caminho da API (ex: /api/v1/accounts)
            method: GET, POST, PUT, DELETE
            body: Body da requisição (string)
            timestamp: Unix timestamp em ms (se None, gera novo)

        Returns:
            (timestamp, sign, passphrase)
        """
        if not timestamp:
            timestamp = str(int(time.time() * 1000))

        # Message = timestamp + method + requestEndpoint + body
        message = timestamp + method + path + body

        logger.debug(f"🔐 Gerando signature para {method} {path}")
        logger.debug(f"   Timestamp: {timestamp}")
        logger.debug(f"   Body: {body}")

        # sign = hmac.sha256(secret, message, base64)
        signature = b64encode(
            hmac.new(
                self.api_secret.encode(),
                message.encode(),
                hashlib.sha256,
            ).digest()
        ).decode()

        # Encode passphrase
        passphrase = b64encode(
            hmac.new(
                self.api_secret.encode(),
                self.passphrase.encode(),
                hashlib.sha256,
            ).digest()
        ).decode()

        return timestamp, signature, passphrase

    def _get_headers(self, path: str, method: str, body: str = "") -> Dict[str, str]:
        """Retorna headers autenticados para requisições KuCoin"""
        timestamp, signature, passphrase = self._generate_signature(path, method, body)

        return {
            "KC-API-SIGN": signature,
            "KC-API-TIMESTAMP": timestamp,
            "KC-API-KEY": self.api_key,
            "KC-API-PASSPHRASE": passphrase,
            "KC-API-KEY-VERSION": "2",
            "Content-Type": "application/json",
        }

    # ==================== VERIFICAÇÃO DE SALDO ====================

    async def check_master_account_balance(self) -> Optional[Decimal]:
        """
        Verifica o saldo de USDT na conta master (Trading Account).

        Returns:
            Saldo em USDT ou None se erro
        """
        logger.info("🔍 Verificando saldo da conta master na KuCoin...")

        try:
            path = f"/api/{self.API_VERSION}/accounts?type=trade"
            headers = self._get_headers(path, "GET")

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.api_base_url}{path}",
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    logger.debug(f"📡 Response Status: {response.status}")

                    if response.status == 200:
                        data = await response.json()
                        logger.debug(f"📡 Response body: {data}")

                        # Procura USDT na trading account
                        for account in data.get("data", []):
                            if account.get("currency") == "USDT":
                                balance = Decimal(str(account.get("available", 0)))
                                logger.info(f"✅ Saldo USDT disponível: {balance}")
                                return balance

                        logger.warning("⚠️  Nenhuma conta USDT encontrada")
                        return Decimal(0)

                    else:
                        error_msg = await response.text()
                        logger.error(f"❌ Erro ao verificar saldo: {response.status} - {error_msg}")
                        return None

        except asyncio.TimeoutError:
            logger.error("❌ Timeout ao verificar saldo")
            return None
        except Exception as e:
            logger.error(f"❌ Erro inesperado ao verificar saldo: {str(e)}", exc_info=True)
            return None

    # ==================== TRANSFERÊNCIAS INTERNAS ====================

    async def process_internal_transfer(
        self,
        destination_uid: str,
        amount_usd: float,
        user_id: str = None,
        withdrawal_id: str = None,
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Realiza uma transferência interna KuCoin para um UID de usuário.

        Args:
            destination_uid: UID do usuário de destino
            amount_usd: Valor em USDT
            user_id: ID do usuário no banco (para logging/auditoria)
            withdrawal_id: ID do saque (para rastreamento)

        Returns:
            (sucesso: bool, mensagem: str, transfer_id: str | None)
        """
        logger.info(
            f"💸 Processando transferência interna: "
            f"UID={destination_uid}, Amount={amount_usd} USDT"
        )

        # ✅ STEP 1: Validar UID
        if not self._validate_uid_format(destination_uid):
            msg = f"UID inválido: {destination_uid}. Deve ser numérico (8-10 dígitos)"
            logger.warning(f"⚠️  {msg}")
            return False, msg, None

        # ✅ STEP 2: Verificar saldo master
        logger.info("📋 Verificando saldo da conta master...")
        master_balance = await self.check_master_account_balance()

        if master_balance is None:
            msg = "Erro ao verificar saldo da conta. Tente novamente."
            logger.error(msg)
            return False, msg, None

        amount_decimal = Decimal(str(amount_usd))

        if master_balance < amount_decimal:
            msg = (
                f"Saldo insuficiente na conta master. "
                f"Disponível: {master_balance} USDT, "
                f"Solicitado: {amount_decimal} USDT"
            )
            logger.warning(f"⚠️  {msg}")
            return False, msg, None

        logger.info(f"✅ Saldo verificado. Master tem {master_balance} USDT")

        # ✅ STEP 3: Realizar Internal Transfer
        try:
            transfer_id = await self._execute_internal_transfer(
                destination_uid, amount_decimal
            )

            if transfer_id:
                # ✅ STEP 4: Registrar em auditoria
                await self._record_transfer_success(
                    user_id, withdrawal_id, destination_uid, amount_usd, transfer_id
                )

                msg = (
                    f"Transferência interna realizada com sucesso! "
                    f"ID: {transfer_id}"
                )
                logger.info(f"✅ {msg}")
                return True, msg, transfer_id

            else:
                msg = "Falha ao processar transferência na KuCoin"
                logger.error(msg)
                return False, msg, None

        except Exception as e:
            msg = f"Erro ao processar transferência: {str(e)}"
            logger.error(f"❌ {msg}", exc_info=True)
            return False, msg, None

    async def _execute_internal_transfer(
        self, destination_uid: str, amount: Decimal
    ) -> Optional[str]:
        """
        Executa a requisição de Internal Transfer na API KuCoin.

        Args:
            destination_uid: UID destino
            amount: Valor em Decimal com 8 casas decimais

        Returns:
            Transfer ID se sucesso, None se falha
        """
        logger.info(f"🚀 Executando Internal Transfer para UID {destination_uid}")

        try:
            # Ajusta precisão para 8 casas decimais (padrão KuCoin)
            amount_str = str(amount.quantize(Decimal("0.00000001")))

            path = f"/api/{self.API_VERSION}/accounts/inner-transfer"

            body_dict = {
                "clientOid": f"CRYPTO_TRADE_HUB_{int(time.time() * 1000)}",
                "currency": "USDT",
                "from": "trade",  # Sacar de trading account
                "to": "main",  # Para main account (antes de enviar para outro UID)
                "amount": amount_str,
            }

            import json
            body = json.dumps(body_dict)

            headers = self._get_headers(path, "POST", body)

            logger.debug(f"📤 Request: POST {path}")
            logger.debug(f"   Body: {body}")
            logger.debug(f"   Headers: {headers}")

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.api_base_url}{path}",
                    headers=headers,
                    data=body,
                    timeout=aiohttp.ClientTimeout(total=15)
                ) as response:
                    response_data = await response.json()

                    logger.debug(f"📥 Response Status: {response.status}")
                    logger.debug(f"   Response: {response_data}")

                    if response.status in [200, 201]:
                        transfer_id = response_data.get("data", {}).get("orderId")

                        if transfer_id:
                            logger.info(f"✅ Internal Transfer criada: {transfer_id}")
                            return transfer_id
                        else:
                            logger.error("❌ Response não contém orderId")
                            return None

                    else:
                        error_code = response_data.get("code", "UNKNOWN")
                        error_msg = response_data.get("msg", "Erro desconhecido")
                        logger.error(
                            f"❌ Erro KuCoin: {response.status} - "
                            f"Code: {error_code}, Message: {error_msg}"
                        )
                        return None

        except asyncio.TimeoutError:
            logger.error("❌ Timeout ao executar Internal Transfer")
            return None
        except Exception as e:
            logger.error(f"❌ Erro ao executar Internal Transfer: {str(e)}", exc_info=True)
            return None

    async def _execute_user_transfer(
        self, destination_uid: str, amount: Decimal
    ) -> Optional[str]:
        """
        Alterna: Transferência direta para o UID do usuário.
        (Requer account-transfer-inner balance)

        Args:
            destination_uid: UID destino
            amount: Valor em USDT

        Returns:
            Transfer ID se sucesso
        """
        logger.info(f"🚀 Executando User Transfer para UID {destination_uid}")

        try:
            path = f"/api/{self.API_VERSION}/accounts/inner-transfer/user"

            amount_str = str(amount.quantize(Decimal("0.00000001")))

            body_dict = {
                "clientOid": f"CRYPTO_TRADE_HUB_{int(time.time() * 1000)}",
                "currency": "USDT",
                "to": destination_uid,
                "amount": amount_str,
            }

            import json
            body = json.dumps(body_dict)

            headers = self._get_headers(path, "POST", body)

            logger.debug(f"📤 Request: POST {path}")
            logger.debug(f"   Body: {body}")

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.api_base_url}{path}",
                    headers=headers,
                    data=body,
                    timeout=aiohttp.ClientTimeout(total=15)
                ) as response:
                    response_data = await response.json()

                    if response.status in [200, 201]:
                        transfer_id = response_data.get("data", {}).get("orderId")
                        if transfer_id:
                            logger.info(f"✅ User Transfer criada: {transfer_id}")
                            return transfer_id

                    logger.error(f"❌ Erro User Transfer: {response_data}")
                    return None

        except Exception as e:
            logger.error(f"❌ Erro ao executar User Transfer: {str(e)}", exc_info=True)
            return None

    # ==================== VALIDAÇÕES ====================

    def _validate_uid_format(self, uid: str) -> bool:
        """
        Valida formato do UID da KuCoin.
        UIDs são geralmente 8-10 dígitos numéricos.
        """
        if not uid:
            return False

        # Remove espaços
        uid = uid.strip()

        # Deve ser numérico
        if not uid.isdigit():
            logger.warning(f"UID contém caracteres não-numéricos: {uid}")
            return False

        # Deve ter entre 8 e 10 dígitos
        if len(uid) < 8 or len(uid) > 10:
            logger.warning(f"UID tem comprimento inválido: {len(uid)} (esperado 8-10)")
            return False

        return True

    # ==================== AUDITORIA ====================

    async def _record_transfer_success(
        self,
        user_id: str,
        withdrawal_id: str,
        destination_uid: str,
        amount: float,
        transfer_id: str,
    ):
        """Registra transferência bem-sucedida para auditoria"""
        try:
            # Atualiza withdrawrequest
            await self.withdraw_col.update_one(
                {"_id": withdrawal_id} if withdrawal_id else {"user_id": user_id},
                {
                    "$set": {
                        "status": "completed",
                        "transaction_id": transfer_id,
                        "kucoin_transfer_id": transfer_id,
                        "destination_uid": destination_uid,
                        "processed_at": datetime.utcnow(),
                        "gateway_response": {
                            "provider": "KuCoin",
                            "method": "Internal Transfer",
                            "transfer_id": transfer_id,
                            "amount": amount,
                        },
                    }
                },
            )

            logger.info(f"✅ WithdrawRequest atualizado: {withdrawal_id}")

        except Exception as e:
            logger.error(f"❌ Erro ao registrar sucesso: {str(e)}", exc_info=True)

    async def get_transfer_status(self, transfer_id: str) -> Optional[str]:
        """
        Verifica o status de uma transferência interna.

        Returns:
            Status: "PENDING", "SUCCESS", "FAILED", ou None
        """
        logger.info(f"🔍 Verificando status da transferência: {transfer_id}")

        try:
            path = f"/api/{self.API_VERSION}/accounts/inner-transfer/{transfer_id}"
            headers = self._get_headers(path, "GET")

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.api_base_url}{path}",
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        status = data.get("data", {}).get("status")
                        logger.info(f"✅ Status: {status}")
                        return status
                    else:
                        logger.error(f"❌ Erro ao verificar status: {response.status}")
                        return None

        except Exception as e:
            logger.error(f"❌ Erro: {str(e)}", exc_info=True)
            return None
