"""
EA Monitor Module — MetaTrader MT4/MT5 Integration

Endpoints REST (EA-side, autenticado via api_key):
    POST   /ea/connect                   Registra conta MT4/MT5; retorna api_key
    POST   /ea/{account_id}/update       EA pusha telemetria + posições
    DELETE /ea/{account_id}              Desconecta conta

Endpoints REST (frontend, autenticado via JWT):
    GET    /ea/accounts                  Lista contas conectadas do usuário
    GET    /ea/{account_id}/positions    Snapshot das posições abertas

WebSocket (frontend, autenticado via JWT):
    WS     /ws/ea/{account_id}           Stream em tempo real
"""

from app.ea_monitor import router

__all__ = ["router"]
