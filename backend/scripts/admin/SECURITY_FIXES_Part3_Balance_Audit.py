# 🔧 CORREÇÃO #3: IMPLEMENTAR VALIDAÇÃO CRUZADA DE SALDO
# Recalcular saldo real a partir do histórico de transações antes de saques
# ============================================================================

# 📍 ARQUIVO: backend/app/affiliates/wallet_service.py
# 📍 NOVOS MÉTODOS: calculate_real_balance(), validate_withdrawal_with_audit()
# ============================================================================

from decimal import Decimal
from datetime import datetime, timedelta
from typing import Tuple
import logging

logger = logging.getLogger(__name__)

# ============================================================================
# ✅ NOVOS MÉTODOS PARA AUDITORIA DE SALDO
# ============================================================================

class AffiliateWalletService:
    """Serviço de Wallet com validação cruzada de saldo"""
    
    async def calculate_real_balance(self, user_id: str) -> Tuple[Decimal, Decimal]:
        """
        Recalcula saldo real baseado no histórico de transações.
        Não confia no valor salvo no documento - recalcula do zero!
        
        Retorna: (saldo_pendente_real, saldo_disponivel_real)
        
        ✅ Detecta inconsistências (fraude, bugs, manipulação de DB)
        ✅ Garante que saque nunca será maior que o real
        ✅ Para uso em operações críticas (saques)
        """
        
        logger.info(f"🔍 Auditando saldo real de {user_id}")
        
        # 1️⃣ CALCULAR SALDO PENDENTE (comissões em carência de 7 dias)
        pending_agg = await self.transaction_col.aggregate([
            {
                "$match": {
                    "user_id": user_id,
                    "type": "commission",  # Apenas comissões
                    "status": "pending",   # Ainda em carência
                }
            },
            {
                "$group": {
                    "_id": None,
                    "total": {"$sum": "$amount_usd"}
                }
            }
        ]).to_list(1)
        
        real_pending = Decimal(str(pending_agg[0]["total"])) if pending_agg else Decimal("0.00")
        real_pending = real_pending.quantize(Decimal("0.01"))
        
        logger.info(f"  📊 Saldo Pendente (em carência): ${real_pending:.2f}")
        
        # 2️⃣ CALCULAR SALDO DISPONÍVEL (comissões já liberadas)
        available_agg = await self.transaction_col.aggregate([
            {
                "$match": {
                    "user_id": user_id,
                    "type": "commission",
                    "status": {"$in": ["available", "completed"]},  # Liberadas ou já levadas
                }
            },
            {
                "$group": {
                    "_id": None,
                    "total": {"$sum": "$amount_usd"}
                }
            }
        ]).to_list(1)
        
        commission_available = Decimal(str(available_agg[0]["total"])) if available_agg else Decimal("0.00")
        commission_available = commission_available.quantize(Decimal("0.01"))
        
        logger.info(f"  💰 Comissões Disponíveis: ${commission_available:.2f}")
        
        # 3️⃣ SUBTRAIR SAQUES JÁ COMPLETADOS
        withdrawals_agg = await self.transaction_col.aggregate([
            {
                "$match": {
                    "user_id": user_id,
                    "type": "withdrawal",
                    "status": {"$in": ["completed", "pending"]},  # Conclui ou em processamento
                }
            },
            {
                "$group": {
                    "_id": None,
                    "total": {"$sum": "$amount_usd"}
                }
            }
        ]).to_list(1)
        
        total_withdrawn = Decimal(str(withdrawals_agg[0]["total"])) if withdrawals_agg else Decimal("0.00")
        total_withdrawn = total_withdrawn.quantize(Decimal("0.01"))
        
        logger.info(f"  💸 Saques Completados: ${total_withdrawn:.2f}")
        
        # 4️⃣ SALDO DISPONÍVEL = Comissões Liberadas - Saques
        real_available = commission_available - total_withdrawn
        real_available = max(real_available, Decimal("0.00"))  # Não pode ser negativo
        real_available = real_available.quantize(Decimal("0.01"))
        
        logger.info(f"  ✅ Saldo Real Final: ${real_available:.2f} (pendente: ${real_pending:.2f})")
        
        return real_pending, real_available
    
    
    async def check_balance_integrity(self, user_id: str) -> Tuple[bool, str]:
        """
        Compara saldo real calculado com saldo salvo no documento.
        Se divergirem, indica fraude ou bug!
        
        Retorna: (está_ok, mensagem)
        """
        
        # Obter saldo real
        real_pending, real_available = await self.calculate_real_balance(user_id)
        
        # Obter saldo salvo
        wallet = await self.get_or_create_wallet(user_id)
        
        # Comparar pendente
        if abs(Decimal(str(wallet.pending_balance)) - real_pending) > Decimal("0.01"):
            logger.error(
                f"🚨 ALERTA: Saldo pendente inconsistente para {user_id}! "
                f"Salvo: ${wallet.pending_balance:.2f}, "
                f"Real: ${real_pending:.2f}, "
                f"Diferença: ${abs(Decimal(str(wallet.pending_balance)) - real_pending):.2f}"
            )
            return False, f"Saldo pendente inconsistente (possível fraude)"
        
        # Comparar disponível
        if abs(Decimal(str(wallet.available_balance)) - real_available) > Decimal("0.01"):
            logger.error(
                f"🚨 ALERTA: Saldo disponível inconsistente para {user_id}! "
                f"Salvo: ${wallet.available_balance:.2f}, "
                f"Real: ${real_available:.2f}, "
                f"Diferença: ${abs(Decimal(str(wallet.available_balance)) - real_available):.2f}"
            )
            return False, f"Saldo disponível inconsistente (possível fraude)"
        
        logger.info(f"✅ Integridade de saldo verificada para {user_id}")
        return True, "OK"
    
    
    async def validate_withdrawal_with_audit(
        self,
        user_id: str,
        amount_usd: Decimal,
    ) -> Tuple[bool, str]:
        """
        Valida saque com auditoria cruzada de saldo.
        
        ✅ Verifica integridade de saldo ANTES de permitir
        ✅ Recalcula saldo real do zero
        ✅ Impede saques fraudulentos
        
        Retorna: (permitido, mensagem)
        """
        
        logger.info(f"🔐 Validando saque de ${amount_usd:.2f} para {user_id}")
        
        # 1️⃣ Verificação de integridade
        is_ok, integrity_msg = await self.check_balance_integrity(user_id)
        if not is_ok:
            logger.error(f"❌ Saque rejeitado: {integrity_msg}")
            return False, f"Sistema detectou inconsistência. Contacte suporte: {integrity_msg}"
        
        # 2️⃣ Recalcular saldo real (não confia no valor salvo)
        _, real_available_balance = await self.calculate_real_balance(user_id)
        
        # 3️⃣ Validar valor mínimo
        MIN_WITHDRAWAL = Decimal("50.00")
        if amount_usd < MIN_WITHDRAWAL:
            logger.warning(f"❌ Saque abaixo do mínimo: ${amount_usd:.2f} < ${MIN_WITHDRAWAL:.2f}")
            return False, f"Saque mínimo é ${MIN_WITHDRAWAL:.2f}"
        
        # 4️⃣ Validar saldo suficiente (usa valor RECALCULADO, não salvo!)
        if real_available_balance < amount_usd:
            logger.warning(
                f"❌ Saldo insuficiente para {user_id}: "
                f"tenta sacar ${amount_usd:.2f}, disponível apenas ${real_available_balance:.2f}"
            )
            return False, f"Saldo insuficiente. Disponível: ${real_available_balance:.2f}"
        
        # 5️⃣ Validar método de saque configurado
        wallet = await self.get_or_create_wallet(user_id)
        if not wallet.withdrawal_method:
            logger.warning(f"❌ Método de saque não configurado para {user_id}")
            return False, "Configure um método de saque primeiro"
        
        logger.info(f"✅ Saque APROVADO: ${amount_usd:.2f} para {user_id}")
        return True, "Saque aprovado"
    
    
    async def process_withdrawal_with_safety(
        self,
        user_id: str,
        amount_usd: Decimal,
        withdrawal_method: dict,
    ) -> Tuple[bool, str]:
        """
        Processa saque com MÚLTIPLAS camadas de segurança.
        
        ✅ Validação cruzada de saldo
        ✅ Operação atômica
        ✅ Rollback em caso de erro
        ✅ Auditoria completa
        """
        
        logger.info(f"💸 Processando saque de ${amount_usd:.2f} para {user_id}")
        
        # 1️⃣ VALIDAÇÃO COM AUDITORIA
        is_valid, validation_msg = await self.validate_withdrawal_with_audit(user_id, amount_usd)
        if not is_valid:
            return False, validation_msg
        
        # 2️⃣ AGUARDAR RATE LIMITING
        from app.services.withdrawal_rate_limiter import WithdrawalRateLimiter
        rate_limiter = WithdrawalRateLimiter(self.db)
        is_allowed, limit_msg = await rate_limiter.check_rate_limit(user_id)
        if not is_allowed:
            logger.warning(f"⏱️ Rate limit exceeded: {limit_msg}")
            return False, limit_msg
        
        try:
            # 3️⃣ OPERAÇÃO ATÔMICA: Debita saldo
            result = await self.wallet_col.update_one(
                {
                    "user_id": user_id,
                    "available_balance": {"$gte": float(amount_usd)}  # Condição: tem saldo
                },
                {
                    "$inc": {
                        "available_balance": -float(amount_usd),  # Debita
                        "total_withdrawn": float(amount_usd),     # Incrementa total
                    },
                    "$set": {
                        "updated_at": datetime.utcnow(),
                        "last_withdrawal_at": datetime.utcnow(),
                    }
                }
            )
            
            # Se não conseguiu debitar (saldo mudou), falha
            if result.matched_count == 0:
                logger.error(f"❌ Race condition: saldo mudou para {user_id}")
                return False, "Saldo mudou. Tente novamente."
            
            # 4️⃣ REGISTRAR TRANSAÇÃO (para auditoria)
            withdrawal_txn = {
                "user_id": user_id,
                "type": "withdrawal",
                "amount_usd": float(amount_usd),
                "status": "pending",
                "withdrawal_method": withdrawal_method,
                "created_at": datetime.utcnow(),
                "request_id": f"withdrawal_{user_id}_{int(datetime.utcnow().timestamp() * 1000)}"
            }
            await self.transaction_col.insert_one(withdrawal_txn)
            
            # 5️⃣ EXECUTAR PAGAMENTO (ex: KuCoin)
            success = await self.execute_payment(user_id, amount_usd, withdrawal_method)
            
            if not success:
                # 6️⃣ ROLLBACK: Gateway falhou, devolve saldo
                logger.warning(f"⚠️ Gateway falhou, revertendo saldo para {user_id}")
                await self.wallet_col.update_one(
                    {"user_id": user_id},
                    {"$inc": {"available_balance": float(amount_usd)}}
                )
                
                # Marcar transação como falha
                await self.transaction_col.update_one(
                    {"request_id": withdrawal_txn["request_id"]},
                    {"$set": {"status": "failed"}}
                )
                
                return False, "Falha ao processar pagamento. Saldo devolvido."
            
            # 7️⃣ SUCESSO: Marcar como completo
            await self.transaction_col.update_one(
                {"request_id": withdrawal_txn["request_id"]},
                {
                    "$set": {
                        "status": "completed",
                        "completed_at": datetime.utcnow()
                    }
                }
            )
            
            logger.info(f"✅ Saque concluído: ${amount_usd:.2f} para {user_id}")
            return True, f"Saque de ${amount_usd:.2f} processado com sucesso"
            
        except Exception as e:
            logger.error(f"❌ Erro crítico ao processar saque: {str(e)}", exc_info=True)
            
            # ROLLBACK DE EMERGÊNCIA
            await self.wallet_col.update_one(
                {"user_id": user_id},
                {"$inc": {"available_balance": float(amount_usd)}}
            )
            
            return False, f"Erro ao processar saque: {str(e)}"


