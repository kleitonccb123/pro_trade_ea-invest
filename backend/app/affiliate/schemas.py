from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum

class AffiliateLevel(str, Enum):
    BRONZE = "bronze"
    SILVER = "silver"
    GOLD = "gold"
    PLATINUM = "platinum"
    DIAMOND = "diamond"


class AffiliateBase(BaseModel):
    referral_code: str
    is_active: bool = True


class AffiliateCreate(BaseModel):
    user_id: int


class AffiliateUpdate(BaseModel):
    level: Optional[AffiliateLevel] = None
    commission_rate: Optional[float] = None
    is_verified: Optional[bool] = None
    bank_account: Optional[str] = None
    bank_name: Optional[str] = None
    cpf: Optional[str] = None


class AffiliateResponse(AffiliateBase):
    id: int
    user_id: int
    referral_link: str
    level: AffiliateLevel
    commission_rate: float
    total_referrals: int
    active_referrals: int
    total_earnings: float
    pending_earnings: float
    withdrawn_earnings: float
    is_verified: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class AffiliateStatsResponse(BaseModel):
    total_referrals: int
    active_referrals: int
    total_earnings: float
    pending_earnings: float
    withdrawn_earnings: float
    commission_rate: float
    level: AffiliateLevel
    next_level: Optional[AffiliateLevel] = None
    referrals_to_next_level: Optional[int] = None


class ReferralResponse(BaseModel):
    id: int
    referred_email: str
    referred_name: str
    referral_date: datetime
    first_purchase_date: Optional[datetime]
    is_active: bool
    total_purchases: float
    total_commission: float
    
    class Config:
        from_attributes = True


class CommissionResponse(BaseModel):
    id: int
    amount: float
    commission_rate: float
    source: str
    status: str
    created_at: datetime
    paid_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class WithdrawalCreate(BaseModel):
    amount: float = Field(..., gt=0)
    bank_account: str
    bank_name: str
    cpf: str


class WithdrawalResponse(BaseModel):
    id: int
    amount: float
    status: str
    requested_at: datetime
    processed_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class LevelBonusResponse(BaseModel):
    level: AffiliateLevel
    bonus_percentage: float
    min_referrals: int
    commission_rate: float
    description: str
    special_benefits: Optional[str]
    
    class Config:
        from_attributes = True


class AffiliateDashboardResponse(BaseModel):
    affiliate: AffiliateResponse
    stats: AffiliateStatsResponse
    recent_referrals: List[ReferralResponse]
    recent_commissions: List[CommissionResponse]
    level_benefits: List[LevelBonusResponse]
