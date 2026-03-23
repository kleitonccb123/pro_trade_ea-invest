"""
monitoring — DOC-08: Sistema de Monitoramento e Logs

Pacote principal de observabilidade operacional.

Exportações:
  metrics   — Prometheus metrics (crypto_* prefix, REGISTRY separado)
  audit_log — log_financial_event() + create_audit_indexes()
  alerting  — TelegramAlerter, AlertLevel, funções de alerta
  health    — router FastAPI com /health e /health/detailed
"""
