"""
Models para o sistema de Afiliados e Wallet
- Gerenciar saldos, comissões, saques e histórico
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, List
from enum import Enum
from pydantic import BaseModel, Field


class TransactionType(str, Enum):
    """Tipos de transacao no wallet"""
    COMMISSION = "commission"
    WITHDRAWAL = "withdrawal"
    REVERSAL = "reversal"
    REFUND = "refund"


class TransactionStatus(str, Enum):
    """Status de uma transacao"""
    PENDING = "pending"
    AVAILABLE = "available"
    COMPLETED = "completed"
    FAILED = "failed"
    REVERSED = "reversed"


class WithdrawalMethodType(str, Enum):
    """Metodos de saque disponveis"""
    PIX = "pix"
    CRYPTO = "crypto"
    BANK_TRANSFER = "bank_transfer"


class WithdrawalStatus(str, Enum):
    """Status de uma requisicao de saque"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WithdrawalMethod(BaseModel):
    """Metodo de saque do afiliado"""
    type: WithdrawalMethodType = Field(..., description="Tipo de saque (pix, crypto, bank_transfer)")
    key: str = Field(..., description="Chave Pix, endereco crypto, ou conta bancaria")
    holder_name: str = Field(..., description="Nome do titular da conta")
    is_verified: bool = Field(default=False, description="Se o metodo foi verificado")
    verified_at: Optional[datetime] = Field(default=None, description="Timestamp da verificacao")

    class Config:
        from_attributes = True


class AffiliateWallet(BaseModel):
    """Wallet de Afiliado - Gerencia saldos e metodos de saque"""
    id: Optional[str] = None
    user_id: str = Field(..., description="ID do usuario afiliado (indexado)")
    
    # Saldos (em USD com Decimal para precisao)
    pending_balance: Decimal = Field(
        default=Decimal("0.00"),
        ge=0,
        description="Saldo em periodo de carencia (7 dias). Nao e saqueavel ainda."
    )
    available_balance: Decimal = Field(
        default=Decimal("0.00"),
        ge=0,
        description="Saldo disponivel para saque (ja passou periodo de carencia)"
    )
    total_withdrawn: Decimal = Field(
        default=Decimal("0.00"),
        ge=0,
        description="Total historico ja sacado em USD"
    )
    
    # Historico
    total_earned: Decimal = Field(
        default=Decimal("0.00"),
        ge=0,
        description="Total ja ganho em comissoes (pending + available + withdrawn)"
    )
    
    # Metodo de saque
    withdrawal_method: Optional[WithdrawalMethod] = Field(
        default=None,
        description="Dados bancarios do afiliado (Pix, Crypto, Bank)"
    )
    
    # Metadados
    last_withdrawal_at: Optional[datetime] = Field(
        default=None,
        description="Data do ultimo saque processado"
    )
    currency: str = Field(default="USD", description="Moeda utilizada")
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    @property
    def total_balance(self) -> Decimal:
        """Total de saldo (pendente + disponvel)"""
        return (self.pending_balance + self.available_balance).quantize(Decimal("0.01"))
    
    @property
    def is_withdrawal_ready(self) -> bool:
        """Se pode fazer saque (saldo >= $50 e metodo configurado)"""
        return self.available_balance >= Decimal("50.0") and self.withdrawal_method is not None
    
    class Config:
        from_attributes = True


class AffiliateTransaction(BaseModel):
    """Transacao no Wallet - Auditoria de movimentacao de saldos"""
    id: Optional[str] = None
    
    user_id: str = Field(..., description="ID do usuario afiliado")
    type: TransactionType = Field(
        ...,
        description="Tipo: commission, withdrawal, reversal, refund"
    )
    status: TransactionStatus = Field(
        default=TransactionStatus.PENDING,
        description="Status: pending, available, completed, failed, reversed"
    )
    
    # Valores em USD (Decimal para precisao)
    amount_usd: Decimal = Field(
        ...,
        gt=0,
        description="Valor da transacao em USD"
    )
    
    # Para comissoes: quando o saldo sera liberado
    release_at: Optional[datetime] = Field(
        default=None,
        description="Data em que o saldo pendente se torna disponvel (Data + 7 dias para comissoes)"
    )
    
    # Para saques: informacoes adicionais
    withdrawal_id: Optional[str] = Field(
        default=None,
        description="ID da requisicao de saque (se type=withdrawal)"
    )
    
    # Referencia da geracao da comissao
    referral_id: Optional[str] = Field(
        default=None,
        description="ID do referral que gerou a comissao (se type=commission)"
    )
    sale_amount_usd: Optional[Decimal] = Field(
        default=None,
        description="Valor da venda que gerou a comissao (para referencia)"
    )
    commission_rate: Optional[Decimal] = Field(
        default=None,
        description="Taxa de comissao aplicada (ex: 0.10 para 10%)"
    )
    
    # Detalhes de falha
    failure_reason: Optional[str] = Field(
        default=None,
        description="Motivo da falha (se status=failed)"
    )
    
    # Metadata
    notes: Optional[str] = Field(
        default=None,
        description="Notas adicionais sobre a transacao"
    )
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        from_attributes = True


class WithdrawRequest(BaseModel):
    """Requisicao de Saque - Rastreamento de saques"""
    id: Optional[str] = None
    
    user_id: str = Field(..., description="ID do usuario afiliado")
    amount_usd: Decimal = Field(
        ...,
        ge=Decimal("50.0"),
        description="Valor solicitado em USD (minimo $50)"
    )
    
    status: WithdrawalStatus = Field(
        default=WithdrawalStatus.PENDING,
        description="Status do saque"
    )
    
    # Informacoes de pagamento
    withdrawal_method: WithdrawalMethod = Field(
        ...,
        description="Metodo de saque utilizado"
    )
    
    # Processamento
    transaction_id: Optional[str] = Field(
        default=None,
        description="ID da transacao no gateway de pagamento (ex: Stripe, StarkBank)"
    )
    gateway_response: Optional[dict] = Field(
        default=None,
        description="Resposta completa do gateway para auditoria"
    )
    
    # Falhas
    failure_reason: Optional[str] = Field(
        default=None,
        description="Motivo da falha (se status=failed)"
    )
    retry_count: int = Field(
        default=0,
        ge=0,
        le=3,
        description="Numero de tentativas de processar"
    )
    last_retry_at: Optional[datetime] = Field(
        default=None,
        description="Data da ultima tentativa"
    )
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    requested_at: datetime = Field(default_factory=datetime.utcnow, description="Quando foi solicitado")
    processed_at: Optional[datetime] = Field(default=None, description="Quando foi processado")
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        from_attributes = True


# Constants para configuracao
COMMISSION_HOLD_DAYS = 7
MINIMUM_WITHDRAWAL_AMOUNT = Decimal("50.0")
COMMISSION_RATE = Decimal("0.10")
MAX_WITHDRAWAL_RETRIES = 3
COMMISSION_TIERS = {
    "bronze": Decimal("0.10"),
    "silver": Decimal("0.15"),
    "gold": Decimal("0.20"),
    "platinum": Decimal("0.25"),
}
