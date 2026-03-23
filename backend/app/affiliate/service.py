from app.affiliate.repository import AffiliateRepository
from app.affiliate.model import AffiliateLevel


class AffiliateService:
    """Service para l?gica de neg?cio de afiliado"""
    
    @staticmethod
    async def create_affiliate(db: AsyncSession, user_id: int):
        """Cria novo afiliado"""
        # Verifica se j? existe
        existing = await AffiliateRepository.get_affiliate_by_user_id(db, user_id)
        if existing:
            raise ValueError("Usu?rio j? ? afiliado")
        
        affiliate = await AffiliateRepository.create_affiliate(db, user_id)
        await db.commit()
        return affiliate
    
    @staticmethod
    async def get_affiliate_dashboard(db: AsyncSession, user_id: int):
        """Obt?m dashboard completo do afiliado"""
        affiliate = await AffiliateRepository.get_affiliate_by_user_id(db, user_id)
        
        if not affiliate:
            raise ValueError("Afiliado n?o encontrado")
        
        # Estat?sticas
        stats = await AffiliateRepository.get_affiliate_stats(db, affiliate.id)
        
        # Refer?ncias recentes
        recent_referrals = await AffiliateRepository.get_referrals(
            db, affiliate.id, skip=0, limit=5
        )
        
        # Comiss?es recentes
        recent_commissions = await AffiliateRepository.get_commissions(
            db, affiliate.id, skip=0, limit=5
        )
        
        # Benef?cios por n?vel
        level_bonuses = await AffiliateRepository.get_level_bonuses(db)
        
        return {
            "affiliate": affiliate,
            "stats": stats,
            "recent_referrals": recent_referrals,
            "recent_commissions": recent_commissions,
            "level_bonuses": level_bonuses
        }
    
    @staticmethod
    async def add_referral(db: AsyncSession, affiliate_id: int, referred_user_id: int,
                          referred_email: str = None, referred_name: str = None):
        """Adiciona nova refer?ncia"""
        # Verifica se refer?ncia j? existe
        affiliate = await AffiliateRepository.get_affiliate_by_id(db, affiliate_id)
        if not affiliate:
            raise ValueError("Afiliado n?o encontrado")
        
        referral = await AffiliateRepository.add_referral(
            db, affiliate_id, referred_user_id, referred_email, referred_name
        )
        await db.commit()
        return referral
    
    @staticmethod
    async def register_purchase_commission(db: AsyncSession, affiliate_id: int,
                                          referred_user_id: int, purchase_amount: float):
        """Registra comiss?o de compra do usu?rio referido"""
        affiliate = await AffiliateRepository.get_affiliate_by_id(db, affiliate_id)
        if not affiliate:
            raise ValueError("Afiliado n?o encontrado")
        
        # Encontra a refer?ncia
        referrals = await AffiliateRepository.get_referrals(db, affiliate_id, limit=100)
        referral = next((r for r in referrals if r.referred_user_id == referred_user_id), None)
        
        if not referral:
            raise ValueError("Refer?ncia n?o encontrada")
        
        # Calcula comiss?o
        commission_amount = (purchase_amount * affiliate.commission_rate) / 100
        
        commission = await AffiliateRepository.add_commission(
            db, affiliate_id, referral.id, commission_amount,
            affiliate.commission_rate, "subscription"
        )
        
        # Atualiza total de compras da refer?ncia
        referral.total_purchases += purchase_amount
        referral.total_commission += commission_amount
        
        await db.commit()
        return commission
    
    @staticmethod
    async def request_withdrawal(db: AsyncSession, affiliate_id: int, amount: float,
                                bank_account: str, bank_name: str, cpf: str):
        """Solicita saque de comiss?o"""
        withdrawal = await AffiliateRepository.request_withdrawal(
            db, affiliate_id, amount, bank_account, bank_name, cpf
        )
        await db.commit()
        return withdrawal
    
    @staticmethod
    async def validate_referral_code(db: AsyncSession, code: str) -> dict:
        """Valida c?digo de refer?ncia"""
        affiliate = await AffiliateRepository.get_affiliate_by_code(db, code)
        
        if not affiliate or not affiliate.is_active:
            raise ValueError("C?digo de refer?ncia inv?lido")
        
        return {
            "affiliate_id": affiliate.id,
            "affiliate_name": affiliate.user_id,
            "level": affiliate.level,
            "commission_rate": affiliate.commission_rate,
            "valid": True
        }
    
    @staticmethod
    async def calculate_next_level_bonus(db: AsyncSession, affiliate_id: int) -> dict:
        """Calcula b?nus e informa??es do pr?ximo n?vel"""
        affiliate = await AffiliateRepository.get_affiliate_by_id(db, affiliate_id)
        
        if not affiliate:
            raise ValueError("Afiliado n?o encontrado")
        
        if affiliate.level == AffiliateLevel.DIAMOND:
            return {"current_level": AffiliateLevel.DIAMOND, "is_max_level": True}
        
        # Define progress?o de n?veis
        levels = [AffiliateLevel.BRONZE, AffiliateLevel.SILVER, AffiliateLevel.GOLD,
                 AffiliateLevel.PLATINUM, AffiliateLevel.DIAMOND]
        current_index = levels.index(affiliate.level)
        next_level = levels[current_index + 1]
        
        next_bonus = await AffiliateRepository.get_level_bonus(db, next_level)
        
        if not next_bonus:
            return {"error": "N?vel n?o configurado"}
        
        return {
            "current_level": affiliate.level,
            "next_level": next_level,
            "current_referrals": affiliate.active_referrals,
            "referrals_needed": next_bonus.min_referrals,
            "referrals_to_goal": max(0, next_bonus.min_referrals - affiliate.active_referrals),
            "commission_increase": next_bonus.bonus_percentage,
            "is_max_level": False
        }
