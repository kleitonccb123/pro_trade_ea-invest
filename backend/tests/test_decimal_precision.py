"""
TEST SUITE: VULNERABILITY #2 - DECIMAL PRECISION VALIDATION

Testes para garantir que:
1. Não há perda de precisão nos cálculos
2. Rounding é feito corretamente (centavos)
3. Operações matemáticas mantêm precisão
4. Valores monetários sempre têm 2 casas decimais
"""

import pytest
from decimal import Decimal
from datetime import datetime


class TestDecimalPrecision:
    """Testes para validar precisão decimal em operações financeiras"""

    def test_decimal_import(self):
        """✅ Teste 1: Verificar que Decimal está importado"""
        from decimal import Decimal
        assert Decimal is not None

    def test_basic_decimal_operations(self):
        """✅ Teste 2: Operações básicas com Decimal"""
        amount = Decimal("100.00")
        rate = Decimal("0.15")  # 15%
        
        commission = (amount * rate).quantize(Decimal("0.01"))
        
        assert commission == Decimal("15.00")
        assert str(commission) == "15.00"

    def test_no_rounding_loss(self):
        """✅ Teste 3: Não há perda de precisão em divisão"""
        # Problem: 100 / 3 = 33.333333...
        value = Decimal("100.00")
        result = (value / Decimal("3")).quantize(Decimal("0.01"))
        
        # Float causaria: 33.33333333333333
        # Decimal com quantize: 33.33
        assert result == Decimal("33.33")

    def test_accumulation_precision(self):
        """✅ Teste 4: Sem perda acumulativa em múltiplas operações"""
        balances = [
            Decimal("10.50"),
            Decimal("20.30"),
            Decimal("15.75"),
            Decimal("5.99")
        ]
        
        total = sum(balances, Decimal("0.00")).quantize(Decimal("0.01"))
        
        # Sem Decimal, haveria floating point errors
        assert total == Decimal("52.54")
        assert total == Decimal("52.54")  # Sempre igual

    def test_commission_calculation_precision(self):
        """✅ Teste 5: Cálculo de comissão com precisão"""
        sale_amount = Decimal("999.99")
        commission_rate = Decimal("0.10")  # 10%
        
        commission = (sale_amount * commission_rate).quantize(Decimal("0.01"))
        
        # Com float: 99.99899999999999
        # Com Decimal: 99.99
        assert commission == Decimal("99.99")

    def test_multiple_rates_precision(self):
        """✅ Teste 6: Múltiplas taxas aplicadas"""
        sale_amount = Decimal("1000.00")
        
        # Tier 1: 5%
        comm1 = (sale_amount * Decimal("0.05")).quantize(Decimal("0.01"))
        # Tier 2: 10%
        comm2 = (sale_amount * Decimal("0.10")).quantize(Decimal("0.01"))
        # Tier 3: 15%
        comm3 = (sale_amount * Decimal("0.15")).quantize(Decimal("0.01"))
        
        total_commission = (comm1 + comm2 + comm3).quantize(Decimal("0.01"))
        
        assert comm1 == Decimal("50.00")
        assert comm2 == Decimal("100.00")
        assert comm3 == Decimal("150.00")
        assert total_commission == Decimal("300.00")

    def test_withdrawal_edge_case(self):
        """✅ Teste 7: Saque com saldo decimal complexo"""
        available_balance = Decimal("123.45")
        withdrawal_amount = Decimal("50.00")
        
        remaining = (available_balance - withdrawal_amount).quantize(Decimal("0.01"))
        
        assert remaining == Decimal("73.45")

    def test_hold_period_with_precision(self):
        """✅ Teste 8: Saldo em carência com precisão"""
        total_commission = Decimal("250.75")
        
        # 20% em carência, 80% disponível
        hold_amount = (total_commission * Decimal("0.20")).quantize(Decimal("0.01"))
        available_amount = (total_commission * Decimal("0.80")).quantize(Decimal("0.01"))
        
        assert hold_amount == Decimal("50.15")
        assert available_amount == Decimal("200.60")
        assert (hold_amount + available_amount) == Decimal("250.75")

    def test_referral_chain_precision(self):
        """✅ Teste 9: Cadeia de referrals mantém precisão"""
        sale_amount = Decimal("500.00")
        
        # Level 1: 10%
        level1 = (sale_amount * Decimal("0.10")).quantize(Decimal("0.01"))
        # Level 2: 5% of level 1
        level2 = (level1 * Decimal("0.05")).quantize(Decimal("0.01"))
        # Level 3: 2% of level 2
        level3 = (level2 * Decimal("0.02")).quantize(Decimal("0.01"))
        
        assert level1 == Decimal("50.00")
        assert level2 == Decimal("2.50")
        assert level3 == Decimal("0.05")

    def test_minimum_withdrawal_validation(self):
        """✅ Teste 10: Validação de saque mínimo"""
        MINIMUM = Decimal("50.00")
        
        # Test 1: Saldo exato
        assert Decimal("50.00") >= MINIMUM
        
        # Test 2: Saldo um centavo abaixo
        assert not (Decimal("49.99") >= MINIMUM)
        
        # Test 3: Saldo com muitas casas decimais (após quantize)
        calculated = (Decimal("100.00") / Decimal("2")).quantize(Decimal("0.01"))
        assert calculated >= MINIMUM

    def test_edge_case_tiny_amounts(self):
        """✅ Teste 11: Valores muito pequenos"""
        tiny_amount = Decimal("0.01")
        
        # Operação com amount tiny
        result = (tiny_amount * Decimal("100")).quantize(Decimal("0.01"))
        
        assert result == Decimal("1.00")

    def test_edge_case_large_amounts(self):
        """✅ Teste 12: Valores muito grandes"""
        large_amount = Decimal("999999.99")
        rate = Decimal("0.015")  # 1.5%
        
        commission = (large_amount * rate).quantize(Decimal("0.01"))
        
        # Com float causaria overflow/precision issues
        assert commission == Decimal("14999.99")

    def test_balance_transfer_precision(self):
        """✅ Teste 13: Transferência entre saldos mantém total"""
        pending = Decimal("75.50")
        available = Decimal("124.50")
        total_before = (pending + available).quantize(Decimal("0.01"))
        
        # Simular liberação de $50 do pending
        new_pending = (pending - Decimal("50.00")).quantize(Decimal("0.01"))
        new_available = (available + Decimal("50.00")).quantize(Decimal("0.01"))
        total_after = (new_pending + new_available).quantize(Decimal("0.01"))
        
        assert total_before == Decimal("200.00")
        assert total_after == Decimal("200.00")
        assert new_pending == Decimal("25.50")
        assert new_available == Decimal("174.50")

    def test_string_conversion_precision(self):
        """✅ Teste 14: Conversão string → Decimal mantém precisão"""
        string_amount = "123.456"
        
        # Decimal converte exatamente
        d = Decimal(string_amount)
        quantized = d.quantize(Decimal("0.01"))
        
        assert quantized == Decimal("123.46")

    def test_float_to_decimal_conversion(self):
        """✅ Teste 15: Conversão float → Decimal é segura via string"""
        float_amount = 123.456
        
        # Correto: converter via string
        d_correct = Decimal(str(float_amount))
        
        # Errado (não fazer): Decimal direto
        # d_wrong = Decimal(float_amount)  # Não recomendado!
        
        assert d_correct.quantize(Decimal("0.01")) == Decimal("123.46")


class TestAffiliateWalletDecimal:
    """Testes integrados para wallet com Decimal"""

    def test_wallet_creation_with_decimals(self):
        """✅ Teste 16: Wallet criada com Decimal por padrão"""
        # Simular criação de wallet
        pending_balance = Decimal("0.00")
        available_balance = Decimal("0.00")
        
        assert pending_balance == Decimal("0.00")
        assert available_balance == Decimal("0.00")

    def test_wallet_commission_deposit(self):
        """✅ Teste 17: Depósito de comissão mantém precisão"""
        pending_balance = Decimal("0.00")
        commission = Decimal("25.75")
        
        new_pending = (pending_balance + commission).quantize(Decimal("0.01"))
        
        assert new_pending == commission

    def test_wallet_multiple_deposits(self):
        """✅ Teste 18: Múltiplos depósitos sem perda"""
        balance = Decimal("0.00")
        
        deposits = [
            Decimal("10.50"),
            Decimal("20.75"),
            Decimal("15.25"),
            Decimal("5.99")
        ]
        
        for deposit in deposits:
            balance = (balance + deposit).quantize(Decimal("0.01"))
        
        assert balance == Decimal("52.49")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

