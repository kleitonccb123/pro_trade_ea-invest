"""
Affiliate System - Sistema de Indica??o/Afiliados

Este m?dulo implementa:
1. Gera??o de link ?nico por usu?rio
2. Tracking de referrals via cookie
3. Atribui??o autom?tica de indica??es
4. C?lculo de comiss?es

Estrutura:
- Cada usu?rio tem um c?digo de afiliado ?nico
- Quando um novo usu?rio se cadastra com cookie de referral, ? atribu?do ao "pai"
- Comiss?es s?o calculadas sobre vendas de licen?as

Author: Crypto Trade Hub
"""

from __future__ import annotations

import logging
import hashlib
import secrets
from datetime import datetime
from typing import Dict, Any, Optional, List
from bson import ObjectId

from app.core.database import get_db

logger = logging.getLogger(__name__)


class AffiliateService:
    """Servi?o de gerenciamento de afiliados."""
    
    USERS_COLLECTION = "users"
    REFERRALS_COLLECTION = "referrals"
    COMMISSIONS_COLLECTION = "affiliate_commissions"
    
    # Taxa de comiss?o (percentual sobre vendas)
    COMMISSION_RATE = 0.10  # 10%
    
    # N?veis de afiliado e taxas
    AFFILIATE_TIERS = {
        "bronze": {"min_referrals": 0, "commission_rate": 0.10},
        "silver": {"min_referrals": 10, "commission_rate": 0.15},
        "gold": {"min_referrals": 50, "commission_rate": 0.20},
        "platinum": {"min_referrals": 100, "commission_rate": 0.25},
    }
    
    @classmethod
    def _get_users_collection(cls):
        db = get_db()
        return db[cls.USERS_COLLECTION]
    
    @classmethod
    def _get_referrals_collection(cls):
        db = get_db()
        return db[cls.REFERRALS_COLLECTION]
    
    @classmethod
    def _get_commissions_collection(cls):
        db = get_db()
        return db[cls.COMMISSIONS_COLLECTION]
    
    # ==================== AFFILIATE CODE ====================
    
    @classmethod
    def generate_affiliate_code(cls, user_id: str) -> str:
        """
        Gera um c?digo de afiliado ?nico baseado no ID do usu?rio.
        
        Formato: 8 caracteres alfanum?ricos (ex: "A3X9K2M7")
        """
        # Combinar user_id com um salt secreto
        salt = "crypto_trade_hub_affiliate_v1"
        hash_input = f"{user_id}:{salt}"
        
        # Gerar hash e pegar primeiros 8 caracteres
        hash_bytes = hashlib.sha256(hash_input.encode()).hexdigest()
        code = hash_bytes[:8].upper()
        
        return code
    
    @classmethod
    async def get_or_create_affiliate_code(cls, user_id: str | ObjectId) -> str:
        """
        Obt?m o c?digo de afiliado do usu?rio, criando se n?o existir.
        """
        collection = cls._get_users_collection()
        
        if isinstance(user_id, str):
            try:
                user_id = ObjectId(user_id)
            except:
                pass
        
        user = await collection.find_one({"_id": user_id})
        
        if not user:
            raise ValueError("Usu?rio n?o encontrado")
        
        # Se j? tem c?digo, retornar
        if user.get("affiliate_code"):
            return user["affiliate_code"]
        
        # Gerar novo c?digo
        code = cls.generate_affiliate_code(str(user_id))
        
        # Verificar se c?digo j? existe (colis?o improv?vel, mas poss?vel)
        existing = await collection.find_one({"affiliate_code": code})
        if existing:
            # Adicionar sufixo aleat?rio
            code = code[:6] + secrets.token_hex(1).upper()
        
        # Salvar no usu?rio
        await collection.update_one(
            {"_id": user_id},
            {
                "$set": {
                    "affiliate_code": code,
                    "affiliate_created_at": datetime.utcnow(),
                }
            }
        )
        
        logger.info(f"? C?digo de afiliado criado: {code} para user {user_id}")
        return code
    
    @classmethod
    def generate_affiliate_link(cls, affiliate_code: str, base_url: str = None) -> str:
        """
        Gera o link completo de indica??o.
        
        Args:
            affiliate_code: C?digo do afiliado
            base_url: URL base (padr?o: do ambiente)
            
        Returns:
            Link completo (ex: https://cryptotrade.hub/r/A3X9K2M7)
        """
        if not base_url:
            base_url = "https://cryptotrade.hub"
        
        return f"{base_url}/r/{affiliate_code}"
    
    # ==================== REFERRAL TRACKING ====================
    
    @classmethod
    async def find_user_by_affiliate_code(cls, code: str) -> Optional[Dict[str, Any]]:
        """Encontra o usu?rio pelo c?digo de afiliado."""
        collection = cls._get_users_collection()
        return await collection.find_one({"affiliate_code": code.upper()})
    
    @classmethod
    async def register_referral(
        cls,
        new_user_id: str | ObjectId,
        referrer_code: str
    ) -> Optional[Dict[str, Any]]:
        """
        Registra uma indica??o quando um novo usu?rio se cadastra.
        
        Args:
            new_user_id: ID do novo usu?rio cadastrado
            referrer_code: C?digo do afiliado que indicou
            
        Returns:
            Documento de referral criado ou None se c?digo inv?lido
        """
        if isinstance(new_user_id, str):
            try:
                new_user_id = ObjectId(new_user_id)
            except:
                pass
        
        # Encontrar o referrer
        referrer = await cls.find_user_by_affiliate_code(referrer_code)
        if not referrer:
            logger.warning(f"?? C?digo de afiliado n?o encontrado: {referrer_code}")
            return None
        
        referrer_id = referrer["_id"]
        
        # Verificar se n?o ? auto-refer?ncia
        if str(referrer_id) == str(new_user_id):
            logger.warning(f"?? Tentativa de auto-refer?ncia: {new_user_id}")
            return None
        
        # Verificar se j? n?o foi indicado por algu?m
        referrals_col = cls._get_referrals_collection()
        existing = await referrals_col.find_one({"referred_user_id": new_user_id})
        if existing:
            logger.warning(f"?? Usu?rio j? foi indicado: {new_user_id}")
            return None
        
        # Criar registro de referral
        now = datetime.utcnow()
        referral_doc = {
            "referrer_id": referrer_id,
            "referred_user_id": new_user_id,
            "affiliate_code": referrer_code.upper(),
            "status": "registered",  # registered, converted, churned
            "created_at": now,
            "converted_at": None,
            "first_purchase_at": None,
            "total_revenue": 0.0,
            "total_commission": 0.0,
        }
        
        result = await referrals_col.insert_one(referral_doc)
        referral_doc["_id"] = result.inserted_id
        
        # Atualizar contador do referrer
        users_col = cls._get_users_collection()
        await users_col.update_one(
            {"_id": referrer_id},
            {
                "$inc": {"total_referrals": 1},
                "$set": {"last_referral_at": now}
            }
        )
        
        # Atualizar o novo usu?rio com o referrer_id
        await users_col.update_one(
            {"_id": new_user_id},
            {
                "$set": {
                    "referred_by": referrer_id,
                    "referral_code_used": referrer_code.upper(),
                }
            }
        )
        
        logger.info(f"? Referral registrado: {new_user_id} indicado por {referrer_id}")
        return referral_doc
    
    # ==================== COMMISSION TRACKING ====================
    
    @classmethod
    async def record_commission(
        cls,
        referral_id: ObjectId,
        sale_amount: float,
        description: str = None
    ) -> Dict[str, Any]:
        """
        Registra uma comiss?o para um referral quando h? uma venda.
        
        Args:
            referral_id: ID do documento de referral
            sale_amount: Valor da venda
            description: Descri??o da transa??o
            
        Returns:
            Documento de comiss?o criado
        """
        referrals_col = cls._get_referrals_collection()
        commissions_col = cls._get_commissions_collection()
        
        # Buscar referral
        referral = await referrals_col.find_one({"_id": referral_id})
        if not referral:
            raise ValueError("Referral n?o encontrado")
        
        referrer_id = referral["referrer_id"]
        
        # Calcular tier e taxa de comiss?o
        users_col = cls._get_users_collection()
        referrer = await users_col.find_one({"_id": referrer_id})
        total_referrals = referrer.get("total_referrals", 0) if referrer else 0
        
        # Determinar tier
        tier = "bronze"
        commission_rate = cls.COMMISSION_RATE
        for tier_name, tier_config in sorted(
            cls.AFFILIATE_TIERS.items(),
            key=lambda x: x[1]["min_referrals"],
            reverse=True
        ):
            if total_referrals >= tier_config["min_referrals"]:
                tier = tier_name
                commission_rate = tier_config["commission_rate"]
                break
        
        # Calcular comiss?o
        commission_amount = sale_amount * commission_rate
        
        now = datetime.utcnow()
        commission_doc = {
            "referral_id": referral_id,
            "referrer_id": referrer_id,
            "referred_user_id": referral["referred_user_id"],
            "sale_amount": sale_amount,
            "commission_rate": commission_rate,
            "commission_amount": commission_amount,
            "tier": tier,
            "status": "pending",  # pending, approved, paid, cancelled
            "description": description,
            "created_at": now,
            "approved_at": None,
            "paid_at": None,
        }
        
        result = await commissions_col.insert_one(commission_doc)
        commission_doc["_id"] = result.inserted_id
        
        # Atualizar totais no referral
        await referrals_col.update_one(
            {"_id": referral_id},
            {
                "$inc": {
                    "total_revenue": sale_amount,
                    "total_commission": commission_amount,
                },
                "$set": {
                    "status": "converted",
                    "converted_at": referral.get("converted_at") or now,
                }
            }
        )
        
        # Atualizar totais do referrer
        await users_col.update_one(
            {"_id": referrer_id},
            {
                "$inc": {
                    "affiliate_total_earnings": commission_amount,
                    "affiliate_pending_earnings": commission_amount,
                }
            }
        )
        
        logger.info(f"? Comiss?o registrada: ${commission_amount:.2f} para {referrer_id}")
        return commission_doc
    
    # ==================== AFFILIATE STATS ====================
    
    @classmethod
    async def get_affiliate_stats(cls, user_id: str | ObjectId) -> Dict[str, Any]:
        """
        Obt?m estat?sticas completas de afiliado para um usu?rio.
        """
        if isinstance(user_id, str):
            try:
                user_id = ObjectId(user_id)
            except:
                pass
        
        users_col = cls._get_users_collection()
        referrals_col = cls._get_referrals_collection()
        commissions_col = cls._get_commissions_collection()
        
        # Dados do usu?rio
        user = await users_col.find_one({"_id": user_id})
        if not user:
            raise ValueError("Usu?rio n?o encontrado")
        
        affiliate_code = await cls.get_or_create_affiliate_code(user_id)
        
        # Contar referrals
        total_referrals = await referrals_col.count_documents({"referrer_id": user_id})
        converted_referrals = await referrals_col.count_documents({
            "referrer_id": user_id,
            "status": "converted"
        })
        
        # Somar comiss?es
        pipeline = [
            {"$match": {"referrer_id": user_id}},
            {"$group": {
                "_id": "$status",
                "total": {"$sum": "$commission_amount"}
            }}
        ]
        commission_totals = {}
        async for doc in commissions_col.aggregate(pipeline):
            commission_totals[doc["_id"]] = doc["total"]
        
        # Determinar tier
        tier = "bronze"
        for tier_name, tier_config in sorted(
            cls.AFFILIATE_TIERS.items(),
            key=lambda x: x[1]["min_referrals"],
            reverse=True
        ):
            if total_referrals >= tier_config["min_referrals"]:
                tier = tier_name
                break
        
        tier_config = cls.AFFILIATE_TIERS[tier]
        
        # Pr?ximo tier
        next_tier = None
        next_tier_remaining = 0
        tier_order = ["bronze", "silver", "gold", "platinum"]
        current_tier_index = tier_order.index(tier)
        if current_tier_index < len(tier_order) - 1:
            next_tier = tier_order[current_tier_index + 1]
            next_tier_remaining = cls.AFFILIATE_TIERS[next_tier]["min_referrals"] - total_referrals
        
        return {
            "affiliate_code": affiliate_code,
            "affiliate_link": cls.generate_affiliate_link(affiliate_code),
            "tier": tier,
            "commission_rate": tier_config["commission_rate"],
            "total_referrals": total_referrals,
            "converted_referrals": converted_referrals,
            "conversion_rate": (converted_referrals / total_referrals * 100) if total_referrals > 0 else 0,
            "earnings": {
                "pending": commission_totals.get("pending", 0),
                "approved": commission_totals.get("approved", 0),
                "paid": commission_totals.get("paid", 0),
                "total": sum(commission_totals.values()),
            },
            "next_tier": next_tier,
            "referrals_to_next_tier": max(0, next_tier_remaining),
        }
    
    @classmethod
    async def get_referrals_list(
        cls,
        user_id: str | ObjectId,
        limit: int = 50,
        skip: int = 0
    ) -> List[Dict[str, Any]]:
        """Lista os referrals de um usu?rio."""
        if isinstance(user_id, str):
            try:
                user_id = ObjectId(user_id)
            except:
                pass
        
        referrals_col = cls._get_referrals_collection()
        users_col = cls._get_users_collection()
        
        cursor = referrals_col.find({"referrer_id": user_id}).sort("created_at", -1).skip(skip).limit(limit)
        referrals = await cursor.to_list(length=limit)
        
        # Enriquecer com dados do usu?rio referido
        result = []
        for ref in referrals:
            referred_user = await users_col.find_one(
                {"_id": ref["referred_user_id"]},
                {"email": 1, "name": 1, "created_at": 1}
            )
            result.append({
                "_id": str(ref["_id"]),
                "referred_email": referred_user.get("email", "***") if referred_user else "Deleted",
                "referred_name": referred_user.get("name") if referred_user else None,
                "status": ref["status"],
                "created_at": ref["created_at"],
                "converted_at": ref.get("converted_at"),
                "total_revenue": ref.get("total_revenue", 0),
                "total_commission": ref.get("total_commission", 0),
            })
        
        return result


# Inst?ncia global
affiliate_service = AffiliateService()
