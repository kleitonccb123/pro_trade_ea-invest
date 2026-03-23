"""
Testes Unitários — TradingExecutor

Testa cada método isoladamente com mocks.

Executar:
    pytest backend/tests/unit/test_trading_executor.py -v
"""

import pytest
from decimal import Decimal
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch, ANY
from bson import ObjectId

from app.trading.executor import (
    TradingExecutor,
    ValidationFailedError,
    InsufficientBalanceError,
    ExchangeTimeoutError,
    OrderExecutionError
)


@pytest.fixture
def executor():
    """Cria um TradingExecutor com user_id fake"""
    exec = TradingExecutor(
        user_id="test_user_123",
        exchange="kucoin",
        testnet=True,
        max_monitoring_time=10  # Reduzido para testes
    )
    return exec


@pytest.fixture
def mock_credentials():
    """Credenciais fake criptografadas"""
    return {
        "user_id": "test_user_123",
        "exchange": "kucoin",
        "api_key_encrypted": "fake_encrypted_key",
        "api_secret_encrypted": "fake_encrypted_secret",
        "passphrase_encrypted": "fake_encrypted_passphrase",
        "is_active": True
    }


@pytest.fixture
def mock_normalized_order():
    """Ordem normalizada fake (do KuCoin)"""
    order = MagicMock()
    order.order_id = "fake_order_id_123"
    order.symbol = "BTC-USDT"
    order.side = "buy"
    order.size = Decimal("0.1")
    order.status = "FILLED"
    order.fill_price = Decimal("42000.00")
    order.filled_qty = Decimal("0.1")
    order.created_at = datetime.utcnow()
    return order


class TestTradingExecutorInitialization:
    """Testes de inicialização"""
    
    @pytest.mark.asyncio
    async def test_initialize_success(self, executor, mock_credentials):
        """Teste: inicialização bem-sucedida"""
        
        # Mock CredentialsRepository
        with patch("app.trading.executor.CredentialsRepository.get_credentials") as mock_get_creds:
            # Mock decrypt
            with patch("app.trading.executor.decrypt_kucoin_credentials") as mock_decrypt:
                # Mock KuCoinRawClient
                with patch("app.trading.executor.KuCoinRawClient") as mock_client_class:
                    # Configurar mocks
                    mock_get_creds.return_value = mock_credentials
                    mock_decrypt.return_value = {
                        "api_key": "real_key",
                        "api_secret": "real_secret",
                        "passphrase": "real_passphrase"
                    }
                    
                    mock_client_instance = AsyncMock()
                    mock_client_class.return_value = mock_client_instance
                    mock_client_instance.get_server_time.return_value = 1234567890
                    mock_client_instance.get_accounts.return_value = [
                        {"id": "account_id_123", "type": "trading"}
                    ]
                    
                    # Execute
                    await executor.initialize()
                    
                    # Assertions
                    assert executor.client is not None
                    assert executor.account_id == "account_id_123"
                    assert executor.credentials is not None
                    
                    mock_client_instance.get_server_time.assert_called_once()
                    mock_client_instance.get_accounts.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_initialize_no_credentials(self, executor):
        """Teste: sem credenciais configuradas"""
        
        with patch("app.trading.executor.CredentialsRepository.get_credentials") as mock_get:
            mock_get.return_value = None
            
            with pytest.raises(PermissionError, match="Nenhuma credencial"):
                await executor.initialize()
    
    @pytest.mark.asyncio
    async def test_initialize_no_accounts(self, executor, mock_credentials):
        """Teste: nenhuma conta encontrada"""
        
        with patch("app.trading.executor.CredentialsRepository.get_credentials") as mock_get_creds:
            with patch("app.trading.executor.decrypt_kucoin_credentials") as mock_decrypt:
                with patch("app.trading.executor.KuCoinRawClient") as mock_client_class:
                    mock_get_creds.return_value = mock_credentials
                    mock_decrypt.return_value = {
                        "api_key": "key",
                        "api_secret": "secret",
                        "passphrase": "pass"
                    }
                    
                    mock_client_instance = AsyncMock()
                    mock_client_class.return_value = mock_client_instance
                    mock_client_instance.get_server_time.return_value = 1234567890
                    mock_client_instance.get_accounts.return_value = []  # ← Nenhuma conta
                    
                    with pytest.raises(ValueError, match="Nenhuma conta encontrada"):
                        await executor.initialize()


class TestValidateOrder:
    """Testes de validação pré-trade"""
    
    @pytest.mark.asyncio
    async def test_validate_order_success(self, executor):
        """Teste: validação bem-sucedida"""
        
        with patch.object(executor.circuit_breaker, "pre_request"):
            with patch.object(executor.risk_manager, "is_kill_switched") as mock_killed:
                with patch.object(executor.risk_manager, "check_can_trade") as mock_check:
                    mock_killed.return_value = False
                    mock_check.return_value = (True, None)
                    
                    is_valid, error = await executor._validate_order(
                        symbol="BTC-USDT",
                        side="buy",
                        quantity=Decimal("0.1")
                    )
                    
                    assert is_valid is True
                    assert error is None
    
    @pytest.mark.asyncio
    async def test_validate_order_kill_switch_active(self, executor):
        """Teste: kill-switch ativo"""
        
        with patch.object(executor.circuit_breaker, "pre_request"):
            with patch.object(executor.risk_manager, "is_kill_switched") as mock_killed:
                mock_killed.return_value = True
                
                is_valid, error = await executor._validate_order(
                    symbol="BTC-USDT",
                    side="buy",
                    quantity=Decimal("0.1")
                )
                
                assert is_valid is False
                assert "Kill-switch" in error


