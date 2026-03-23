# CRYPTO TRADE HUB — DOCUMENTAÇÃO TÉCNICA DE ENGENHARIA
## Correções e Elevaçãoo a Nível Institucional (KuCoin Exclusivo)

> **Documento interno de engenharia. Classificação: CONFIDENCIAL.**
> Versão: 1.0 — Fevereiro 2026
> Arquitetura: Frontend SaaS → FastAPI Backend → Trading Engine (única instância) → KuCoin REST + WebSocket

---

## ÍNDICE

1. [DOC-K01 — Criptografia Obrigatória de API Key e Secret](#doc-k01)
2. [DOC-K02 — Rate Limiting com Headers Nativos gw-ratelimit da KuCoin](#doc-k02)
3. [DOC-K03 — Sincronização de Estado via WebSocket (Execution Reports)](#doc-k03)
4. [DOC-K04 — Idempotência de Ordens com clientOid e Persistência Pre-Send](#doc-k04)
5. [DOC-K05 — Take Profit e Stop Loss configuráveis via SaaS (TP/SL nativos)](#doc-k05)
6. [DOC-K06 — OCO (One-Cancels-the-Other) correto para Spot na KuCoin](#doc-k06)
7. [DOC-K07 — Kill Switch com Contagem Real de Posições Abertas](#doc-k07)
8. [DOC-K08 — Reconexão Automática de WebSocket e Resubscrição](#doc-k08)
9. [DOC-K09 — Consistência de Estado após Restart da Engine](#doc-k09)
10. [DOC-K10 — Race Condition entre Strategy → OrderManager → Exchange](#doc-k10)

---

<a id="doc-k01"></a>
# DOC-K01 — Criptografia Obrigatória de API Key e API Secret

## 🎯 Objetivo

Garantir que **nenhuma credencial KuCoin** (api_key, api_secret, api_passphrase) seja armazenada ou transmitida em texto plano em qualquer ponto do sistema — banco de dados, logs, Redis, memória serializada ou response de API.

---

## 🚨 Problema Técnico Atual

**Arquivo:** `backend/app/trading/service.py`, linha 40

```python
# ESTADO ATUAL — VULNERÁVEL:
'api_secret': credentials.api_secret,  # TODO: Encrypt this
```

A classe `CredentialEncryption` em `backend/app/security/credential_encryption.py` **existe e está correta** (usa Fernet simétrico), mas **não está conectada ao fluxo de salvamento e leitura de credenciais** no Worker nem no serviço de trading.

O `BotWorker` em `backend/app/engine/worker.py` lê:
```python
self._exchange = KuCoinClient(
    api_key=self.instance.get("decrypted_api_key", ""),
    api_secret=self.instance.get("decrypted_api_secret", ""),
    api_passphrase=self.instance.get("decrypted_api_passphrase", ""),
```

Esse campo `decrypted_api_key` só existirá se **algum componente upstream** fizer a descriptografia antes de chamar o worker. Se isso não ocorrer, o worker opera sem credenciais (string vazia), e todas as ordens falharão silenciosamente ou com erro de autenticação.

---

## 🔎 Risco Real em Produção

| Risco | Consequência |
|---|---|
| API Secret em texto plano no MongoDB | Qualquer dump de banco expõe acesso total à conta da exchange do usuário |
| API Secret em logs de debug | Logs em Sentry, Grafana ou stdout expõem o secret |
| Worker sem credenciais (campo vazio) | Ordens parecem estar sendo enviadas mas retornam 401 — posição fica sem controle |
| Secret visível em response de `/api/trading/credentials` | XSS ou MITM recupera o secret |

**Impacto financeiro direto:** roubo de posições abertas, ordens não autorizadas, perda total de capital do usuário.

---

## 🛠 Plano de Correção Passo a Passo

### Passo 1 — Configurar variável de ambiente

```bash
# Gerar chave Fernet (executar uma vez, guardar em .env.prod):
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Resultado: z2J8K...base64...=
```

```bash
# .env.prod (nunca no git)
CREDENTIAL_ENCRYPTION_KEY=z2J8K...base64...=
```

### Passo 2 — Singleton seguro do cipher

**Arquivo a criar:** `backend/app/security/cipher_singleton.py`

```python
"""
Singleton thread-safe do CredentialEncryption.
Inicializado uma vez no startup da aplicação.
"""
from __future__ import annotations
import os
from functools import lru_cache
from app.security.credential_encryption import CredentialEncryption, CredentialEncryptionError

@lru_cache(maxsize=1)
def get_cipher() -> CredentialEncryption:
    """
    Retorna instância única do cipher.
    Falha em startup se CREDENTIAL_ENCRYPTION_KEY não estiver configurada.
    """
    key = os.getenv("CREDENTIAL_ENCRYPTION_KEY")
    if not key:
        raise RuntimeError(
            "[STARTUP FATAL] CREDENTIAL_ENCRYPTION_KEY não configurada. "
            "Gere com: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    return CredentialEncryption(encryption_key=key)
```

### Passo 3 — Criptografar no momento do salvamento

**Arquivo:** `backend/app/trading/service.py` (ou router de credenciais KuCoin)

```python
from app.security.cipher_singleton import get_cipher
from app.security.credential_encryption import CredentialEncryptionError

async def save_kucoin_credentials(
    db,
    user_id: str,
    api_key: str,
    api_secret: str,
    api_passphrase: str,
    sandbox: bool = False,
) -> dict:
    """
    Salva credenciais KuCoin SEMPRE criptografadas.
    Nunca persiste texto plano.
    """
    cipher = get_cipher()

    try:
        encrypted = cipher.encrypt_credentials(api_key, api_secret, api_passphrase)
    except CredentialEncryptionError as e:
        raise ValueError(f"Falha ao criptografar credenciais: {e}") from e

    doc = {
        "user_id": user_id,
        "exchange": "kucoin",
        "sandbox": sandbox,
        # Armazenar APENAS campos criptografados
        "api_key_enc": encrypted["api_key_enc"],
        "api_secret_enc": encrypted["api_secret_enc"],
        "passphrase_enc": encrypted["passphrase_enc"],
        "algorithm": "fernet",
        # NUNCA armazenar: api_key, api_secret, api_passphrase em texto plano
    }

    await db["exchange_credentials"].update_one(
        {"user_id": user_id, "exchange": "kucoin"},
        {"$set": doc},
        upsert=True,
    )
    return {"status": "saved", "exchange": "kucoin", "sandbox": sandbox}
```

### Passo 4 — Descriptografar antes de passar ao Worker

**Arquivo:** `backend/app/engine/orchestrator.py` — método que inicia o worker

```python
from app.security.cipher_singleton import get_cipher
from app.security.credential_encryption import CredentialEncryptionError

async def _load_decrypted_instance(self, db, instance: dict) -> dict:
    """
    Carrega as credenciais criptografadas do banco e injeta os campos
    decrypted_* no dict do instance para uso pelo BotWorker.

    Os campos decrypted_* existem apenas em memória — nunca são persistidos.
    """
    user_id = instance["user_id"]

    creds_doc = await db["exchange_credentials"].find_one(
        {"user_id": user_id, "exchange": "kucoin"}
    )
    if not creds_doc:
        raise ValueError(f"Credenciais KuCoin não encontradas para user {user_id}")

    cipher = get_cipher()
    try:
        decrypted = cipher.decrypt_credentials(
            api_key_enc=creds_doc["api_key_enc"],
            api_secret_enc=creds_doc["api_secret_enc"],
            passphrase_enc=creds_doc["passphrase_enc"],
        )
    except CredentialEncryptionError as e:
        raise RuntimeError(
            f"Falha ao descriptografar credenciais para user {user_id}: {e}"
        ) from e

    # Injetar em memória — NUNCA salvar de volta
    instance_copy = dict(instance)
    instance_copy["decrypted_api_key"]        = decrypted["api_key"]
    instance_copy["decrypted_api_secret"]     = decrypted["api_secret"]
    instance_copy["decrypted_api_passphrase"] = decrypted["passphrase"]

    return instance_copy
```

### Passo 5 — Sanitizar logs

**Arquivo:** `backend/app/security/log_sanitizer.py` (já existe — verificar se cobre os campos abaixo)

```python
# Garantir que esses padrões sejam mascarados em TODOS os logs:
SENSITIVE_PATTERNS = [
    r"KC-API-KEY:\s*\S+",
    r"KC-API-SIGN:\s*\S+",
    r"KC-API-PASSPHRASE:\s*\S+",
    r"api_secret[\"']?\s*[:=]\s*[\"']?[A-Za-z0-9+/=\-_]{20,}",
    r"api_key[\"']?\s*[:=]\s*[\"']?[A-Za-z0-9\-]{20,}",
    r"passphrase[\"']?\s*[:=]\s*[\"']?.{8,}",
]
```

---

## 📂 Arquivos a Modificar

| Arquivo | Mudança |
|---|---|
| `backend/app/security/cipher_singleton.py` | CRIAR — singleton do cipher |
| `backend/app/trading/service.py` | Substituir TODO por chamada ao cipher |
| `backend/app/engine/orchestrator.py` | Adicionar `_load_decrypted_instance()` |
| `backend/app/security/log_sanitizer.py` | Validar cobertura de padrões KC-API-* |
| `.env.prod.example` | Documentar CREDENTIAL_ENCRYPTION_KEY |

---

## 🧪 Estratégia de Testes

```python
# tests/test_credential_encryption.py

import pytest
from app.security.credential_encryption import CredentialEncryption

def test_roundtrip():
    key = CredentialEncryption.generate_key()
    cipher = CredentialEncryption(key)
    result = cipher.encrypt_credentials("KEY123", "SECRET456", "PASS789")
    decrypted = cipher.decrypt_credentials(
        result["api_key_enc"], result["api_secret_enc"], result["passphrase_enc"]
    )
    assert decrypted["api_secret"] == "SECRET456"

def test_tampered_token_raises():
    key = CredentialEncryption.generate_key()
    cipher = CredentialEncryption(key)
    enc = cipher.encrypt_secret("mysecret")
    with pytest.raises(Exception):
        cipher.decrypt_secret(enc[:-5] + "XXXXX")  # tampered

def test_empty_key_raises():
    with pytest.raises(Exception):
        CredentialEncryption("")
```

---

## 📈 Impacto na Estabilidade

- Elimina vetor de ataque mais crítico do sistema
- Workers não operarão sem credenciais válidas (falha rápida no startup)
- Logs limpos permitem debugging sem risco de exposição

## ✅ Checklist Final

- [ ] `CREDENTIAL_ENCRYPTION_KEY` gerada e salva no `.env.prod`
- [ ] `cipher_singleton.py` criado e importado no `main.py` startup
- [ ] Nenhum campo `api_secret` ou `api_passphrase` em texto plano no MongoDB
- [ ] `_load_decrypted_instance()` chamado antes de cada `BotWorker.__init__`
- [ ] Testes de encrypt/decrypt passando
- [ ] Grep por `api_secret` no código confirma 0 ocorrências em texto plano

---

<a id="doc-k02"></a>
# DOC-K02 — Rate Limiting com Headers Nativos gw-ratelimit-* da KuCoin

## 🎯 Objetivo

Substituir o rate limiter baseado em contadores locais estáticos por um sistema que **lê e respeita os headers `gw-ratelimit-*`** retornados pela KuCoin em cada resposta HTTP, adaptando-se dinamicamente ao estado real do servidor da exchange.

---

## 🚨 Problema Técnico Atual

**Arquivo:** `backend/app/integrations/kucoin/rate_limiter.py`

O `KuCoinRateLimiter` atual usa buckets configurados estaticamente:
```python
KUCOIN_RATE_LIMITS: Dict[str, RateLimitBucket] = {
    "order_place": RateLimitBucket(max_requests=45, window_seconds=10),
    ...
}
```

**Problema crítico:** A KuCoin retorna em cada resposta os headers:
```
gw-ratelimit-limit: 2000
gw-ratelimit-remaining: 1987
gw-ratelimit-reset: 1709123456789
```

O sistema atual **ignora completamente esses headers**. Isso significa que:

1. O limite local pode estar calculado errado para a conta específica (limites variam por nível de API)
2. Se múltiplas instâncias da engine rodarem, cada uma tem seu próprio contador — **a soma ultrapassa o limite real**
3. Quando a KuCoin muda os limites (o que acontece periodicamente), o sistema não se adapta

No arquivo `rest_client.py`, o handling do 429 usa apenas `Retry-After`:
```python
if response.status == 429:
    retry_after = int(response.headers.get("Retry-After", 5))
```

Mas **não lê** os headers `gw-ratelimit-*` que informam o estado antes de chegar ao 429.

---

## 🔎 Risco Real em Produção

| Cenário | Consequência |
|---|---|
| Engine ultrapassa limite real da KuCoin | Ordens rejeitadas com 429; posições ficam abertas sem controle de saída |
| Burst de ordens no mesmo millisegundo | Todas rejeitadas — bots ficam em estado inválido (posição aberta, sem ordem de saída) |
| IP banimento temporário (excesso de 429) | Todas as operações do usuário bloqueadas por minutos/horas |

---

## 🛠 Plano de Correção Passo a Passo

### Passo 1 — Criar RateLimitState para rastrear headers

**Arquivo a modificar:** `backend/app/integrations/kucoin/rate_limiter.py`

```python
"""
KuCoin Rate Limiter — v2 com headers gw-ratelimit-* nativos.

Funciona em dois modos simultâneos:
  1. Proativo: sliding-window local (evita chegar no limite)
  2. Reativo: atualiza estado com headers reais de cada resposta
"""
from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, Optional

logger = logging.getLogger("kucoin.ratelimit")


@dataclass
class GatewayRateLimitState:
    """
    Estado real do rate limit conforme informado pelos headers da KuCoin.

    Headers esperados em cada resposta:
      gw-ratelimit-limit:     total de pontos disponíveis na janela
      gw-ratelimit-remaining: pontos restantes NESTE momento
      gw-ratelimit-reset:     timestamp Unix (ms) quando os pontos resetam
    """
    limit: int = 2000
    remaining: int = 2000
    reset_at_ms: int = 0          # timestamp ms quando reseta
    last_updated: float = 0.0     # monotonic time da última atualização
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def update_from_headers(self, headers: dict) -> None:
        """Atualiza estado com headers da resposta. Thread-safe via chamada no event loop."""
        raw_limit     = headers.get("gw-ratelimit-limit")
        raw_remaining = headers.get("gw-ratelimit-remaining")
        raw_reset     = headers.get("gw-ratelimit-reset")

        if raw_limit is not None:
            try:
                self.limit = int(raw_limit)
            except (ValueError, TypeError):
                pass

        if raw_remaining is not None:
            try:
                self.remaining = int(raw_remaining)
            except (ValueError, TypeError):
                pass

        if raw_reset is not None:
            try:
                self.reset_at_ms = int(raw_reset)
            except (ValueError, TypeError):
                pass

        self.last_updated = time.monotonic()

        if self.remaining < 100:
            logger.warning(
                "⚠️  gw-ratelimit-remaining=%d (limit=%d). "
                "Aplicando throttle preventivo.",
                self.remaining, self.limit,
            )

    def seconds_until_reset(self) -> float:
        """Segundos até o próximo reset do gateway."""
        if not self.reset_at_ms:
            return 0.0
        reset_ts = self.reset_at_ms / 1000.0
        return max(0.0, reset_ts - time.time())

    def usage_pct(self) -> float:
        """Percentual de uso (0.0 a 1.0)."""
        if self.limit == 0:
            return 1.0
        return 1.0 - (self.remaining / self.limit)
```

### Passo 2 — Integrar leitura de headers no `request()` do REST client

**Arquivo:** `backend/app/integrations/kucoin/rest_client.py`

```python
# Adicionar no topo:
from app.integrations.kucoin.rate_limiter import (
    KuCoinRateLimiter,
    GatewayRateLimitState,
)

# Singleton de estado do gateway (compartilhado por todas as requisições)
_GATEWAY_STATE = GatewayRateLimitState()


class KuCoinRESTClient:
    # ... código existente ...

    async def request(self, method, endpoint, params=None, body=None, authenticated=True) -> dict:
        body_str = json.dumps(body, separators=(",", ":")) if body else ""
        url = f"{self.base_url}{endpoint}"

        headers: dict = {}
        if authenticated:
            headers = build_auth_headers(
                self.api_key, self.api_secret, self.api_passphrase,
                method, endpoint, body_str,
            )

        # === THROTTLE PREVENTIVO baseado no estado do gateway ===
        usage = _GATEWAY_STATE.usage_pct()
        if usage > 0.85:
            # Acima de 85% de uso: adicionar delay proporcional
            wait = _GATEWAY_STATE.seconds_until_reset() * 0.1
            if wait > 0:
                logger.warning(
                    "Rate limit gateway em %.0f%% — aguardando %.2fs",
                    usage * 100, wait,
                )
                await asyncio.sleep(wait)

        # Rate limit local proativo (mantido para segurança adicional)
        await KuCoinRateLimiter.acquire(endpoint)

        last_exc: Exception = RuntimeError("No attempts made")

        for attempt in range(MAX_RETRIES + 1):
            try:
                session = await self._get_session()
                async with session.request(
                    method=method, url=url, params=params,
                    data=body_str or None, headers=headers,
                ) as response:

                    # === LER HEADERS GW-RATELIMIT EM TODA RESPOSTA ===
                    _GATEWAY_STATE.update_from_headers(dict(response.headers))

                    if response.status == 429:
                        # Ler Retry-After OU calcular pelo reset do gateway
                        retry_after_hdr = response.headers.get("Retry-After")
                        if retry_after_hdr:
                            wait_secs = float(retry_after_hdr)
                        else:
                            wait_secs = _GATEWAY_STATE.seconds_until_reset() + 1.0

                        logger.warning(
                            "❌ 429 em %s (remaining=%d). Aguardando %.1fs",
                            endpoint, _GATEWAY_STATE.remaining, wait_secs,
                        )
                        await asyncio.sleep(wait_secs)

                        # Readquirir slot após espera
                        await KuCoinRateLimiter.acquire(endpoint)
                        continue

                    if response.status in RETRYABLE_STATUS and attempt < MAX_RETRIES:
                        wait = BACKOFF_BASE ** attempt
                        logger.warning(
                            "Status %d em %s, retry %d/%d em %.1fs",
                            response.status, endpoint, attempt + 1, MAX_RETRIES, wait,
                        )
                        await asyncio.sleep(wait)
                        continue

                    data = await response.json(content_type=None)

                    if response.status >= 400:
                        raise KuCoinAPIError(
                            status=response.status,
                            code=str(data.get("code", response.status)),
                            message=data.get("msg", "Unknown error"),
                            endpoint=endpoint,
                        )

                    if str(data.get("code")) != "200000":
                        raise KuCoinAPIError(
                            status=200,
                            code=str(data.get("code", "?")),
                            message=str(data.get("msg", data)),
                            endpoint=endpoint,
                        )

                    return data.get("data", data)

            except KuCoinAPIError:
                raise
            except aiohttp.ClientError as exc:
                last_exc = exc
                if attempt < MAX_RETRIES:
                    await asyncio.sleep(BACKOFF_BASE ** attempt)
                else:
                    raise KuCoinNetworkError(
                        f"Falha persistente em {endpoint}: {exc}"
                    ) from exc

        raise KuCoinNetworkError(
            f"Máximo de tentativas atingido para {endpoint}"
        ) from last_exc
```

### Passo 3 — Endpoint de métricas de rate limit para o dashboard

**Arquivo:** `backend/app/trading/router.py` (adicionar endpoint)

```python
@router.get("/rate-limit/status", tags=["Trading"])
async def get_rate_limit_status(current_user: dict = Depends(get_current_user)):
    """Retorna estado atual do rate limit com a KuCoin."""
    from app.integrations.kucoin.rest_client import _GATEWAY_STATE
    return {
        "gateway_limit": _GATEWAY_STATE.limit,
        "gateway_remaining": _GATEWAY_STATE.remaining,
        "usage_pct": round(_GATEWAY_STATE.usage_pct() * 100, 1),
        "seconds_until_reset": round(_GATEWAY_STATE.seconds_until_reset(), 1),
        "last_updated_ago_seconds": round(
            time.monotonic() - _GATEWAY_STATE.last_updated, 1
        ) if _GATEWAY_STATE.last_updated else None,
        "health": "ok" if _GATEWAY_STATE.usage_pct() < 0.8 else "throttling",
    }
```

---

## 📂 Arquivos a Modificar

| Arquivo | Mudança |
|---|---|
| `backend/app/integrations/kucoin/rate_limiter.py` | Adicionar `GatewayRateLimitState` |
| `backend/app/integrations/kucoin/rest_client.py` | Singleton `_GATEWAY_STATE`, leitura em toda resposta |
| `backend/app/trading/router.py` | Endpoint `/rate-limit/status` |

---

## 🧪 Estratégia de Testes

```python
# tests/test_rate_limiter.py

def test_gateway_state_updates_from_headers():
    from app.integrations.kucoin.rate_limiter import GatewayRateLimitState
    state = GatewayRateLimitState()
    state.update_from_headers({
        "gw-ratelimit-limit": "2000",
        "gw-ratelimit-remaining": "150",
        "gw-ratelimit-reset": str(int((time.time() + 10) * 1000)),
    })
    assert state.limit == 2000
    assert state.remaining == 150
    assert state.usage_pct() > 0.9
    assert 0 < state.seconds_until_reset() <= 11

def test_gateway_state_ignores_malformed_headers():
    state = GatewayRateLimitState()
    original_limit = state.limit
    state.update_from_headers({"gw-ratelimit-limit": "nao-e-numero"})
    assert state.limit == original_limit  # não mudou
```

---

## 📈 Impacto na Estabilidade

- **Elimina 429s inesperados** em produção
- Sistema adapta-se automaticamente a mudanças de limite pela KuCoin
- Dashboard pode mostrar saúde do rate limit em tempo real

## ✅ Checklist Final

- [ ] `GatewayRateLimitState` implementado e testado
- [ ] `_GATEWAY_STATE.update_from_headers()` chamado em TODA resposta HTTP
- [ ] Throttle preventivo ativa com > 85% de uso
- [ ] Logs emitidos quando remaining < 100
- [ ] Endpoint `/rate-limit/status` retornando dados corretos

---

<a id="doc-k03"></a>
# DOC-K03 — Sincronização de Estado via WebSocket (Execution Reports)

## 🎯 Objetivo

Garantir que o estado interno do `BotWorker` (posição aberta, preço de entrada, quantidade) seja **sincronizado em tempo real** com os execution reports da KuCoin via WebSocket privado, eliminando polling e divergências de estado.

---

## 🚨 Problema Técnico Atual

**Arquivo:** `backend/app/engine/worker.py`

O `BotWorker` mantém o estado em memória:
```python
self._open_position: Optional[dict] = None
```

E fecha posições apenas por:
1. Sinal da estratégia
2. Check de risco no tick de preço

**O que está ausente:** O sistema **não processa execution reports** do WebSocket privado (`/spotMarket/tradeOrders`). Isso significa:

- Se uma ordem for parcialmente preenchida (partial fill), o worker não sabe a quantidade real
- Se uma ordem for cancelada pela exchange (por liquidez insuficiente), o worker ainda acredita que tem posição aberta
- Se a conexão WebSocket cair e a ordem ser preenchida durante a reconexão, o estado fica inconsistente
- `_open_position["entry_quantity"]` pode estar errado se o fill foi parcial

---

## 🔎 Risco Real em Produção

| Cenário | Consequência |
|---|---|
| Ordem de compra parcialmente preenchida (partial fill) | Worker tenta vender quantidade maior do que possui → KuCoin rejeita a venda → posição fica "presa" |
| Ordem cancelada pela exchange | Worker acredita ter posição aberta → bloqueia novos sinais de compra indefinidamente |
| Reconnect durante fill | Worker perde o evento de fill → estado: "posição aberta" sem ordem real na exchange |
| Venda forçada pela exchange (margin call em futures) | Worker não sabe → continua calculando TP/SL sobre posição inexistente |

---

## 🛠 Plano de Correção Passo a Passo

### Passo 1 — Subscrever ao canal de execution reports no startup do Worker

**Arquivo:** `backend/app/engine/worker.py`

```python
async def run(self):
    """Entry point chamado pelo BotOrchestrator."""
    self._running = True
    self._init_components()
    logger.info(f"▶️  BotWorker {self.bot_id[:8]} iniciando execução")

    await self._update_status("running")

    # === NOVO: Iniciar WebSocket privado para execution reports ===
    from app.integrations.kucoin.ws_client import (
        KuCoinWebSocketClient,
        TOPIC_ORDERS,
        TOPIC_BALANCES,
    )
    from app.integrations.kucoin.rest_client import KuCoinRESTClient

    rest_client = KuCoinRESTClient(
        api_key=self.instance.get("decrypted_api_key", ""),
        api_secret=self.instance.get("decrypted_api_secret", ""),
        api_passphrase=self.instance.get("decrypted_api_passphrase", ""),
        sandbox=self._is_sandbox(),
    )
    self._ws_client = KuCoinWebSocketClient(
        rest_client=rest_client,
        on_message=self._handle_ws_message,
        on_disconnect=self._on_ws_disconnect,
        private=True,
    )
    ws_task = asyncio.create_task(self._ws_client.connect())
    await self._ws_client.subscribe(TOPIC_ORDERS)
    await self._ws_client.subscribe(TOPIC_BALANCES)

    try:
        pair = self.config.get("pair", "BTC-USDT")
        async for tick in self._exchange.price_feed(pair, stop_event=self._stop_event):
            if self._stop_event.is_set():
                break
            await self._pause_event.wait()
            try:
                await self._execute_cycle(tick)
            except Exception as exc:
                logger.error(f"❌ Erro no ciclo bot {self.bot_id[:8]}: {exc}", exc_info=True)
                await self._log_event("ERROR", str(exc))
                burst_reason = self._risk.record_error()
                if burst_reason:
                    await self._update_status("stopped", stop_reason=burst_reason)
                    self._stop_event.set()
                    break
    finally:
        self._running = False
        await self._ws_client.disconnect()
        ws_task.cancel()
        await self._update_status("stopped")
        logger.info(f"⏹️  BotWorker {self.bot_id[:8]} encerrado")
```

### Passo 2 — Handler de mensagens WebSocket

```python
async def _handle_ws_message(self, msg: dict) -> None:
    """
    Processa execution reports do WebSocket privado da KuCoin.

    Formato do evento /spotMarket/tradeOrders:
    {
        "type": "message",
        "topic": "/spotMarket/tradeOrders",
        "subject": "orderChange",
        "data": {
            "orderId": "5bd6e9286d99522a52e458de",
            "clientOid": "...",
            "symbol": "BTC-USDT",
            "side": "buy",
            "type": "market",
            "status": "done",       # open | done | match | cancelled
            "matchSize": "0.00123", # quantidade preenchida
            "matchFunds": "50",     # fundos gastos
            "price": "40000",
            "remainSize": "0",      # restante não preenchido
            "filledSize": "0.00123",
            "filledFunds": "49.87",
            "fee": "0.049",
            "feeCurrency": "USDT",
            "ts": 1709123456789,    # timestamp nanoseconds
        }
    }
    """
    topic = msg.get("topic", "")
    data  = msg.get("data", {})

    if "/spotMarket/tradeOrders" not in topic:
        return

    subject = msg.get("subject", "")
    if subject not in ("orderChange", "match"):
        return

    order_id   = data.get("orderId", "")
    status     = data.get("status", "")
    symbol     = data.get("symbol", "")
    side       = data.get("side", "")
    filled_size  = float(data.get("filledSize") or data.get("matchSize") or 0)
    filled_funds = float(data.get("filledFunds") or data.get("matchFunds") or 0)
    fee          = float(data.get("fee") or 0)

    logger.debug(
        "WS execution report: orderId=%s status=%s symbol=%s side=%s "
        "filledSize=%s filledFunds=%s",
        order_id, status, symbol, side, filled_size, filled_funds,
    )

    # Verificar se é uma ordem nossa
    if not self._open_position:
        return

    tracked_order_id = self._open_position.get("entry_order_id", "")

    # === CASO 1: Ordem de ENTRADA preenchida (parcial ou total) ===
    if order_id == tracked_order_id and side == "buy":
        if status in ("match", "done"):
            # Atualizar quantidade REAL preenchida
            old_qty = self._open_position.get("entry_quantity", 0)
            if filled_size > 0 and abs(filled_size - old_qty) / max(old_qty, 1e-10) > 0.01:
                # Divergência > 1% — atualizar
                logger.warning(
                    "⚠️  Partial fill detectado: qty esperada=%.6f real=%.6f [bot=%s]",
                    old_qty, filled_size, self.bot_id[:8],
                )
                self._open_position["entry_quantity"] = filled_size
                self._open_position["entry_funds"]    = filled_funds
                self._open_position["entry_fee"]      = fee
                self._open_position["entry_price"]    = (
                    filled_funds / filled_size if filled_size > 0 else 0
                )

                # Persistir correção no banco
                if self._open_position.get("_trade_doc_id"):
                    from app.core.database import get_db
                    db = get_db()
                    await db["bot_trades"].update_one(
                        {"_id": ObjectId(self._open_position["_trade_doc_id"])},
                        {"$set": {
                            "entry_price": self._open_position["entry_price"],
                            "entry_funds": filled_funds,
                            "entry_fee_usdt": fee,
                        }}
                    )

        elif status == "cancelled":
            # Ordem de compra cancelada — não temos posição real
            logger.warning(
                "⚠️  Ordem de compra %s CANCELADA pela exchange. "
                "Limpando posição local. [bot=%s]",
                order_id, self.bot_id[:8],
            )
            await self._log_event(
                "WARNING",
                f"Ordem de compra {order_id} cancelada pela exchange — posição limpa",
                {"order_id": order_id, "symbol": symbol},
            )
            if self._open_position.get("_trade_doc_id"):
                from app.core.database import get_db
                db = get_db()
                await db["bot_trades"].update_one(
                    {"_id": ObjectId(self._open_position["_trade_doc_id"])},
                    {"$set": {"status": "cancelled", "exit_reason": "order_cancelled_by_exchange"}}
                )
            self._open_position = None

    # === CASO 2: Ordem de SAÍDA preenchida ===
    exit_order_id = self._open_position.get("exit_order_id", "") if self._open_position else ""
    if order_id == exit_order_id and side == "sell" and status == "done":
        logger.info(
            "✅ Ordem de saída %s confirmada via WS. filledSize=%.6f [bot=%s]",
            order_id, filled_size, self.bot_id[:8],
        )
        # Estado já foi atualizado pelo _close_position — apenas confirmar

async def _on_ws_disconnect(self, reconnect_count: int) -> None:
    """Chamado antes de cada tentativa de reconexão do WebSocket."""
    logger.warning(
        "📡 WebSocket privado desconectado (tentativa reconexão %d). "
        "Consultando estado real das ordens abertas via REST. [bot=%s]",
        reconnect_count, self.bot_id[:8],
    )
    # Durante desconexão: verificar se posição ainda está aberta na exchange
    await self._reconcile_position_via_rest()

async def _reconcile_position_via_rest(self) -> None:
    """
    Verifica via REST se as ordens rastreadas localmente ainda existem na exchange.
    Chamado após reconexão de WebSocket para recuperar eventos perdidos.
    """
    if not self._open_position:
        return

    order_id = self._open_position.get("entry_order_id", "")
    if not order_id:
        return

    try:
        order_data = await self._exchange.get_order(order_id)
        status = order_data.get("isActive", True)
        filled_size = float(order_data.get("dealSize") or 0)

        if not status and filled_size == 0:
            # Ordem não existente ou cancelada sem fill
            logger.warning(
                "🔄 Reconciliação: ordem %s não encontrada/cancelada. "
                "Limpando posição local. [bot=%s]",
                order_id, self.bot_id[:8],
            )
            self._open_position = None

        elif abs(filled_size - self._open_position.get("entry_quantity", 0)) > 0.000001:
            logger.warning(
                "🔄 Reconciliação: quantidade real=%.6f difere do local=%.6f. Corrigindo.",
                filled_size, self._open_position.get("entry_quantity", 0),
            )
            self._open_position["entry_quantity"] = filled_size

    except Exception as exc:
        logger.error("Erro na reconciliação via REST: %s [bot=%s]", exc, self.bot_id[:8])
```

---

## 📂 Arquivos a Modificar

| Arquivo | Mudança |
|---|---|
| `backend/app/engine/worker.py` | Adicionar WS privado no `run()`, handlers de execution reports |
| `backend/app/integrations/kucoin/ws_client.py` | Verificar `TOPIC_ORDERS` importável |

---

## 🧪 Estratégia de Testes

```python
# tests/test_execution_reports.py

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock

@pytest.mark.anyio
async def test_partial_fill_updates_position():
    """Worker deve corrigir quantidade quando fill parcial é confirmado via WS."""
    worker = create_test_worker()
    worker._open_position = {
        "entry_order_id": "ORDER-001",
        "entry_quantity": 0.00200,  # quantidade esperada
        "entry_funds": 80.0,
        "entry_price": 40000.0,
        "_trade_doc_id": "trade-doc-1",
    }

    ws_msg = {
        "topic": "/spotMarket/tradeOrders",
        "subject": "orderChange",
        "data": {
            "orderId": "ORDER-001",
            "side": "buy",
            "status": "done",
            "filledSize": "0.00123",  # fill parcial — menos que esperado
            "filledFunds": "49.20",
            "fee": "0.049",
        }
    }

    await worker._handle_ws_message(ws_msg)

    assert worker._open_position["entry_quantity"] == pytest.approx(0.00123, rel=1e-4)

@pytest.mark.anyio
async def test_cancelled_order_clears_position():
    worker = create_test_worker()
    worker._open_position = {
        "entry_order_id": "ORDER-002",
        "entry_quantity": 0.001,
        "_trade_doc_id": None,
    }
    ws_msg = {
        "topic": "/spotMarket/tradeOrders",
        "subject": "orderChange",
        "data": {
            "orderId": "ORDER-002",
            "side": "buy",
            "status": "cancelled",
            "filledSize": "0",
        }
    }
    await worker._handle_ws_message(ws_msg)
    assert worker._open_position is None
```

---

## 📈 Impacto na Estabilidade

- **Elimina divergência de estado** entre engine e exchange
- Partial fills são tratados corretamente — quantidade de venda é sempre a quantidade real
- Posições "fantasma" (ordem cancelada, estado local desatualizado) são limpas automaticamente

## ✅ Checklist Final

- [ ] `TOPIC_ORDERS` subscrito no startup de cada `BotWorker`
- [ ] `_handle_ws_message` trata `status: cancelled` limpando `_open_position`
- [ ] `_handle_ws_message` trata partial fills corrigindo `entry_quantity`
- [ ] `_on_ws_disconnect` chama `_reconcile_position_via_rest()`
- [ ] Testes de partial fill e ordem cancelada passando

---

<a id="doc-k04"></a>
# DOC-K04 — Idempotência de Ordens com clientOid e Persistência Pre-Send

## 🎯 Objetivo

Garantir que **nenhuma ordem seja duplicada** mesmo em cenários de timeout, retry ou restart da engine, usando `clientOid` como chave de idempotência e persistindo a intenção de ordem **antes** de enviá-la à exchange.

---

## 🚨 Problema Técnico Atual

**Arquivo:** `backend/app/integrations/kucoin/rest_client.py` — `place_market_order()`

```python
body: dict = {
    "clientOid": str(uuid.uuid4()),   # ← gerado NA hora do envio
    ...
}
result = await self.request("POST", "/api/v1/orders", body=body)
```

**Problema crítico:** O `clientOid` é gerado **no momento do envio**. Se a chamada a `place_market_order()` for chamada duas vezes (ex.: timeout no primeiro envio, retry automático), dois `clientOid` diferentes são gerados, criando **duas ordens separadas** na exchange.

**Segundo problema:** Se a engine reinicia enquanto uma ordem está em trânsito (resposta HTTP perdida), a engine não sabe se a ordem foi aceita. Sem `clientOid` pré-persistido, é impossível consultar o estado.

**A KuCoin garante idempotência por `clientOid`:** se você reenviar o mesmo `clientOid`, a exchange retorna a ordem original sem criar uma nova. Mas isso só funciona se o `clientOid` for **o mesmo na re-tentativa**.

---

## 🔎 Risco Real em Produção

| Cenário | Consequência |
|---|---|
| Timeout em `/api/v1/orders` → retry automático → novo UUID | **Duas ordens de compra** são criadas — dobro do capital comprometido |
| Engine reinicia durante envio da ordem | Não sabe se ordem foi aceita → abre nova posição = posição dupla |
| Race condition: dois ciclos enviando simultaneamente | Duas ordens de compra no mesmo tick |

---

## 🛠 Plano de Correção Passo a Passo

### Passo 1 — Persistir intenção ANTES de enviar (Write-Ahead Order Log)

**Arquivo a criar:** `backend/app/engine/order_intent_store.py`

```python
"""
Order Intent Store (Write-Ahead Log para ordens).

Persiste a intenção de uma ordem ANTES de enviá-la à exchange.
Permite recuperar o clientOid em caso de retry e detectar ordens em trânsito
no restart da engine.

Coleção MongoDB: order_intents
Índice único: { clientOid: 1 }
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId

logger = logging.getLogger("engine.order_intent")


class OrderIntentStore:
    """Gerencia o write-ahead log de intenções de ordem."""

    def __init__(self, db):
        self._col = db["order_intents"]

    async def ensure_indexes(self) -> None:
        await self._col.create_index("client_oid", unique=True)
        await self._col.create_index("bot_instance_id")
        await self._col.create_index("state")
        # TTL: limpa intents resolvidos após 7 dias
        await self._col.create_index(
            "resolved_at",
            expireAfterSeconds=604800,
            sparse=True,
        )

    async def create_intent(
        self,
        bot_instance_id: str,
        user_id: str,
        pair: str,
        side: str,
        order_type: str,
        client_oid: str,
        funds: Optional[float] = None,
        size: Optional[float] = None,
        price: Optional[float] = None,
    ) -> str:
        """
        Persiste a intenção de ordem antes do envio.

        Retorna o _id do documento criado.
        Se o clientOid já existir (retry), retorna o _id existente.
        """
        doc = {
            "bot_instance_id": bot_instance_id,
            "user_id": user_id,
            "pair": pair,
            "side": side,
            "order_type": order_type,
            "client_oid": client_oid,
            "funds": funds,
            "size": size,
            "price": price,
            "state": "pending",      # pending | sent | filled | cancelled | error
            "exchange_order_id": None,
            "created_at": datetime.now(timezone.utc),
            "resolved_at": None,
        }
        try:
            result = await self._col.insert_one(doc)
            logger.debug(
                "Order intent criado: clientOid=%s pair=%s side=%s",
                client_oid, pair, side,
            )
            return str(result.inserted_id)
        except Exception:
            # Documento já existe (retry com mesmo clientOid) — recuperar _id existente
            existing = await self._col.find_one({"client_oid": client_oid})
            if existing:
                logger.info(
                    "Order intent já existia: clientOid=%s state=%s",
                    client_oid, existing.get("state"),
                )
                return str(existing["_id"])
            raise

    async def mark_sent(self, client_oid: str, exchange_order_id: str) -> None:
        await self._col.update_one(
            {"client_oid": client_oid},
            {"$set": {"state": "sent", "exchange_order_id": exchange_order_id}},
        )

    async def mark_filled(self, client_oid: str) -> None:
        await self._col.update_one(
            {"client_oid": client_oid},
            {"$set": {"state": "filled", "resolved_at": datetime.now(timezone.utc)}},
        )

    async def mark_error(self, client_oid: str, error: str) -> None:
        await self._col.update_one(
            {"client_oid": client_oid},
            {"$set": {"state": "error", "error": error, "resolved_at": datetime.now(timezone.utc)}},
        )

    async def get_pending_intents(self, bot_instance_id: str) -> list:
        """Retorna intents em estado pending/sent — usados no restart da engine."""
        cursor = self._col.find({
            "bot_instance_id": bot_instance_id,
            "state": {"$in": ["pending", "sent"]},
        })
        return await cursor.to_list(length=100)
```

### Passo 2 — Modificar `place_market_order` para usar clientOid pré-gerado

**Arquivo:** `backend/app/integrations/kucoin/rest_client.py`

```python
async def place_market_order(
    self,
    pair:       str,
    side:       str,
    size:       Optional[float] = None,
    funds:      Optional[float] = None,
    client_oid: Optional[str]   = None,   # ← NOVO parâmetro
) -> dict:
    """
    Place a market order.

    client_oid: pré-gerado e pré-persistido pelo BotWorker.
                Se None, gera um (mas sem garantia de idempotência em retry).
    """
    if not size and not funds:
        raise ValueError("Um de 'size' ou 'funds' deve ser fornecido")

    # Usar o clientOid passado — NUNCA gerar um novo em retry
    oid = client_oid if client_oid else str(uuid.uuid4())

    body: dict = {
        "clientOid": oid,
        "symbol":    pair,
        "side":      side.lower(),
        "type":      "market",
    }
    if funds is not None:
        body["funds"] = str(round(funds, 6))
    if size is not None:
        body["size"] = str(round(size, 8))

    result = await self.request("POST", "/api/v1/orders", body=body)
    order_id = result.get("orderId", "")
    logger.info(f"✅ Ordem {side.upper()} {pair} | orderId={order_id} | clientOid={oid}")

    try:
        return await self.get_order(order_id)
    except Exception:
        return {"orderId": order_id, "clientOid": oid, "dealFunds": funds or 0}
```

### Passo 3 — Usar o OrderIntentStore no BotWorker

**Arquivo:** `backend/app/engine/worker.py` — `_open_position_handler()`

```python
async def _open_position_handler(self, price: float, signal):
    """Abre posição com garantia de idempotência via clientOid pré-persistido."""
    from app.core.database import get_db
    from app.engine.order_intent_store import OrderIntentStore

    pair    = self.config.get("pair", "BTC-USDT")
    capital = float(self.config.get("capital_usdt", 100))

    db    = get_db()
    store = OrderIntentStore(db)

    # PASSO 1: Gerar clientOid ANTES de qualquer envio
    client_oid = str(uuid.uuid4())

    # PASSO 2: Persistir intenção ANTES de enviar à exchange
    intent_id = await store.create_intent(
        bot_instance_id=self.bot_id,
        user_id=self.user_id,
        pair=pair,
        side="buy",
        order_type="market",
        client_oid=client_oid,
        funds=capital,
    )
    logger.debug("Intent %s persistido para bot %s", intent_id, self.bot_id[:8])

    try:
        # PASSO 3: Enviar à exchange com o clientOid pre-gerado
        order = await self._exchange.place_market_order(
            pair=pair,
            side="buy",
            funds=capital,
            client_oid=client_oid,   # ← idempotência garantida
        )
        if not order:
            await store.mark_error(client_oid, "order returned None")
            return

        # PASSO 4: Marcar como enviada
        exchange_order_id = order.get("orderId", "")
        await store.mark_sent(client_oid, exchange_order_id)

        filled_price = float(order.get("dealPrice") or price)
        filled_funds = float(order.get("dealFunds") or capital)
        fee          = float(order.get("fee") or filled_funds * 0.001)
        quantity     = (filled_funds - fee) / filled_price if filled_price else 0

        self._open_position = {
            "entry_order_id":   exchange_order_id,
            "client_oid":       client_oid,
            "intent_id":        intent_id,
            "entry_price":      filled_price,
            "entry_funds":      filled_funds,
            "entry_quantity":   quantity,
            "entry_fee":        fee,
            "entry_timestamp":  datetime.now(timezone.utc),
            "reason":           signal.reason,
        }

        await self._persist_trade_event("buy", order, signal)
        await store.mark_filled(client_oid)
        await self._log_event(
            "TRADE",
            f"📈 BUY @ {filled_price:.4f} | qty={quantity:.6f} | clientOid={client_oid[:8]}",
        )
    except Exception as exc:
        await store.mark_error(client_oid, str(exc))
        logger.error(f"Falha ao abrir posição: {exc}", exc_info=True)
        await self._log_event("ERROR", f"Falha ao abrir posição: {exc}")
```

---

## 📂 Arquivos a Modificar

| Arquivo | Mudança |
|---|---|
| `backend/app/engine/order_intent_store.py` | CRIAR — write-ahead log |
| `backend/app/integrations/kucoin/rest_client.py` | Parâmetro `client_oid` em `place_market_order` e `place_limit_order` |
| `backend/app/engine/worker.py` | `_open_position_handler` usa `OrderIntentStore` |

---

## ✅ Checklist Final

- [ ] `order_intents` collection com índice único em `client_oid`
- [ ] `clientOid` gerado ANTES do envio e persistido no intent
- [ ] `place_market_order()` aceita `client_oid` externo
- [ ] Testes confirmam que retry com mesmo `client_oid` não cria ordem dupla

---

<a id="doc-k05"></a>
# DOC-K05 — Take Profit e Stop Loss Configuráveis via SaaS

## 🎯 Objetivo

Implementar TP/SL **configuráveis pelo usuário via frontend SaaS**, com suporte a dois modos:
1. **Modo engine (soft):** TP/SL calculado pelo `PositionRiskManager` a cada tick de preço
2. **Modo nativo KuCoin (hard):** ordens de stop-limit enviadas à exchange no momento da entrada — funciona mesmo se a engine cair

---

## 🚨 Problema Técnico Atual

**Arquivo:** `backend/app/risk/manager.py`

O `PositionRiskManager` calcula TP/SL corretamente:
```python
if gain_pct >= self.cfg.take_profit_pct:
    return StopReason.TAKE_PROFIT
```

**Problema:** Este cálculo é feito **em memória na engine**, a cada tick de preço via WebSocket. Se a engine for reiniciada, pausada, ou perder conexão com a exchange, **as proteções de TP/SL ficam inativas durante o período offline**. O preço pode cruzar o stop-loss e a posição não é fechada.

**Não existe** implementação de ordens stop-limit nativas na KuCoin (que rodam no servidor da exchange, independente da engine).

---

## 🔎 Risco Real em Produção

| Cenário | Consequência |
|---|---|
| Engine offline por 5 minutos | TP/SL não executado → preço cruza stop-loss → perda não controlada |
| Restart durante mercado volátil | Bot sem proteção durante reconexão |
| Provider de VPS com instabilidade | Usuário perde capital real por ausência de stop nativo |

**Estimativa de perda em mercado crypto volátil:** uma posição sem stop pode perder 10-30% em minutos durante eventos de alta volatilidade.

---

## 🛠 Plano de Correção Passo a Passo

### Passo 1 — Adicionar campos TP/SL ao schema de configuração do bot

**Arquivo:** `backend/app/bots/schemas.py` ou equivalente

```python
from pydantic import BaseModel, Field, field_validator
from typing import Literal, Optional

class TakeProfitConfig(BaseModel):
    mode: Literal["percentage", "fixed_price"] = "percentage"
    value: float = Field(..., gt=0, description="% ou preço absoluto")
    # Para modo nativo: envia stop-limit na exchange
    use_native_order: bool = False

class StopLossConfig(BaseModel):
    mode: Literal["percentage", "fixed_price", "trailing"] = "percentage"
    value: float = Field(..., gt=0)
    trailing_callback_pct: Optional[float] = None  # apenas para mode=trailing
    use_native_order: bool = False  # envia stop-limit na exchange

class BotConfigSchema(BaseModel):
    pair:         str   = "BTC-USDT"
    capital_usdt: float = Field(..., gt=10, le=100_000)
    timeframe:    str   = "1h"

    take_profit: Optional[TakeProfitConfig] = None
    stop_loss:   Optional[StopLossConfig]   = None

    # Campos legados (manter compatibilidade)
    take_profit_pct: Optional[float] = None
    stop_loss_pct:   Optional[float] = None
```

### Passo 2 — Implementar ordem stop-limit nativa na KuCoin

**Arquivo:** `backend/app/integrations/kucoin/rest_client.py`

```python
async def place_stop_order(
    self,
    pair:        str,
    side:        str,           # "sell" para stop-loss, "buy" para stop sobre short
    stop_price:  float,         # preço que ativa a ordem (stopPrice)
    limit_price: float,         # preço da ordem limit após ativação
    size:        float,         # quantidade
    client_oid:  Optional[str] = None,
    stop_type:   str = "loss",  # "loss" ou "entry"
) -> dict:
    """
    Coloca uma ordem stop-limit na KuCoin (Stop Order).

    Endpoint: POST /api/v1/stop-order

    A ordem ficará na exchange e será executada automaticamente quando
    stopPrice for atingido, independente do estado da engine.

    Args:
        stop_price:  Preço de ativação (trigger). Para stop-loss: abaixo do preço atual.
        limit_price: Preço limit após ativação. Normalmente ligeiramente abaixo do stopPrice
                     para garantir preenchimento.
        stop_type:   "loss" = ativa quando preço cai ABAIXO do stopPrice.
                     "entry" = ativa quando preço SOBE ACIMA do stopPrice.
    """
    body = {
        "clientOid":    client_oid or str(uuid.uuid4()),
        "symbol":       pair,
        "side":         side.lower(),
        "type":         "limit",
        "stopPrice":    str(round(stop_price, 8)),
        "price":        str(round(limit_price, 8)),
        "size":         str(round(size, 8)),
        "stop":         stop_type,
        "tradeType":    "TRADE",   # spot trade
    }
    result = await self.request("POST", "/api/v1/stop-order", body=body)
    order_id = result.get("orderId", "")
    logger.info(
        "🛡️  Stop order criada: %s %s stopPrice=%s limitPrice=%s orderId=%s",
        side.upper(), pair, stop_price, limit_price, order_id,
    )
    return result

async def cancel_stop_order(self, order_id: str) -> dict:
    """Cancela uma stop order pelo ID."""
    return await self.request("DELETE", f"/api/v1/stop-order/{order_id}")

async def get_open_stop_orders(self, pair: Optional[str] = None) -> list:
    """Lista stop orders abertas."""
    params = {}
    if pair:
        params["symbol"] = pair
    data = await self.request("GET", "/api/v1/stop-order", params=params)
    return data.get("items", []) if isinstance(data, dict) else data
```

### Passo 3 — Integrar no BotWorker: colocar stop nativo ao abrir posição

**Arquivo:** `backend/app/engine/worker.py` — `_open_position_handler()`

```python
async def _open_position_handler(self, price: float, signal):
    # ... código existente de abertura de posição ...

    # === NOVO: Colocar ordens nativas de TP/SL se configurado ===
    tp_cfg = self.config.get("take_profit", {})
    sl_cfg = self.config.get("stop_loss", {})

    # Stop-Loss nativo
    if sl_cfg and sl_cfg.get("use_native_order") and quantity > 0:
        sl_mode  = sl_cfg.get("mode", "percentage")
        sl_value = float(sl_cfg.get("value", 2.0))

        if sl_mode == "percentage":
            stop_price  = filled_price * (1 - sl_value / 100)
            limit_price = stop_price * 0.995   # 0.5% de slippage tolerance
        elif sl_mode == "fixed_price":
            stop_price  = sl_value
            limit_price = stop_price * 0.995

        try:
            sl_client_oid = str(uuid.uuid4())
            sl_order = await self._exchange.place_stop_order(
                pair=pair,
                side="sell",
                stop_price=round(stop_price, 8),
                limit_price=round(limit_price, 8),
                size=round(quantity, 8),
                client_oid=sl_client_oid,
                stop_type="loss",
            )
            self._open_position["native_sl_order_id"]  = sl_order.get("orderId", "")
            self._open_position["native_sl_stop_price"] = stop_price
            logger.info(
                "🛡️  Stop-Loss nativo @ %.4f (%.1f%%) — orderId=%s [bot=%s]",
                stop_price, sl_value, sl_order.get("orderId", ""), self.bot_id[:8],
            )
        except Exception as exc:
            logger.error("Falha ao criar stop-loss nativo: %s", exc)
            await self._log_event("ERROR", f"Falha ao criar SL nativo: {exc}")

    # Take-Profit nativo (ordem limit de venda acima do preço atual)
    if tp_cfg and tp_cfg.get("use_native_order") and quantity > 0:
        tp_mode  = tp_cfg.get("mode", "percentage")
        tp_value = float(tp_cfg.get("value", 5.0))

        if tp_mode == "percentage":
            tp_price = filled_price * (1 + tp_value / 100)
        elif tp_mode == "fixed_price":
            tp_price = tp_value

        try:
            tp_client_oid = str(uuid.uuid4())
            tp_order = await self._exchange.place_limit_order(
                pair=pair,
                side="sell",
                price=round(tp_price, 8),
                size=round(quantity, 8),
                client_oid=tp_client_oid,
            )
            self._open_position["native_tp_order_id"]  = tp_order.get("orderId", "")
            self._open_position["native_tp_price"]      = tp_price
            logger.info(
                "🎯 Take-Profit nativo @ %.4f (%.1f%%) — orderId=%s [bot=%s]",
                tp_price, tp_value, tp_order.get("orderId", ""), self.bot_id[:8],
            )
        except Exception as exc:
            logger.error("Falha ao criar take-profit nativo: %s", exc)

async def _close_position(self, current_price: float, reason: str):
    # === NOVO: Cancelar ordens nativas antes de fechar manualmente ===
    if self._open_position:
        native_sl_id = self._open_position.get("native_sl_order_id")
        native_tp_id = self._open_position.get("native_tp_order_id")

        for order_id in [native_sl_id, native_tp_id]:
            if order_id:
                try:
                    await self._exchange.cancel_stop_order(order_id)
                    logger.debug(
                        "Stop order nativa %s cancelada antes do fechamento manual.",
                        order_id,
                    )
                except Exception as exc:
                    logger.warning("Falha ao cancelar stop order nativa %s: %s", order_id, exc)

    # ... resto do código de fechamento existente ...
```

---

## 📂 Arquivos a Modificar

| Arquivo | Mudança |
|---|---|
| `backend/app/integrations/kucoin/rest_client.py` | `place_stop_order`, `cancel_stop_order`, `get_open_stop_orders` |
| `backend/app/engine/worker.py` | Colocar SL/TP nativo após abertura, cancelar antes de fechar |
| `backend/app/bots/schemas.py` | `TakeProfitConfig`, `StopLossConfig` no `BotConfigSchema` |

---

## ✅ Checklist Final

- [ ] `place_stop_order()` implementado e testado em sandbox
- [ ] SL nativo colocado imediatamente após fill de compra confirmado
- [ ] TP nativo (limit order) colocado imediatamente após fill
- [ ] Cancelamento de SL/TP nativo antes de qualquer fechamento manual
- [ ] Frontend allows configurar `use_native_order: true` por bot

---

<a id="doc-k06"></a>
# DOC-K06 — OCO (One-Cancels-the-Other) Correto para Spot na KuCoin

## 🎯 Objetivo

Implementar corretamente o par de ordens OCO para proteção de posições spot, garantindo que quando uma ordem (TP ou SL) for executada, a outra seja **automaticamente cancelada** — evitando venda dupla.

---

## 🚨 Problema Técnico Atual

A KuCoin **não tem OCO nativo** para spot (diferente da Binance). O sistema atual simplesmente coloca ordens de TP e SL independentes. Se ambas forem preenchidas (improvável mas possível em volatilidade extrema), o bot tentaria vender o dobro da posição.

Cenário de problema:
1. Bot compra 0.001 BTC
2. Coloca SL limit @ 39,000 (0.001 BTC)
3. Coloca TP limit @ 42,000 (0.001 BTC)
4. Preço cai drasticamente: SL executado (0.001 BTC vendido)
5. Antes do cancelamento: TP ainda ativo com 0.001 BTC
6. Mercado recupera: TP executado → bot tenta vender 0.001 BTC que não possui → erro ou venda a descoberto

---

## 🔎 Risco Real em Produção

| Cenário | Consequência |
|---|---|
| SL e TP executados em sequência (mercado volátil) | Venda dupla — saldo negativo ou rejeição da exchange |
| Cancelamento do OCO manual com delay | Janela de race condition onde ambas as ordens estão ativas |

---

## 🛠 Plano de Correção — OCO Emulado via WebSocket

**A solução correta** para KuCoin Spot é emular OCO via WebSocket: quando qualquer execução na posição for detectada, cancelar imediatamente a ordem complementar.

**Arquivo:** `backend/app/engine/worker.py`

```python
class BotWorker:
    # ...

    async def _handle_ws_message(self, msg: dict) -> None:
        """Handler expandido para OCO emulado."""
        topic = msg.get("topic", "")
        data  = msg.get("data", {})

        if "/spotMarket/tradeOrders" not in topic:
            return

        status   = data.get("status", "")
        order_id = data.get("orderId", "")
        side     = data.get("side", "")

        if status not in ("done", "match"):
            return

        if not self._open_position:
            return

        native_sl_id = self._open_position.get("native_sl_order_id")
        native_tp_id = self._open_position.get("native_tp_order_id")

        # === OCO: Se SL foi executado → cancelar TP ===
        if order_id == native_sl_id and side == "sell":
            logger.info(
                "🛡️  OCO: SL native executado (%s). Cancelando TP (%s). [bot=%s]",
                native_sl_id, native_tp_id, self.bot_id[:8],
            )
            if native_tp_id:
                try:
                    await self._exchange.cancel_order(native_tp_id)
                    logger.info("✅ OCO: TP %s cancelado com sucesso.", native_tp_id)
                except Exception as exc:
                    logger.error("❌ OCO: Erro ao cancelar TP %s: %s", native_tp_id, exc)
            # Registrar fechamento por SL
            exit_price = float(data.get("price") or data.get("matchPrice") or 0)
            await self._ocо_close_position(exit_price, "stop_loss_native")

        # === OCO: Se TP foi executado → cancelar SL ===
        elif order_id == native_tp_id and side == "sell":
            logger.info(
                "🎯 OCO: TP native executado (%s). Cancelando SL (%s). [bot=%s]",
                native_tp_id, native_sl_id, self.bot_id[:8],
            )
            if native_sl_id:
                try:
                    await self._exchange.cancel_stop_order(native_sl_id)
                    logger.info("✅ OCO: SL %s cancelado com sucesso.", native_sl_id)
                except Exception as exc:
                    logger.error("❌ OCO: Erro ao cancelar SL %s: %s", native_sl_id, exc)
            exit_price = float(data.get("price") or data.get("matchPrice") or 0)
            await self._ocо_close_position(exit_price, "take_profit_native")

    async def _ocо_close_position(self, exit_price: float, reason: str) -> None:
        """
        Registra fechamento de posição originado por evento OCO do WebSocket.
        NÃO envia nova ordem à exchange (a ordem OCO já foi executada).
        """
        if not self._open_position:
            return

        entry_funds  = self._open_position.get("entry_funds", 0)
        quantity     = self._open_position.get("entry_quantity", 0)
        exit_gross   = exit_price * quantity
        exit_fee     = exit_gross * 0.001   # estimativa — fee real virá do WS
        pnl_net      = exit_gross - exit_fee - entry_funds

        await self._persist_trade_close(
            order={"orderId": "", "fee": exit_fee},
            exit_price=exit_price,
            pnl_net=pnl_net,
            reason=reason,
        )
        await self._update_instance_metrics(pnl_net)
        await self._log_event(
            "TRADE",
            f"📉 OCO {reason.upper()} @ {exit_price:.4f} | PnL={pnl_net:+.4f} USDT",
        )
        session_stop = self._risk.record_trade_result(pnl_net)
        self._open_position = None
        if session_stop:
            await self._update_status("stopped", stop_reason=session_stop)
            self._stop_event.set()
```

---

## ✅ Checklist Final

- [ ] OCO emulado via WebSocket — SL executado → TP cancelado e vice-versa
- [ ] `_ocо_close_position()` NÃO envia nova ordem (evita venda dupla)
- [ ] Logs registram qual lado do OCO foi executado
- [ ] Reconciliação pós-restart verifica e cancela ordens órfãs

---

<a id="doc-k07"></a>
# DOC-K07 — Kill Switch com Contagem Real de Posições Abertas

## 🎯 Objetivo

Corrigir o `kill_switch_router.py` para que `open_positions` retorne a **contagem real de posições abertas na KuCoin**, consultando tanto o banco de dados local quanto a exchange via REST.

---

## 🚨 Problema Técnico Atual

**Arquivo:** `backend/app/trading/kill_switch_router.py`, linha 161

```python
open_positions=0,  # TODO: Implementar contagem de posições
```

O endpoint `/emergency/status` sempre retorna `open_positions=0`, independente do estado real. Isso significa:
- O usuário não sabe quantas posições serão afetadas ao acionar o kill switch
- O dashboard mostra informação incorreta
- Não há validação antes do kill switch de emergência

---

## 🛠 Plano de Correção

**Arquivo:** `backend/app/trading/kill_switch_router.py`

```python
from app.core.database import get_db
from bson import ObjectId

async def count_real_open_positions(user_id: str) -> dict:
    """
    Conta posições reais abertas combinando:
    1. Banco local (bot_trades onde status='open')
    2. user_bot_instances onde status='running' e current_position != None

    Retorna dict com contagens separadas.
    """
    db = get_db()

    # Posições abertas no banco de dados local
    local_open_count = await db["bot_trades"].count_documents({
        "user_id": user_id,
        "status": "open",
    })

    # Instâncias de bot ativas
    active_bots_cursor = db["user_bot_instances"].find({
        "user_id": user_id,
        "status": {"$in": ["running", "paused"]},
    }, {"_id": 1, "configuration": 1, "current_position": 1})
    active_bots = await active_bots_cursor.to_list(length=100)

    bots_with_position = [
        b for b in active_bots
        if b.get("current_position") is not None
    ]

    return {
        "active_bot_instances": len(active_bots),
        "local_open_trades": local_open_count,
        "bots_with_tracked_position": len(bots_with_position),
        # Total estimado (conservador — usar o maior)
        "estimated_open_positions": max(local_open_count, len(bots_with_position)),
    }


@router.get("/status", response_model=EmergencyStatusResponse)
async def get_emergency_status(current_user: dict = Depends(get_current_user)):
    """Status real do sistema de emergência."""
    user_id = str(current_user.get("_id") or current_user.get("id", ""))
    db = get_db()

    # Contagem de bots ativos
    active_bots = await db["user_bot_instances"].count_documents({
        "user_id": user_id,
        "status": {"$in": ["running", "paused"]},
    })

    # Contagem REAL de posições abertas
    positions_info = await count_real_open_positions(user_id)

    return EmergencyStatusResponse(
        active_bots=active_bots,
        open_positions=positions_info["estimated_open_positions"],
        kill_switch_available=True,
        positions_detail=positions_info,
    )
```

Atualizar `EmergencyStatusResponse`:

```python
class EmergencyStatusResponse(BaseModel):
    active_bots: int
    open_positions: int                    # era sempre 0 — agora real
    kill_switch_available: bool
    last_emergency: Optional[str] = None
    positions_detail: Optional[dict] = None  # NOVO: breakdown detalhado
```

### Verificação Real na Exchange durante Kill Switch

```python
@router.post("/panic")
async def emergency_panic(current_user: dict = Depends(get_current_user)):
    user_id = str(current_user.get("_id") or current_user.get("id", ""))
    db = get_db()

    # 1. Parar todos os bots
    await db["user_bot_instances"].update_many(
        {"user_id": user_id, "status": {"$in": ["running", "paused"]}},
        {"$set": {"status": "stopped", "stop_reason": "emergency_kill"}},
    )

    # 2. Notificar orchestrator via Redis
    from app.shared.redis_client import get_redis
    r = await get_redis()
    await r.publish(f"kill_switch:{user_id}", "emergency")

    # 3. Cancelar TODAS as ordens abertas na exchange via REST
    cancelled_orders = 0
    creds_doc = await db["exchange_credentials"].find_one(
        {"user_id": user_id, "exchange": "kucoin"}
    )
    if creds_doc:
        from app.security.cipher_singleton import get_cipher
        cipher = get_cipher()
        decrypted = cipher.decrypt_credentials(
            creds_doc["api_key_enc"],
            creds_doc["api_secret_enc"],
            creds_doc["passphrase_enc"],
        )
        from app.integrations.kucoin.rest_client import KuCoinRESTClient
        import os
        client = KuCoinRESTClient(
            api_key=decrypted["api_key"],
            api_secret=decrypted["api_secret"],
            api_passphrase=decrypted["passphrase"],
            sandbox=os.getenv("KUCOIN_SANDBOX", "false").lower() == "true",
        )
        try:
            # Cancelar todas as ordens spot
            result = await client.cancel_all_orders()
            cancelled_orders = result.get("cancelledOrderIds", [])
            logger.info(
                "🚨 Kill Switch: %d ordens canceladas para user %s",
                len(cancelled_orders), user_id,
            )
        except Exception as exc:
            logger.error("Erro ao cancelar ordens no kill switch: %s", exc)
        finally:
            await client.close()

    # 4. Marcar posições locais como encerradas por emergência
    await db["bot_trades"].update_many(
        {"user_id": user_id, "status": "open"},
        {"$set": {"status": "emergency_closed", "exit_reason": "emergency_kill"}},
    )

    return {
        "status": "emergency_activated",
        "bots_stopped": True,
        "exchange_orders_cancelled": len(cancelled_orders) if isinstance(cancelled_orders, list) else 0,
        "message": "Kill switch ativado. Todas as ordens foram canceladas.",
    }
```

---

## ✅ Checklist Final

- [ ] `open_positions` retorna contagem real (não mais hardcoded `0`)
- [ ] Kill switch cancela ordens na exchange via REST (não apenas no banco local)
- [ ] `EmergencyStatusResponse` inclui `positions_detail`
- [ ] Redis pub/sub notifica orchestrator do kill switch

---

<a id="doc-k08"></a>
# DOC-K08 — Reconexão Automática de WebSocket e Resubscrição

## 🎯 Objetivo

Garantir que o WebSocket da KuCoin reconecte automaticamente com **token fresco**, resubscreva em todos os tópicos anteriores, e sincronize o estado perdido durante o período offline.

---

## 🚨 Problema Técnico Atual

**Arquivo:** `backend/app/integrations/kucoin/ws_client.py`

O `KuCoinWebSocketClient` já tem reconexão implementada com backoff exponencial. **Problemas identificados:**

1. **Token expirado:** O token WS da KuCoin expira em 24h. Após reconexão, o mesmo token pode ser reutilizado se o `_connect_once` chamar `get_ws_token()` de novo — mas o `_RECONNECT_MAX_WAIT` de 60s pode ser atingido antes do token expirar, o que é correto. Verificar que **cada tentativa de reconexão chama `get_ws_token()` com um token NOVO**.

2. **Ping loop não cancelado corretamente:** Se o ping task não for cancelado antes da reconexão, dois ping loops podem rodar simultaneamente.

3. **Eventos perdidos durante offline:** O sistema não tem mecanismo de "catch-up" — eventos ocorridos durante a desconexão são perdidos.

---

## 🛠 Plano de Correção

**Arquivo:** `backend/app/integrations/kucoin/ws_client.py`

```python
async def _connect_once(self) -> None:
    """
    Tenta UMA conexão WebSocket.
    Cada chamada obtém um token NOVO — nunca reutiliza token de sessão anterior.
    """
    # === CORREÇÃO 1: Token sempre fresco por tentativa ===
    token, ws_url, ping_interval_s = await self.rest.get_ws_token(
        private=self.private
    )
    logger.debug("WS token obtido (expira em ~24h): ...%s", token[-8:])

    # === CORREÇÃO 2: Cancelar ping task anterior antes de criar novo ===
    if self._ping_task and not self._ping_task.done():
        self._ping_task.cancel()
        try:
            await self._ping_task
        except asyncio.CancelledError:
            pass
        self._ping_task = None

    # Gerenciar sessão aiohttp separada por conexão
    if self._session and not self._session.closed:
        await self._session.close()

    self._session = aiohttp.ClientSession()
    try:
        async with self._session.ws_connect(
            ws_url,
            heartbeat=None,
            receive_timeout=ping_interval_s * 2,
            max_msg_size=0,   # sem limite de tamanho de mensagem
        ) as ws:
            self._ws = ws
            self._reconnect_count = 0
            label = "private" if self.private else "public"
            logger.info("✅ WebSocket KuCoin conectado (%s) — ping=%.0fs", label, ping_interval_s)

            # Replay subscriptions
            for sub in list(self._subscriptions):
                await self._send_subscribe(sub["topic"], sub["private"])
                await asyncio.sleep(0.1)   # pequeno delay entre subs

            # Iniciar ping loop
            self._ping_task = asyncio.create_task(
                self._ping_loop(ws, ping_interval_s),
                name=f"ws_ping_{label}",
            )

            await self._message_loop(ws)

    finally:
        if self._session and not self._session.closed:
            await self._session.close()

async def _message_loop(self, ws: aiohttp.ClientWebSocketResponse) -> None:
    """Loop de leitura de mensagens com tratamento de tipos."""
    async for raw in ws:
        if raw.type == aiohttp.WSMsgType.TEXT:
            try:
                msg = json.loads(raw.data)
            except json.JSONDecodeError:
                logger.warning("WS mensagem inválida (não-JSON): %s", raw.data[:100])
                continue

            msg_type = msg.get("type", "")

            if msg_type == "welcome":
                logger.debug("WS: welcome recebido")
            elif msg_type == "pong":
                logger.debug("WS: pong recebido")
            elif msg_type == "ack":
                logger.debug("WS: ack de subscription: topic=%s", msg.get("topic"))
            elif msg_type == "error":
                logger.error("WS: erro do servidor KuCoin: %s", msg)
            elif msg_type == "message":
                try:
                    result = self.on_message(msg)
                    if asyncio.iscoroutine(result):
                        await result
                except Exception as cb_exc:
                    logger.error("Erro no handler de mensagem WS: %s", cb_exc, exc_info=True)

        elif raw.type == aiohttp.WSMsgType.CLOSED:
            logger.warning("WS: conexão fechada pelo servidor (code=%s)", ws.close_code)
            break
        elif raw.type == aiohttp.WSMsgType.ERROR:
            logger.error("WS: erro de protocolo: %s", ws.exception())
            break

async def _ping_loop(
    self,
    ws: aiohttp.ClientWebSocketResponse,
    interval_s: float,
) -> None:
    """
    Envio periódico de ping.
    KuCoin recomenda 80% do intervalo (pingTimeout).
    """
    ping_interval = interval_s * 0.8
    try:
        while not ws.closed:
            await asyncio.sleep(ping_interval)
            if ws.closed:
                break
            msg_id = self._next_id()
            await ws.send_str(json.dumps({"id": msg_id, "type": "ping"}))
            logger.debug("WS ping enviado (id=%s)", msg_id)
    except asyncio.CancelledError:
        pass
    except Exception as exc:
        logger.warning("WS ping loop encerrado: %s", exc)
```

### Catch-up de estado pós-reconexão

```python
async def _on_ws_disconnect(self, reconnect_count: int) -> None:
    """
    Chamado antes de cada reconexão.
    Consulta REST para recuperar eventos perdidos durante offline.
    """
    logger.warning(
        "📡 WS offline — reconciliando estado (reconexão %d). [bot=%s]",
        reconnect_count, self.bot_id[:8],
    )

    if reconnect_count == 0:
        return  # primeira desconexão — aguardar reconexão antes de reconciliar

    # Verificar ordens abertas na exchange
    await self._reconcile_position_via_rest()

    # Verificar se stop orders nativas foram executadas durante offline
    if self._open_position:
        pair = self.config.get("pair", "BTC-USDT")
        try:
            open_stop_orders = await self._exchange.get_open_stop_orders(pair)
            open_stop_ids = {o.get("id") for o in open_stop_orders}

            native_sl_id = self._open_position.get("native_sl_order_id")
            native_tp_id = self._open_position.get("native_tp_order_id")

            # Se SL sumiu das stop orders abertas → foi executado durante offline
            if native_sl_id and native_sl_id not in open_stop_ids:
                logger.warning(
                    "🔄 Catch-up: SL nativo %s executado durante offline. "
                    "Fechando posição local. [bot=%s]",
                    native_sl_id, self.bot_id[:8],
                )
                await self._ocо_close_position(
                    exit_price=self._open_position.get("native_sl_stop_price", 0),
                    reason="stop_loss_native_offline",
                )
        except Exception as exc:
            logger.error("Erro no catch-up pós-reconexão: %s", exc)
```

---

## ✅ Checklist Final

- [ ] Token WS obtido NOVO em cada tentativa de reconexão
- [ ] Ping task anterior cancelado antes de criar novo
- [ ] `_message_loop()` trata todos os tipos: welcome, pong, ack, error, message
- [ ] `_on_ws_disconnect()` reconcilia estado via REST após reconexão
- [ ] Catch-up verifica stop orders nativas executadas durante offline

---

<a id="doc-k09"></a>
# DOC-K09 — Consistência de Estado após Restart da Engine

## 🎯 Objetivo

Garantir que ao reiniciar a engine (deploy, crash, OOM), todos os `BotWorker`s recuperem seus estados anteriores corretamente — sem criar posições duplicadas, sem perder posições existentes, e sem operar em estado inválido.

---

## 🚨 Problema Técnico Atual

**Arquivo:** `backend/app/engine/orchestrator.py`

Ao reiniciar, o `BotOrchestrator` carrega instâncias com `status="running"` do banco e reinicia os workers. **O que não é feito:**

1. Verificação se `_open_position` (estado em memória) deveria ser restaurado a partir do banco
2. Cancelamento de ordens pendentes órfãs (intents no estado "sent" sem confirmação)
3. Verificação de ordens abertas na exchange que não estão no banco
4. Reconciliação de `order_intents` pendentes

---

## 🛠 Plano de Correção — Startup Reconciliation

**Arquivo a criar:** `backend/app/engine/startup_reconciler.py`

```python
"""
StartupReconciler — Reconciliação de estado ao iniciar a engine.

Executado UMA VEZ durante o startup do BotOrchestrator, antes de
iniciar qualquer BotWorker.

Responsabilidades:
1. Detectar order_intents no estado "sent" (ordens em trânsito no crash anterior)
2. Verificar via REST se essas ordens foram preenchidas ou canceladas
3. Atualizar bot_trades de acordo
4. Restaurar _open_position nos instances que têm trade aberto
5. Cancelar stop orders nativas órfãs
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("engine.startup_reconciler")


class StartupReconciler:

    def __init__(self, db, rest_client_factory):
        """
        db: instância Motor do MongoDB
        rest_client_factory: callable(user_id) → KuCoinRESTClient (com credenciais descriptografadas)
        """
        self._db      = db
        self._factory = rest_client_factory

    async def run(self) -> dict:
        """
        Executa reconciliação completa.
        Retorna relatório do que foi reconciliado.
        """
        report = {
            "instances_checked": 0,
            "intents_reconciled": 0,
            "positions_restored": 0,
            "orphan_orders_cancelled": 0,
            "errors": [],
        }

        # Buscar todas as instâncias que estavam "running" antes do crash
        cursor = self._db["user_bot_instances"].find(
            {"status": {"$in": ["running", "paused", "stopped"]}},
            # Incluir instâncias paradas recentemente (últimas 24h)
        )
        instances = await cursor.to_list(length=500)
        report["instances_checked"] = len(instances)

        for instance in instances:
            try:
                await self._reconcile_instance(instance, report)
            except Exception as exc:
                err = f"Erro reconciliando instance {instance.get('_id')}: {exc}"
                logger.error(err)
                report["errors"].append(err)

        logger.info(
            "✅ Startup reconciliation completa: %s", report
        )
        return report

    async def _reconcile_instance(self, instance: dict, report: dict) -> None:
        """Reconcilia UMA instância de bot."""
        instance_id = str(instance["_id"])
        user_id     = instance.get("user_id", "")

        # 1. Verificar se existe trade aberto no banco
        open_trade = await self._db["bot_trades"].find_one({
            "bot_instance_id": instance_id,
            "status": "open",
        })

        # 2. Verificar order_intents pendentes
        pending_intents = await self._db["order_intents"].find({
            "bot_instance_id": instance_id,
            "state": {"$in": ["pending", "sent"]},
        }).to_list(length=10)

        if not open_trade and not pending_intents:
            return  # Instância sem estado pendente — OK

        # 3. Obter client REST para este usuário
        try:
            rest_client = await self._factory(user_id)
        except Exception as exc:
            logger.warning(
                "Não foi possível criar REST client para user %s: %s", user_id, exc
            )
            return

        # 4. Reconciliar order_intents pendentes
        for intent in pending_intents:
            await self._reconcile_intent(intent, rest_client, report)

        # 5. Verificar se trade aberto ainda é real
        if open_trade:
            exchange_order_id = open_trade.get("exchange_order_id", "")
            if exchange_order_id:
                try:
                    order_data = await rest_client.get_order(exchange_order_id)
                    is_active  = order_data.get("isActive", False)
                    deal_size  = float(order_data.get("dealSize") or 0)

                    if deal_size > 0:
                        # Ordem preenchida — trade está aberto, restaurar posição
                        logger.info(
                            "✅ Trade aberto restaurado: instance=%s orderId=%s",
                            instance_id, exchange_order_id,
                        )
                        report["positions_restored"] += 1
                    else:
                        # Ordem não preenchida — limpar trade local
                        await self._db["bot_trades"].update_one(
                            {"_id": open_trade["_id"]},
                            {"$set": {
                                "status": "cancelled",
                                "exit_reason": "unfilled_on_restart",
                                "exit_timestamp": datetime.now(timezone.utc),
                            }}
                        )
                        logger.warning(
                            "⚠️  Trade local limpo (não preenchido): instance=%s", instance_id
                        )
                except Exception as exc:
                    logger.warning(
                        "Não foi possível verificar ordem %s: %s", exchange_order_id, exc
                    )

        try:
            await rest_client.close()
        except Exception:
            pass

    async def _reconcile_intent(self, intent: dict, rest_client, report: dict) -> None:
        """Reconcilia um order_intent pendente verificando seu estado na exchange."""
        client_oid        = intent.get("client_oid", "")
        exchange_order_id = intent.get("exchange_order_id")

        if not exchange_order_id:
            # Intent "pending" — ordem nunca enviada (crash antes do envio)
            # Marcar como erro — será tratado como não executado
            await self._db["order_intents"].update_one(
                {"client_oid": client_oid},
                {"$set": {
                    "state": "error",
                    "error": "never_sent_crash_before_send",
                    "resolved_at": datetime.now(timezone.utc),
                }}
            )
            report["intents_reconciled"] += 1
            return

        # Intent "sent" — verificar se a ordem chegou na exchange
        try:
            order_data = await rest_client.get_order(exchange_order_id)
            status     = order_data.get("isActive", False)
            deal_size  = float(order_data.get("dealSize") or 0)

            if deal_size > 0:
                # Preenchida — marcar como filled
                await self._db["order_intents"].update_one(
                    {"client_oid": client_oid},
                    {"$set": {
                        "state": "filled",
                        "resolved_at": datetime.now(timezone.utc),
                    }}
                )
                logger.info("Intent %s: FILLED (reconciliado no restart)", client_oid[:8])
            else:
                # Não preenchida — cancelar mais tarde
                await self._db["order_intents"].update_one(
                    {"client_oid": client_oid},
                    {"$set": {
                        "state": "error",
                        "error": "not_filled_on_restart",
                        "resolved_at": datetime.now(timezone.utc),
                    }}
                )
                logger.warning("Intent %s: NÃO PREENCHIDA (limpo no restart)", client_oid[:8])

            report["intents_reconciled"] += 1

        except Exception as exc:
            logger.error(
                "Erro ao reconciliar intent %s (orderId=%s): %s",
                client_oid[:8], exchange_order_id, exc,
            )
```

### Integrar no startup do Orchestrator

**Arquivo:** `backend/app/engine/orchestrator.py`

```python
async def start(self) -> None:
    """Inicia o orchestrator com reconciliação de estado."""
    from app.core.database import get_db
    from app.engine.startup_reconciler import StartupReconciler

    logger.info("🚀 BotOrchestrator iniciando...")
    db = get_db()

    # === RECONCILIAÇÃO DE STARTUP (NOVO) ===
    async def rest_client_factory(user_id: str):
        from app.security.cipher_singleton import get_cipher
        from app.integrations.kucoin.rest_client import KuCoinRESTClient
        import os

        cipher   = get_cipher()
        creds    = await db["exchange_credentials"].find_one(
            {"user_id": user_id, "exchange": "kucoin"}
        )
        if not creds:
            raise ValueError(f"Sem credenciais para {user_id}")
        dec = cipher.decrypt_credentials(
            creds["api_key_enc"], creds["api_secret_enc"], creds["passphrase_enc"]
        )
        return KuCoinRESTClient(
            api_key=dec["api_key"],
            api_secret=dec["api_secret"],
            api_passphrase=dec["passphrase"],
            sandbox=os.getenv("KUCOIN_SANDBOX", "false").lower() == "true",
        )

    reconciler = StartupReconciler(db, rest_client_factory)
    report = await reconciler.run()
    logger.info("Reconciliação de startup: %s", report)

    # ... resto do startup existente (carregar e iniciar workers) ...
```

---

## ✅ Checklist Final

- [ ] `StartupReconciler` executa ANTES de qualquer `BotWorker` iniciar
- [ ] `order_intents` em "pending" marcados como erro (nunca enviados)
- [ ] `order_intents` em "sent" verificados via REST — filled ou limpos
- [ ] Trades locais "open" com ordem inexistente na exchange são limpos
- [ ] Relatório de reconciliação salvo em log estruturado

---

<a id="doc-k10"></a>
# DOC-K10 — Race Condition entre Strategy → OrderManager → Exchange

## 🎯 Objetivo

Eliminar a condição de corrida onde dois ciclos de tick simultâneos podem ambos detectar sinal de compra e enviar duas ordens à exchange antes que `_open_position` seja definido.

---

## 🚨 Problema Técnico Atual

**Arquivo:** `backend/app/engine/worker.py`

```python
# FLUXO ATUAL — VULNERÁVEL A RACE CONDITION:
async def _do_execute_cycle(self, tick: dict):
    # ...
    signal = await self._strategy.calculate(candles, current_price)   # ← await 1
    # ...
    if signal.action == "buy" and not self._open_position:             # ← check
        await self._open_position_handler(current_price, signal)       # ← await 2
```

O problema: entre o `not self._open_position` (check) e o `_open_position_handler` (quando `self._open_position` é de fato definido), existe um gap de **múltiplos awaits**. Em Python asyncio, qualquer `await` é um ponto de troca de contexto. Se outro tick chegar e entrar no ciclo durante esse gap, ele também verá `_open_position = None` e enviará outra ordem de compra.

O lock distribuído Redis (`acquire_lock`) previne execução **entre instâncias diferentes do mesmo bot**, mas não previne race condition **intra-worker** se o loop de ticks for mais rápido que o cycle.

**Cenário concreto:**
```
Tick 1 → strategy.calculate() → await (yield control)
Tick 2 → chega, entra no ciclo, passa no lock (mesmo bot, mesmo par)
Tick 1 → volta → open_position is None → ENVIA ORDEM
Tick 2 → open_position AINDA é None → ENVIA SEGUNDA ORDEM
```

---

## 🛠 Plano de Correção — Guard em Memória + Lock

**Arquivo:** `backend/app/engine/worker.py`

```python
class BotWorker:

    def __init__(self, instance: dict):
        # ... código existente ...
        self._open_position: Optional[dict] = None

        # === NOVO: Guard para prevenir race condition intra-worker ===
        self._order_in_progress: bool = False
        self._cycle_lock: asyncio.Lock = asyncio.Lock()

    async def _do_execute_cycle(self, tick: dict):
        """Cycle com proteção contra race condition."""
        current_price: float = tick["price"]

        # === GUARD 1: Lock de ciclo (apenas um ciclo por vez no worker) ===
        if self._cycle_lock.locked():
            logger.debug(
                "Ciclo pulado — ciclo anterior ainda em execução. [bot=%s]",
                self.bot_id[:8],
            )
            return

        async with self._cycle_lock:
            await self._do_execute_cycle_locked(tick, current_price)

    async def _do_execute_cycle_locked(self, tick: dict, current_price: float):
        """
        Lógica real do ciclo — executada apenas quando o cycle_lock está adquirido.
        Garante que apenas um ciclo completo executa por vez dentro do worker.
        """

        # ── 1. Check risk on open position ─────────────────────────────────
        if self._open_position:
            exit_reason = self._risk.check_position_exit(
                entry_price=self._open_position["entry_price"],
                current_price=current_price,
                entry_timestamp=self._open_position["entry_timestamp"],
            )
            if exit_reason:
                await self._close_position(current_price, reason=exit_reason)
                return

        # ── 2. Guard: não abrir posição se outra ordem está em andamento ───
        if self._order_in_progress:
            logger.debug(
                "Sinal ignorado — ordem em andamento. [bot=%s]", self.bot_id[:8]
            )
            return

        # ── 3. Fetch candles ────────────────────────────────────────────────
        candles = await self._exchange.get_candles(
            pair=self.config.get("pair", "BTC-USDT"),
            timeframe=self.config.get("timeframe", "1h"),
            limit=200,
        )
        if not candles:
            return

        # ── 4. Strategy signal ──────────────────────────────────────────────
        signal = await self._strategy.calculate(candles, current_price)
        if signal.action == "hold":
            return

        # ── 5. Session risk ─────────────────────────────────────────────────
        stop_reason = await self._check_session_risk(signal.action)
        if stop_reason:
            await self._update_status("stopped", stop_reason=stop_reason)
            self._stop_event.set()
            return

        # ── 6. Place order — protegido pelo cycle_lock ─────────────────────
        if signal.action == "buy" and not self._open_position and not self._order_in_progress:
            # === GUARD 2: marcar flag ANTES de qualquer await ===
            self._order_in_progress = True
            try:
                await self._open_position_handler(current_price, signal)
            finally:
                self._order_in_progress = False

        elif signal.action == "sell" and self._open_position and not self._order_in_progress:
            self._order_in_progress = True
            try:
                await self._close_position(current_price, reason="strategy_signal")
            finally:
                self._order_in_progress = False

    async def _open_position_handler(self, price: float, signal):
        """
        Protegido pelo cycle_lock e pelo _order_in_progress flag.
        Não pode ser chamado duas vezes simultaneamente.
        """
        # Dupla verificação dentro do guard
        if self._open_position:
            logger.warning(
                "⚠️  _open_position_handler chamado mas _open_position já existe. "
                "Race condition evitado. [bot=%s]", self.bot_id[:8],
            )
            return

        # ... resto do código existente de abertura de posição ...
```

### Validação de consistência extra — double-check na exchange

```python
    async def _open_position_handler(self, price: float, signal):
        """Abre posição com double-check de segurança."""
        pair = self.config.get("pair", "BTC-USDT")

        # === DOUBLE-CHECK: Consultar ordens abertas na exchange ===
        # Previne abertura de posição duplicada se o banco local estiver desatualizado
        try:
            open_orders = await self._exchange.get_open_orders(pair)
            if open_orders:
                logger.warning(
                    "⚠️  Existem %d ordens abertas na exchange antes de abrir nova posição. "
                    "Abortando para evitar duplicata. [bot=%s]",
                    len(open_orders), self.bot_id[:8],
                )
                return
        except Exception as exc:
            logger.warning(
                "Não foi possível verificar ordens abertas: %s. Prosseguindo com cautela.",
                exc,
            )

        # ... resto do código ...
```

---

## 📂 Arquivos a Modificar

| Arquivo | Mudança |
|---|---|
| `backend/app/engine/worker.py` | `_cycle_lock`, `_order_in_progress`, `_do_execute_cycle_locked()`, double-check |

---

## 🧪 Estratégia de Testes

```python
# tests/test_race_condition.py

import asyncio
import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.anyio
async def test_concurrent_ticks_only_one_order_placed():
    """
    Simula dois ticks chegando "simultaneamente" (entre awaits).
    Garante que apenas UMA ordem de compra é enviada.
    """
    worker = create_test_worker()

    order_call_count = 0

    async def mock_place_order(*args, **kwargs):
        nonlocal order_call_count
        order_call_count += 1
        await asyncio.sleep(0.05)  # simula latência da exchange
        return {"orderId": f"ORDER-{order_call_count}", "dealPrice": "40000", "dealFunds": "100", "fee": "0.1"}

    worker._exchange.place_market_order = mock_place_order

    # Simular dois ticks simultâneos
    tick_a = {"price": 40000.0}
    tick_b = {"price": 40010.0}

    await asyncio.gather(
        worker._execute_cycle(tick_a),
        worker._execute_cycle(tick_b),
    )

    # Apenas uma ordem deve ter sido colocada
    assert order_call_count <= 1, (
        f"Race condition: {order_call_count} ordens colocadas quando apenas 1 era esperada"
    )

@pytest.mark.anyio
async def test_order_in_progress_blocks_new_signal():
    worker = create_test_worker()
    worker._order_in_progress = True

    # Mesmo com sinal válido, não deve colocar ordem
    with patch.object(worker, '_open_position_handler', new_callable=AsyncMock) as mock_handler:
        await worker._do_execute_cycle({"price": 40000.0})
        mock_handler.assert_not_called()
```

---

## 📈 Impacto na Estabilidade

- **Elimina ordens duplicadas** causadas por race condition intra-worker
- `asyncio.Lock` é de custo zero quando não há contenção (caso normal)
- Double-check na exchange adiciona 1 request REST por abertura de posição (~50ms) — aceitável

## ✅ Checklist Final

- [ ] `_cycle_lock: asyncio.Lock` adicionado ao `__init__` do BotWorker
- [ ] `_order_in_progress: bool` adicionado ao `__init__`
- [ ] `_execute_cycle()` retorna imediatamente se lock está ocupado
- [ ] `_order_in_progress = True` definido ANTES do primeiro `await` em `_open_position_handler`
- [ ] `_order_in_progress` reset em bloco `finally`
- [ ] Double-check de ordens abertas antes de abrir nova posição
- [ ] Testes de race condition passando

---

## RESUMO EXECUTIVO — PRIORIDADE DE IMPLEMENTAÇÃO

| Prioridade | Doc | Risco Financeiro | Complexidade |
|---|---|---|---|
| 🔴 CRÍTICO | DOC-K01 — Criptografia | API Secret exposta → conta comprometida | Média |
| 🔴 CRÍTICO | DOC-K04 — Idempotência | Ordens duplicadas → dobro do capital | Média |
| 🔴 CRÍTICO | DOC-K10 — Race Condition | Ordens duplicadas por concorrência | Baixa |
| 🟠 ALTO | DOC-K03 — WS Execution Reports | Partial fills → venda da quantidade errada | Alta |
| 🟠 ALTO | DOC-K05 — TP/SL Nativos | Engine offline → sem stop de proteção | Média |
| 🟠 ALTO | DOC-K06 — OCO Spot | Venda dupla = posição descoberta | Média |
| 🟠 ALTO | DOC-K07 — Kill Switch Real | Dashboard mostra `0` posições → ação errada | Baixa |
| 🟡 MÉDIO | DOC-K02 — Rate Limit Nativo | 429 em cascata → bots sem controle | Baixa |
| 🟡 MÉDIO | DOC-K08 — WS Reconexão | Período offline sem estado correto | Alta |
| 🟡 MÉDIO | DOC-K09 — Restart Consistency | Posições duplicadas após deploy | Alta |

---

## ARQUITETURA FINAL ESPERADA

```
Frontend SaaS (React)
        │
        │  HTTPS / WSS
        ▼
FastAPI Backend (uvicorn)
        │
        ├── Auth & JWT
        ├── Plan limits & quota check
        ├── Credential encryption (Fernet)
        │
        ▼
Trading Engine (única instância asyncio)
        │
        ├── BotOrchestrator
        │     └── BotWorker × N (one per active bot)
        │           ├── _cycle_lock (anti-race)
        │           ├── _order_in_progress (anti-duplicate)
        │           ├── OrderIntentStore (write-ahead log)
        │           └── WebSocket privado (execution reports)
        │
        ├── StartupReconciler (on startup)
        │
        └── KuCoin Integration
              ├── REST Client
              │     ├── HMAC-SHA256 signing
              │     ├── gw-ratelimit-* header tracking
              │     ├── Exponential backoff retry
              │     ├── place_stop_order() [TP/SL nativo]
              │     └── cancel_all_orders() [kill switch]
              │
              └── WebSocket Client
                    ├── Token fresco por reconexão
                    ├── Ping loop (80% interval)
                    ├── Execution reports → OCO emulado
                    └── Catch-up pós-reconexão via REST
```

---

*Documento gerado para uso interno de engenharia.*
*Todas as implementações são específicas para a KuCoin. Nenhuma abstração multi-exchange é necessária ou desejada.*