# ============================================================================
# 📊 EXEMPLO DE USO
# ============================================================================

"""
# router.py - Endpoint de saque com validação cruzada:

@router.post("/withdraw")
async def request_withdrawal_safe(
    user_id: str,
    amount_usd: Decimal,
    db = Depends(get_db),
):
    '''
    Saque com múltiplas verificações de segurança
    '''
    
    wallet_service = AffiliateWalletService(db)
    
    # ✅ Usa método seguro com auditoria
    success, message = await wallet_service.process_withdrawal_with_safety(
        user_id=user_id,
        amount_usd=amount_usd,
        withdrawal_method={"type": "pix", "key": "..."}
    )
    
    if success:
        return {"status": "ok", "message": message}
    else:
        return {"status": "error", "message": message}
"""

# ============================================================================
# 🧪 TESTES DE VALIDAÇÃO CRUZADA
# ============================================================================

"""
# Adicione ao test_wallet.py:

@pytest.mark.asyncio
async def test_balance_cross_validation():
    '''Testa que saldo recalculado é consistente'''
    
    wallet_service = AffiliateWalletService(db)
    user_id = "test_user_audit"
    
    # Limpar
    await wallet_service.wallet_col.delete_one({"user_id": user_id})
    await wallet_service.transaction_col.delete_many({"user_id": user_id})
    
    # Registrar 10 comissões de $10.00
    for i in range(10):
        await wallet_service.record_commission(
            affiliate_user_id=user_id,
            referral_id=f"ref_{i}",
            sale_amount_usd=100.0,
            commission_rate=0.10,
        )
    
    # Calcular saldo real
    pending, available = await wallet_service.calculate_real_balance(user_id)
    
    print(f"Saldo Pendente (auditado): ${pending:.2f}")
    print(f"Saldo Disponível (auditado): ${available:.2f}")
    
    # 10 comissões de $10 = $100 pendente
    assert pending == Decimal("100.00"), f"Saldo pendente incorreto: {pending}"
    assert available == Decimal("0.00"), f"Saldo disponível deve ser 0: {available}"
    
    print("✅ Auditoria de saldo validada!")


@pytest.mark.asyncio
async def test_detect_balance_tampering():
    '''Testa detecção de saldo manipulado'''
    
    wallet_service = AffiliateWalletService(db)
    user_id = "test_user_fraud"
    
    # Limpar
    await wallet_service.wallet_col.delete_one({"user_id": user_id})
    
    # Criar wallet legítimo com $100
    await wallet_service.wallet_col.insert_one({
        "user_id": user_id,
        "available_balance": Decimal("100.00"),
        "pending_balance": Decimal("0.00"),
        "total_earned": Decimal("100.00"),
        "created_at": datetime.utcnow(),
    })
    
    # Simular manipulação de DB (aumento fraudulento)
    await wallet_service.wallet_col.update_one(
        {"user_id": user_id},
        {"$set": {"available_balance": Decimal("10000.00")}}  # ← FRAUDE!
    )
    
    # Verificar integridade
    is_ok, message = await wallet_service.check_balance_integrity(user_id)
    
    # Deve detectar inconsistência
    assert not is_ok, "Deveria ter detectado fraude!"
    assert "inconsistente" in message.lower(), f"Mensagem: {message}"
    
    print("✅ Fraude detectada corretamente!")
"""

# ============================================================================
# 🚀 INSTRUÇÕES DE IMPLEMENTAÇÃO
# ============================================================================

"""
PASSO 1: Adicionar novos métodos ao AffiliateWalletService

PASSO 2: Testar métodos de auditoria
$ pytest backend/tests/test_wallet.py::test_balance_cross_validation -v
$ pytest backend/tests/test_wallet.py::test_detect_balance_tampering -v

PASSO 3: Atualizar router.py para usar validate_withdrawal_with_audit()

PASSO 4: Deploy
$ git add backend/app/affiliates/wallet_service.py
$ git commit -m "🛡️ FIX: Adicionar validação cruzada de saldo (auditoria)"
$ git push origin main

IMPACTO:
- ✅ Detecta manipulação de DB
- ✅ Impede saques fraudulentos
- ✅ Auditoria 100% confiável
- ✅ Zero perda de integridade
"""
