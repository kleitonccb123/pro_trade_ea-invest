"""
strategy_registry.py
DOC-STRAT-10 | Crypto Trade Hub — SaaS Strategy Registry

Registro central de todas as estratégias SaaS disponíveis.
Cada entry mapeia um strategy_id para:
  - classe Python que implementa SaaSStrategyModule
  - magic_number do EA no MetaTrader 5
  - metadados operacionais e de segurança

Para adicionar uma nova estratégia:
  1. Criar <nome>_module.py em backend/app/bots/ seguindo PriceProMoneyModule
  2. Adicionar entry em STRATEGY_REGISTRY abaixo
  3. Adicionar entry em BOT_MAGIC_NUMBERS em strategy_manager.py
  4. Registrar o strategy_id no MongoDB (coleção 'strategies')
  5. Compilar e instalar o EA .mq5 correspondente no MT5
"""

from typing import Dict, Any

from app.bots.strategy_base import SaaSStrategyModule
from app.bots.pricepro_money_module import PriceProMoneyModule

# ─────────────────────────────────────────────────────────────────────────────
# REGISTRY PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────
STRATEGY_REGISTRY: Dict[str, Dict[str, Any]] = {
    "pricepro_money_v1": {
        # Classe Python responsável por controlar este EA
        "class": PriceProMoneyModule,

        # Magic number exclusivo usado pelo EA no MT5 (deve coincidir com #define MAGIC_NUMBER)
        "magic_number": 20240001,

        # Metadados exibidos no frontend / painel admin
        "display_name": "PRICEPRO MONEY",
        "version": "1.0",

        # Limites operacionais de segurança (usados pelo backend durante trocas)
        "min_switch_interval_s": 60,       # Mínimo de segundos entre trocas de estratégia
        "safe_shutdown_timeout_s": 120,    # Tempo máximo para risco zero antes de forçar troca
        "handshake_timeout_s": 30,         # Tempo máximo para EA responder ao backend no boot
    },

    # ─── Adicionar novas estratégias aqui seguindo o padrão acima ───────────
    # "nova_estrategia_v1": {
    #     "class": NovaEstrategiaModule,
    #     "magic_number": 20240002,
    #     "display_name": "NOVA ESTRATÉGIA",
    #     "version": "1.0",
    #     "min_switch_interval_s": 60,
    #     "safe_shutdown_timeout_s": 120,
    #     "handshake_timeout_s": 30,
    # },
}


# ─────────────────────────────────────────────────────────────────────────────
# FACTORY — instancia o módulo correto para um usuário
# ─────────────────────────────────────────────────────────────────────────────
def get_strategy_module(strategy_id: str, user_id: str) -> SaaSStrategyModule:
    """
    Retorna uma instância do SaaSStrategyModule para a estratégia e usuário dados.

    Args:
        strategy_id: ID da estratégia (ex: "pricepro_money_v1")
        user_id:     ID do usuário no sistema (usado para montar caminhos de arquivo)

    Returns:
        Instância de SaaSStrategyModule pronta para uso.

    Raises:
        ValueError: Se strategy_id não estiver registrado em STRATEGY_REGISTRY.
    """
    entry = STRATEGY_REGISTRY.get(strategy_id)
    if not entry:
        raise ValueError(
            f"Estratégia '{strategy_id}' não registrada no SaaS. "
            f"Estratégias disponíveis: {list(STRATEGY_REGISTRY.keys())}"
        )
    return entry["class"](user_id)


def get_strategy_metadata(strategy_id: str) -> Dict[str, Any]:
    """
    Retorna os metadados de uma estratégia sem instanciar o módulo.

    Args:
        strategy_id: ID da estratégia

    Returns:
        Dict com magic_number, display_name, version, timeouts, etc.

    Raises:
        ValueError: Se strategy_id não estiver registrado.
    """
    entry = STRATEGY_REGISTRY.get(strategy_id)
    if not entry:
        raise ValueError(
            f"Estratégia '{strategy_id}' não registrada no SaaS. "
            f"Estratégias disponíveis: {list(STRATEGY_REGISTRY.keys())}"
        )
    # Retornar cópia sem a referência à class para serialização segura
    return {k: v for k, v in entry.items() if k != "class"}


def list_strategy_ids() -> list:
    """Retorna lista de todos os strategy_ids registrados."""
    return list(STRATEGY_REGISTRY.keys())
