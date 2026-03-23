"""
pytest configuration and shared fixtures
"""

import pytest
import os

def pytest_addoption(parser):
    """Adiciona opções customizadas ao pytest."""
    parser.addoption(
        "--base-url",
        action="store",
        default=os.getenv("BASE_URL", "http://localhost:8000"),
        help="URL base do servidor (default: http://localhost:8000 ou $BASE_URL)"
    )
    parser.addoption(
        "--timeout",
        action="store",
        default=os.getenv("TIMEOUT", "30"),
        type=int,
        help="Timeout para requisições (default: 30s ou $TIMEOUT)"
    )


@pytest.fixture(scope="session")
def base_url(request):
    """Retorna a URL base do servidor."""
    return request.config.getoption("--base-url").rstrip('/')


@pytest.fixture(scope="session")
def timeout(request):
    """Retorna o timeout configurado."""
    return request.config.getoption("--timeout")
