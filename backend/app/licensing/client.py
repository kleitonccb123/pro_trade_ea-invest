from __future__ import annotations

import asyncio
from typing import Optional

import httpx

from app.core.config import settings
from app.licensing.schemas import LicenseResponse
from datetime import datetime


async def fetch_remote_license() -> LicenseResponse:
    """
    Legado: busca licença de endpoint HTTP externo (LICENSING_URL).

    AVISO: Esta função é mantida apenas para compatibilidade com
    configurações que usam LICENSING_URL. O novo sistema (DOC-07) usa
    LicensingService com MongoDB + Redis diretamente, sem HTTP externo.

    CRÍTICO — DEV BYPASS REMOVIDO (DOC-07):
    Se LICENSING_URL não estiver configurado, retorna plano 'free'.
    NUNCA retornar Premium como fallback.
    """
    url = settings.licensing_url
    if not url:
        # DOC-07: sem URL configurada → free (não Premium)
        # O sistema real usa LicensingService com MongoDB.
        return LicenseResponse(valid=True, plan="free", features={})

    timeout = settings.licensing_timeout
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        payload = resp.json()
        expires = None
        if payload.get("expires_at"):
            try:
                expires = datetime.fromisoformat(payload.get("expires_at"))
            except Exception:
                expires = None
        return LicenseResponse(
            valid=bool(payload.get("valid", False)),
            plan=payload.get("plan", "free"),
            features=payload.get("features", {}),
            expires_at=expires,
        )
