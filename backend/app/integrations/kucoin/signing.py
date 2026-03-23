"""
KuCoin HMAC-SHA256 request signing — DOC_04 §2.

KuCoin v2 API requires five authentication headers per private request.
All calculations here are pure functions — no side effects, easy to test.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import time


def build_signature(
    api_secret: str,
    timestamp: str,
    method: str,
    endpoint: str,
    body: str = "",
) -> str:
    """
    Compute the HMAC-SHA256 request signature.

    signature = base64(HMAC-SHA256(api_secret, timestamp + METHOD + endpoint + body))

    Args:
        api_secret: KuCoin API secret.
        timestamp:  Unix timestamp in milliseconds as a string.
        method:     HTTP method, e.g. "GET", "POST", "DELETE".
        endpoint:   Path + query string, e.g. "/api/v1/orders?status=active".
        body:       JSON body string (empty string for GET requests).
    """
    message = f"{timestamp}{method.upper()}{endpoint}{body}"
    mac = hmac.new(
        api_secret.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    )
    return base64.b64encode(mac.digest()).decode("utf-8")


def build_passphrase_signature(api_secret: str, passphrase: str) -> str:
    """
    Encrypt the API passphrase with HMAC-SHA256 (required for v2 keys).

    KC-API-KEY-VERSION: "2" → passphrase must be signed, not raw.
    """
    mac = hmac.new(
        api_secret.encode("utf-8"),
        passphrase.encode("utf-8"),
        hashlib.sha256,
    )
    return base64.b64encode(mac.digest()).decode("utf-8")


def build_auth_headers(
    api_key: str,
    api_secret: str,
    api_passphrase: str,
    method: str,
    endpoint: str,
    body: str = "",
) -> dict:
    """
    Generate all five KuCoin authentication headers for a single request.

    Usage:
        headers = build_auth_headers(key, secret, passphrase, "POST", "/api/v1/orders", body_str)
        async with session.post(url, headers=headers, data=body_str) as resp: ...

    Returns a dict ready to be merged into your request headers.
    """
    timestamp = str(int(time.time() * 1000))
    return {
        "KC-API-KEY": api_key,
        "KC-API-SIGN": build_signature(api_secret, timestamp, method, endpoint, body),
        "KC-API-TIMESTAMP": timestamp,
        "KC-API-PASSPHRASE": build_passphrase_signature(api_secret, api_passphrase),
        "KC-API-KEY-VERSION": "2",
        "Content-Type": "application/json",
    }
