"""
Utilities para autenticação e segurança
"""

from fastapi import Request
from typing import Optional


def get_client_ip(request: Optional[Request]) -> str:
    """
    Obter IP do cliente da requisição.
    
    Args:
        request: Requisição FastAPI
        
    Returns:
        IP do cliente ou "unknown" se não disponível
    """
    if not request:
        return "unknown"
    
    if request.client:
        return request.client.host
    
    # Verificar headers proxy
    if "x-forwarded-for" in request.headers:
        # x-forwarded-for pode ter múltiplos IPs, pega o primeiro
        return request.headers["x-forwarded-for"].split(",")[0].strip()
    
    if "x-real-ip" in request.headers:
        return request.headers["x-real-ip"]
    
    return "unknown"