class TestPersistPendingOrder:
    """Testes de persistência idempotente"""
    
    @pytest.mark.asyncio
    async def test_persist_pending_order_creates_doc(self, executor):
        """Teste: cria documento com client_oid"""
        
        # Mock generate_client_oid
        with patch("app.trading.executor.generate_client_oid") as mock_gen_oid:
            mock_gen_oid.return_value = "fake_client_oid_123"
            
            # Mock MongoDB insert
            with patch.object(executor.db.trading_orders, "insert_one") as mock_insert:
                mock_insert.return_value = MagicMock(inserted_id=ObjectId())
                
                # Execute
                order_db = await executor._persist_pending_order(
                    symbol="BTC-USDT",
                    side="buy",
                    quantity=Decimal("0.1")
                )
                
                # Assertions
                assert order_db["client_oid"] == "fake_client_oid_123"
                assert order_db["symbol"] == "BTC-USDT"
                assert order_db["side"] == "buy"
                assert order_db["quantity"] == Decimal("0.1")
                assert order_db["status"] == "pending"
                assert order_db["user_id"] == "test_user_123"
                
                mock_insert.assert_called_once()


class TestPlaceAtExchange:
    """Testes de envio para exchange"""
    
    @pytest.mark.asyncio
    async def test_place_at_exchange_success(self, executor, mock_normalized_order):
        """Teste: envio bem-sucedido"""
        
        executor.client = AsyncMock()
        executor.client.place_market_order.return_value = mock_normalized_order
        
        with patch.object(executor.db.trading_orders, "update_one") as mock_update:
            order_db = {
                "_id": ObjectId(),
                "symbol": "BTC-USDT",
                "side": "buy",
                "quantity": Decimal("0.1"),
                "client_oid": "oid_123"
            }
            
            result = await executor._place_at_exchange(order_db)
            
            assert result.order_id == "fake_order_id_123"
            mock_update.assert_called_once()  # Atualizar com exchange_order_id


class TestMonitorUntilFilled:
    """Testes de monitoramento de preenchimento"""
    
    @pytest.mark.asyncio
    async def test_monitor_until_filled_success(self, executor, mock_normalized_order):
        """Teste: ordem preenchida na primeira tentativa"""
        
        executor.client = AsyncMock()
        executor.client.get_order.return_value = mock_normalized_order
        
        result = await executor._monitor_until_filled(mock_normalized_order, max_attempts=3)
        
        assert result.order_id == "fake_order_id_123"
        assert result.status == "FILLED"
        executor.client.get_order.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_monitor_until_filled_timeout(self, executor, mock_normalized_order):
        """Teste: timeout (não preencheu em tempo)"""
        
        # Mock ordem sempre em PENDING
        pending_order = MagicMock()
        pending_order.order_id = "fake_order_id_123"
        pending_order.status = "OPEN"
        pending_order.filled_qty = Decimal("0")
        pending_order.size = Decimal("0.1")
        
        executor.client = AsyncMock()
        executor.client.get_order.return_value = pending_order
        executor.polling_interval = 0.01  # Muito rápido para testes
        
        with pytest.raises(ExchangeTimeoutError):
            await executor._monitor_until_filled(mock_normalized_order, max_attempts=2)


class TestSyncToDatabase:
    """Testes de sincronização final"""
    
    @pytest.mark.asyncio
    async def test_sync_to_database_updates_order(self, executor, mock_normalized_order):
        """Teste: sincroniza resultado no banco"""
        
        order_db = {
            "_id": ObjectId(),
            "status": "pending"
        }
        
        with patch.object(executor.db.trading_orders, "update_one") as mock_update:
            await executor._sync_to_database(mock_normalized_order, order_db)
            
            # Verificar que update foi chamado
            mock_update.assert_called_once()
            
            # Pegar argumento da chamada
            call_args = mock_update.call_args
            filter_doc = call_args[0][0]
            update_doc = call_args[0][1]
            
            # Assertions
            assert filter_doc["_id"] == order_db["_id"]
            assert update_doc["$set"]["status"] == "filled"
            assert update_doc["$set"]["exchange_order_id"] == "fake_order_id_123"


class TestExecuteMarketOrder:
    """Testes de execução completa (integração menor)"""
    
    @pytest.mark.asyncio
    async def test_execute_market_order_not_initialized(self, executor):
        """Teste: erro se não inicializado"""
        
        executor.client = None  # Não inicializado
        
        with pytest.raises(RuntimeError, match="não foi inicializado"):
            await executor.execute_market_order(
                symbol="BTC-USDT",
                side="buy",
                quantity=Decimal("0.1")
            )
    
    @pytest.mark.asyncio
    async def test_execute_market_order_validation_fails(self, executor):
        """Teste: falha na validação pré-trade"""
        
        executor.client = AsyncMock()
        
        with patch.object(executor, "_validate_order") as mock_validate:
            mock_validate.return_value = (False, "Saldo insuficiente")
            
            with pytest.raises(ValidationFailedError):
                await executor.execute_market_order(
                    symbol="BTC-USDT",
                    side="buy",
                    quantity=Decimal("0.1")
                )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
