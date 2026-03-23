"""
Unit tests for Task 3.2 (Circuit Breaker Service) and Task 3.3 (Monitoring & Alertas)

Tests validate:
✅ CircuitBreakerService lifecycle (start/stop)
✅ Health probe success/failure recording
✅ State transition detection + alert dispatch
✅ Prometheus metrics updates
✅ AlertManager send/cooldown/query
✅ AlertManager multi-channel dispatch (log, webhook, database)
✅ AlertManager acknowledge
✅ Integration: CB events → AlertManager
✅ System dashboard endpoint consolidation
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, ANY
from datetime import datetime, timedelta

from app.trading.circuit_breaker import CircuitState, ExchangeHealthMonitor
from app.trading.circuit_breaker_service import (
    CircuitBreakerService,
    init_circuit_breaker_service,
    shutdown_circuit_breaker_service,
    get_circuit_breaker_service,
)
from app.observability.alert_manager import (
    Alert,
    AlertChannel,
    AlertManager,
    AlertSeverity,
    init_alert_manager,
    get_alert_manager,
)


# ============================================================================
#  FIXTURES
# ============================================================================

@pytest.fixture
def cb_service():
    """Cria CircuitBreakerService sem iniciar background tasks."""
    svc = CircuitBreakerService(
        exchange="kucoin_test",
        probe_interval_s=1.0,
        probe_timeout_s=2.0,
        failure_threshold=3,
        success_threshold=1,
        recovery_timeout_s=5.0,
    )
    return svc


@pytest.fixture
def alert_manager():
    """AlertManager sem webhook e sem DB."""
    return AlertManager(
        webhook_url=None,
        db=None,
        cooldown_s=5.0,
    )


@pytest.fixture
def alert_manager_with_db():
    """AlertManager com mock de DB."""
    mock_db = MagicMock()
    mock_db.system_alerts = AsyncMock()
    mock_db.system_alerts.insert_one = AsyncMock()
    return AlertManager(
        webhook_url=None,
        db=mock_db,
        cooldown_s=5.0,
    )


# ============================================================================
#  TASK 3.2 — CircuitBreakerService
# ============================================================================

class TestCircuitBreakerServiceInit:
    """Testes de inicialização do CircuitBreakerService."""

    def test_creates_with_defaults(self, cb_service):
        assert cb_service.exchange == "kucoin_test"
        assert cb_service.probe_interval_s == 1.0
        assert cb_service.probe_timeout_s == 2.0
        assert cb_service._running is False
        assert cb_service._probe_task is None
        assert isinstance(cb_service.monitor, ExchangeHealthMonitor)

    def test_initial_state_is_closed(self, cb_service):
        assert cb_service.monitor.state == CircuitState.CLOSED

    def test_no_events_initially(self, cb_service):
        assert cb_service._event_log == []

    def test_no_callbacks_initially(self, cb_service):
        assert cb_service._alert_callbacks == []


class TestCircuitBreakerServiceLifecycle:
    """Testes de lifecycle (start/stop)."""

    @pytest.mark.asyncio
    async def test_start_sets_running(self, cb_service):
        with patch.object(cb_service, "_probe_loop", new_callable=AsyncMock):
            await cb_service.start()
            assert cb_service._running is True
            assert cb_service._probe_task is not None
            await cb_service.stop()

    @pytest.mark.asyncio
    async def test_stop_cancels_task(self, cb_service):
        with patch.object(cb_service, "_probe_loop", new_callable=AsyncMock):
            await cb_service.start()
            await cb_service.stop()
            assert cb_service._running is False

    @pytest.mark.asyncio
    async def test_double_start_is_noop(self, cb_service):
        with patch.object(cb_service, "_probe_loop", new_callable=AsyncMock) as mock_probe:
            await cb_service.start()
            task1 = cb_service._probe_task
            await cb_service.start()
            task2 = cb_service._probe_task
            assert task1 is task2
            await cb_service.stop()


class TestCircuitBreakerStateTransitions:
    """Testes de transitions CLOSED → OPEN → HALF_OPEN → CLOSED."""

    @pytest.mark.asyncio
    async def test_record_failures_opens_circuit(self, cb_service):
        for i in range(3):
            cb_service.record_failure(Exception(f"fail_{i}"))
        await asyncio.sleep(0.05)
        assert cb_service.monitor.state == CircuitState.OPEN

    def test_record_success_in_closed(self, cb_service):
        cb_service.record_success()
        assert cb_service.monitor.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_state_transition_dispatches_alert(self, cb_service):
        callback = AsyncMock()
        cb_service.on_alert(callback)

        # Trigger CLOSED → OPEN
        for i in range(3):
            cb_service.record_failure(Exception(f"fail_{i}"))

        # Allow alert task to run
        await asyncio.sleep(0.1)

        callback.assert_called()
        event_type, event = callback.call_args[0]
        assert event_type == "circuit_opened"
        assert event["exchange"] == "kucoin_test"

    @pytest.mark.asyncio
    async def test_pre_request_raises_when_open(self, cb_service):
        from app.trading.circuit_breaker import CircuitOpenError

        for i in range(3):
            cb_service.record_failure(Exception(f"fail_{i}"))
        await asyncio.sleep(0.05)

        with pytest.raises(CircuitOpenError):
            cb_service.pre_request()


class TestCircuitBreakerGuard:
    """Testes do guard (execução protegida)."""

    @pytest.mark.asyncio
    async def test_guard_success(self, cb_service):
        async def my_fn():
            return "ok"

        result = await cb_service.guard(my_fn)
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_guard_failure_records(self, cb_service):
        async def my_fn():
            raise ValueError("boom")

        with pytest.raises(ValueError):
            await cb_service.guard(my_fn)

        # Should have recorded a failure
        assert cb_service.monitor._consecutive_fails >= 1

    @pytest.mark.asyncio
    async def test_guard_circuit_open_raises(self, cb_service):
        from app.trading.circuit_breaker import CircuitOpenError

        for i in range(3):
            cb_service.record_failure(Exception("fail"))

        async def my_fn():
            return "should_not_reach"

        with pytest.raises(CircuitOpenError):
            await cb_service.guard(my_fn)


class TestCircuitBreakerHealthProbe:
    """Testes de health probe."""

    @pytest.mark.asyncio
    async def test_successful_probe_records_success(self, cb_service):
        with patch.object(cb_service, "_ping_exchange", return_value=True):
            await cb_service._run_probe()
            # State should stay CLOSED
            assert cb_service.monitor.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_failed_probe_records_failure(self, cb_service):
        with patch.object(cb_service, "_ping_exchange", return_value=False):
            for _ in range(3):
                await cb_service._run_probe()
                cb_service._check_state_transition()
            assert cb_service.monitor.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_probe_exception_records_failure(self, cb_service):
        with patch.object(
            cb_service, "_ping_exchange", side_effect=Exception("timeout")
        ):
            for _ in range(3):
                await cb_service._run_probe()
                cb_service._check_state_transition()
            assert cb_service.monitor.state == CircuitState.OPEN


class TestCircuitBreakerStatus:
    """Testes do status / dashboard."""

    def test_status_returns_dict(self, cb_service):
        status = cb_service.status()
        assert "exchange" in status
        assert status["exchange"] == "kucoin_test"
        assert "state" in status
        assert status["state"] == "closed"
        assert "running" in status
        assert "recent_events" in status

    @pytest.mark.asyncio
    async def test_status_after_failures(self, cb_service):
        for i in range(3):
            cb_service.record_failure(Exception("fail"))
        await asyncio.sleep(0.05)
        status = cb_service.status()
        assert status["state"] == "open"
        assert status["consecutive_fails"] >= 3


class TestCircuitBreakerPrometheusMetrics:
    """Testes de integração com Prometheus."""

    def test_update_metrics_graceful_without_prometheus(self, cb_service):
        # Should not raise even if Prometheus not available
        with patch(
            "app.trading.circuit_breaker_service._HAS_PROMETHEUS", False
        ):
            cb_service._update_metrics()  # noop, no crash

    def test_update_metrics_with_prometheus(self, cb_service):
        mock_gauge = MagicMock()
        mock_gauge.labels.return_value.set = MagicMock()

        with patch(
            "app.trading.circuit_breaker_service._HAS_PROMETHEUS", True
        ), patch(
            "app.trading.circuit_breaker_service.trading_circuit_breaker_state",
            mock_gauge,
        ):
            cb_service._update_metrics()
            mock_gauge.labels.assert_called_with(service="kucoin_test")
            mock_gauge.labels.return_value.set.assert_called_with(0)  # CLOSED=0


class TestCircuitBreakerServiceSingleton:
    """Testes do padrão singleton."""

    @pytest.mark.asyncio
    async def test_init_and_get(self):
        with patch.object(
            CircuitBreakerService, "_probe_loop", new_callable=AsyncMock
        ):
            svc = await init_circuit_breaker_service(
                exchange="test_singleton",
                probe_interval_s=1.0,
            )
            assert svc is not None
            assert get_circuit_breaker_service() is svc
            await shutdown_circuit_breaker_service()
            assert get_circuit_breaker_service() is None

    @pytest.mark.asyncio
    async def test_init_with_callback(self):
        callback = MagicMock()
        with patch.object(
            CircuitBreakerService, "_probe_loop", new_callable=AsyncMock
        ):
            svc = await init_circuit_breaker_service(
                exchange="test_cb",
                alert_callback=callback,
            )
            assert callback in svc._alert_callbacks
            await shutdown_circuit_breaker_service()


# ============================================================================
#  TASK 3.3 — AlertManager
# ============================================================================

class TestAlertCreation:
    """Testes de criação de Alert."""

    def test_alert_has_unique_id(self):
        a1 = Alert(AlertSeverity.INFO, "Test 1", "msg1")
        a2 = Alert(AlertSeverity.INFO, "Test 2", "msg2")
        assert a1.id != a2.id

    def test_alert_to_dict(self):
        a = Alert(
            AlertSeverity.CRITICAL,
            "Circuit Open",
            "KuCoin down",
            component="circuit_breaker",
            metadata={"exchange": "kucoin"},
        )
        d = a.to_dict()
        assert d["severity"] == "critical"
        assert d["title"] == "Circuit Open"
        assert d["component"] == "circuit_breaker"
        assert d["metadata"]["exchange"] == "kucoin"
        assert d["acknowledged"] is False

    def test_alert_timestamp(self):
        before = datetime.utcnow()
        a = Alert(AlertSeverity.INFO, "t", "m")
        after = datetime.utcnow()
        assert before <= a.timestamp <= after


class TestAlertManagerSend:
    """Testes de envio de alertas."""

    @pytest.mark.asyncio
    async def test_send_returns_alert(self, alert_manager):
        alert = await alert_manager.send(
            AlertSeverity.WARNING,
            "Test Alert",
            "Something happened",
            component="test",
        )
        assert alert is not None
        assert alert.severity == AlertSeverity.WARNING
        assert alert.title == "Test Alert"

    @pytest.mark.asyncio
    async def test_send_stores_in_history(self, alert_manager):
        await alert_manager.send(AlertSeverity.INFO, "t1", "m1")
        await alert_manager.send(AlertSeverity.WARNING, "t2", "m2")
        assert len(alert_manager._alerts) == 2

    @pytest.mark.asyncio
    async def test_send_increments_counter(self, alert_manager):
        await alert_manager.send(AlertSeverity.INFO, "t", "m")
        assert alert_manager._total_sent == 1

    @pytest.mark.asyncio
    async def test_send_log_channel_always_active(self, alert_manager):
        alert = await alert_manager.send(AlertSeverity.INFO, "t", "m")
        assert AlertChannel.LOG.value in alert.channels_sent


class TestAlertManagerCooldown:
    """Testes de cooldown (anti-spam)."""

    @pytest.mark.asyncio
    async def test_duplicate_suppressed(self, alert_manager):
        a1 = await alert_manager.send(AlertSeverity.WARNING, "Same Title", "m1", component="cb")
        a2 = await alert_manager.send(AlertSeverity.WARNING, "Same Title", "m2", component="cb")
        assert a1 is not None
        assert a2 is None
        assert alert_manager._total_suppressed == 1

    @pytest.mark.asyncio
    async def test_different_alerts_not_suppressed(self, alert_manager):
        a1 = await alert_manager.send(AlertSeverity.WARNING, "Title A", "m1")
        a2 = await alert_manager.send(AlertSeverity.WARNING, "Title B", "m2")
        assert a1 is not None
        assert a2 is not None

    @pytest.mark.asyncio
    async def test_cooldown_expires(self, alert_manager):
        alert_manager._cooldown_s = 0.1
        await alert_manager.send(AlertSeverity.INFO, "Expire Test", "m1")
        await asyncio.sleep(0.15)
        a2 = await alert_manager.send(AlertSeverity.INFO, "Expire Test", "m2")
        assert a2 is not None

    def test_cleanup_cooldowns(self, alert_manager):
        # Manually set old cooldown
        alert_manager._cooldowns["old:key:comp"] = datetime.utcnow() - timedelta(seconds=9999)
        alert_manager._cooldowns["new:key:comp"] = datetime.utcnow()
        alert_manager._cleanup_cooldowns()
        assert "old:key:comp" not in alert_manager._cooldowns
        assert "new:key:comp" in alert_manager._cooldowns


class TestAlertManagerConvenience:
    """Testes dos métodos de conveniência."""

    @pytest.mark.asyncio
    async def test_info(self, alert_manager):
        a = await alert_manager.info("Info Title", "info msg")
        assert a.severity == AlertSeverity.INFO

    @pytest.mark.asyncio
    async def test_warning(self, alert_manager):
        a = await alert_manager.warning("Warn Title", "warn msg")
        assert a.severity == AlertSeverity.WARNING

    @pytest.mark.asyncio
    async def test_critical(self, alert_manager):
        a = await alert_manager.critical("Crit Title", "crit msg")
        assert a.severity == AlertSeverity.CRITICAL

    @pytest.mark.asyncio
    async def test_emergency(self, alert_manager):
        a = await alert_manager.emergency("Emerg Title", "emerg msg")
        assert a.severity == AlertSeverity.EMERGENCY


class TestAlertManagerDatabase:
    """Testes de persistência em MongoDB."""

    @pytest.mark.asyncio
    async def test_alert_persisted_to_db(self, alert_manager_with_db):
        mgr = alert_manager_with_db
        alert = await mgr.send(AlertSeverity.CRITICAL, "DB Test", "msg")
        mgr._db.system_alerts.insert_one.assert_called_once()
        assert AlertChannel.DATABASE.value in alert.channels_sent

    @pytest.mark.asyncio
    async def test_db_error_does_not_crash(self):
        mock_db = MagicMock()
        mock_db.system_alerts = AsyncMock()
        mock_db.system_alerts.insert_one = AsyncMock(
            side_effect=Exception("DB down")
        )
        mgr = AlertManager(db=mock_db, cooldown_s=0)
        alert = await mgr.send(AlertSeverity.INFO, "t", "m")
        # Should still succeed (alert created, but DB channel failed)
        assert alert is not None
        assert AlertChannel.DATABASE.value not in alert.channels_sent


class TestAlertManagerWebhook:
    """Testes de webhook."""

    @pytest.mark.asyncio
    async def test_webhook_skipped_when_no_url(self, alert_manager):
        alert = await alert_manager.send(AlertSeverity.INFO, "t", "m")
        assert AlertChannel.WEBHOOK.value not in alert.channels_sent

    @pytest.mark.asyncio
    async def test_webhook_called_with_url(self):
        mgr = AlertManager(webhook_url="https://example.com/hook", cooldown_s=0)

        # Mock the entire _dispatch_webhook to confirm it was called and mark channel
        original = mgr._dispatch_webhook

        async def mock_dispatch_webhook(alert):
            alert.channels_sent.append(AlertChannel.WEBHOOK.value)

        mgr._dispatch_webhook = mock_dispatch_webhook
        alert = await mgr.send(AlertSeverity.CRITICAL, "Webhook Test", "msg")
        assert AlertChannel.WEBHOOK.value in alert.channels_sent


class TestAlertManagerQuery:
    """Testes de consulta (dashboard)."""

    @pytest.mark.asyncio
    async def test_get_recent(self, alert_manager):
        alert_manager._cooldown_s = 0
        for i in range(5):
            await alert_manager.send(AlertSeverity.INFO, f"Alert {i}", "m")
        recent = alert_manager.get_recent(3)
        assert len(recent) == 3
        assert recent[-1]["title"] == "Alert 4"

    @pytest.mark.asyncio
    async def test_get_by_severity(self, alert_manager):
        alert_manager._cooldown_s = 0
        await alert_manager.send(AlertSeverity.INFO, "I1", "m")
        await alert_manager.send(AlertSeverity.CRITICAL, "C1", "m")
        await alert_manager.send(AlertSeverity.INFO, "I2", "m")
        crits = alert_manager.get_by_severity(AlertSeverity.CRITICAL)
        assert len(crits) == 1
        assert crits[0]["title"] == "C1"

    @pytest.mark.asyncio
    async def test_get_unacknowledged(self, alert_manager):
        alert_manager._cooldown_s = 0
        a1 = await alert_manager.send(AlertSeverity.INFO, "A1", "m")
        a2 = await alert_manager.send(AlertSeverity.INFO, "A2", "m")
        alert_manager.acknowledge(a1.id)
        unack = alert_manager.get_unacknowledged()
        assert len(unack) == 1
        assert unack[0]["title"] == "A2"


class TestAlertManagerAcknowledge:
    """Testes de acknowledge."""

    @pytest.mark.asyncio
    async def test_acknowledge_valid_id(self, alert_manager):
        alert = await alert_manager.send(AlertSeverity.INFO, "t", "m")
        assert alert_manager.acknowledge(alert.id) is True
        assert alert.acknowledged is True

    @pytest.mark.asyncio
    async def test_acknowledge_invalid_id(self, alert_manager):
        assert alert_manager.acknowledge("nonexistent_id") is False


class TestAlertManagerStats:
    """Testes de estatísticas."""

    @pytest.mark.asyncio
    async def test_stats_empty(self, alert_manager):
        stats = alert_manager.stats()
        assert stats["total_sent"] == 0
        assert stats["total_suppressed"] == 0
        assert stats["in_memory"] == 0

    @pytest.mark.asyncio
    async def test_stats_after_sends(self, alert_manager):
        alert_manager._cooldown_s = 0
        await alert_manager.send(AlertSeverity.INFO, "t1", "m")
        await alert_manager.send(AlertSeverity.CRITICAL, "t2", "m")
        stats = alert_manager.stats()
        assert stats["total_sent"] == 2
        assert stats["by_severity"]["info"] == 1
        assert stats["by_severity"]["critical"] == 1

    @pytest.mark.asyncio
    async def test_stats_includes_suppressed(self, alert_manager):
        await alert_manager.send(AlertSeverity.INFO, "dup", "m")
        await alert_manager.send(AlertSeverity.INFO, "dup", "m")
        stats = alert_manager.stats()
        assert stats["total_sent"] == 1
        assert stats["total_suppressed"] == 1


class TestAlertManagerMaxHistory:
    """Testes de limite de histórico."""

    @pytest.mark.asyncio
    async def test_history_truncation(self):
        mgr = AlertManager(max_history=5, cooldown_s=0)
        for i in range(10):
            await mgr.send(AlertSeverity.INFO, f"Alert {i}", "m")
        assert len(mgr._alerts) == 5
        # Most recent should be the last
        assert mgr._alerts[-1].title == "Alert 9"


class TestAlertManagerSingleton:
    """Testes do padrão singleton global."""

    def test_init_and_get(self):
        mgr = init_alert_manager(cooldown_s=1.0)
        assert mgr is not None
        assert get_alert_manager() is mgr


# ============================================================================
#  INTEGRATION: Circuit Breaker → AlertManager
# ============================================================================

class TestCircuitBreakerAlertIntegration:
    """
    Testa que quando o circuit breaker abre,
    um alerta é disparado via AlertManager.
    """

    @pytest.mark.asyncio
    async def test_cb_open_triggers_alert(self, cb_service, alert_manager):
        """Simula: 3 falhas → circuit opens → alert sent."""
        alerts_received = []

        async def alert_handler(event_type, details):
            alerts_received.append((event_type, details))

        cb_service.on_alert(alert_handler)

        # Trigger failures
        for i in range(3):
            cb_service.record_failure(Exception(f"fail_{i}"))

        # Allow async tasks to complete
        await asyncio.sleep(0.2)

        assert len(alerts_received) >= 1
        event_type, details = alerts_received[0]
        assert event_type == "circuit_opened"

    @pytest.mark.asyncio
    async def test_cb_recovery_triggers_alert(self, cb_service):
        """Simula: circuit abre → recovery → alert de fechamento."""
        alerts_received = []

        async def alert_handler(event_type, details):
            alerts_received.append((event_type, details))

        cb_service.on_alert(alert_handler)

        # Open circuit
        for i in range(3):
            cb_service.record_failure(Exception("fail"))

        await asyncio.sleep(0.1)

        # Force transition to HALF_OPEN by resetting timeout
        cb_service.monitor._opened_at = 0

        # Record success to close it
        cb_service.record_success()

        await asyncio.sleep(0.2)

        types = [et for et, _ in alerts_received]
        assert "circuit_opened" in types
        # Should also have half_open or closed
        assert any(t in types for t in ("circuit_closed", "circuit_half_open"))

    @pytest.mark.asyncio
    async def test_cb_to_alert_manager_pipeline(self, cb_service, alert_manager):
        """
        Pipeline completo:
        CB state change → callback → AlertManager.send()
        """
        async def cb_to_alert(event_type, details):
            severity = (
                AlertSeverity.CRITICAL
                if event_type == "circuit_opened"
                else AlertSeverity.INFO
            )
            await alert_manager.send(
                severity=severity,
                title=f"CB: {event_type}",
                message=str(details),
                component="circuit_breaker",
            )

        cb_service.on_alert(cb_to_alert)

        # Trigger circuit opening
        for i in range(3):
            cb_service.record_failure(Exception("fail"))
        await asyncio.sleep(0.2)

        # Verify alert manager received it
        crits = alert_manager.get_by_severity(AlertSeverity.CRITICAL)
        assert len(crits) >= 1
        assert "circuit_opened" in crits[0]["title"]
