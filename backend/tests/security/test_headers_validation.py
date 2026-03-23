"""
? Security Headers Validation Test
Valida presen?a de 7 Security Headers em m?ltiplos endpoints

Requisitos:
  pip install requests

Uso:
  python backend/tests/security/test_headers_validation.py

Valida??o:
  ? Todos os 7 headers presentes
  ? Valores corretos
  ? Consist?ncia em m?ltiplos endpoints
  ? Performance sem overhead
"""

import requests
import json
import time
from typing import Dict, List, Tuple
from dataclasses import dataclass
from enum import Enum
import statistics

# ============================================
# Configura??o
# ============================================

BASE_URL = "http://localhost:8000"
ENDPOINTS_TO_TEST = [
    ("/health", "GET"),
    ("/docs", "GET"),
    ("/redoc", "GET"),
]
NUM_REQUESTS_PER_ENDPOINT = 10  # Para medir performance

# ============================================
# Headers Esperados
# ============================================

REQUIRED_HEADERS = {
    "Strict-Transport-Security": {
        "description": "Force HTTPS (HSTS)",
        "expected_pattern": "max-age=",
        "critical": False,  # Pode estar vazio em dev
    },
    "X-Content-Type-Options": {
        "description": "MIME type sniffing protection",
        "expected_value": "nosniff",
        "critical": True,
    },
    "X-Frame-Options": {
        "description": "Clickjacking protection",
        "expected_value": "DENY",
        "critical": True,
    },
    "X-XSS-Protection": {
        "description": "XSS protection (legacy browsers)",
        "expected_pattern": "1",
        "critical": True,
    },
    "Content-Security-Policy": {
        "description": "XSS/Injection prevention",
        "expected_pattern": "default-src",
        "critical": True,
    },
    "Referrer-Policy": {
        "description": "Referrer privacy control",
        "expected_pattern": "origin",
        "critical": True,
    },
    "Permissions-Policy": {
        "description": "Browser feature restrictions",
        "expected_pattern": "()",
        "critical": True,
    },
}


class HeaderStatus(Enum):
    """Status de um header"""
    PRESENT = "? Present"
    MISSING = "? Missing"
    INVALID_VALUE = "??  Invalid Value"
    EMPTY = "??  Empty"


@dataclass
class HeaderValidation:
    """Resultado da valida??o de um header"""
    name: str
    status: HeaderStatus
    actual_value: str = ""
    expected: str = ""
    description: str = ""


@dataclass
class EndpointValidation:
    """Resultado da valida??o de um endpoint"""
    endpoint: str
    method: str
    status_code: int
    response_time_ms: float
    headers_valid: List[HeaderValidation]
    critical_failures: int = 0


class SecurityHeaderValidator:
    """Valida headers de seguran?a em endpoints"""
    
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.results: List[EndpointValidation] = []
        self.timing_results: Dict[str, List[float]] = {}
    
    def validate_endpoint(self, endpoint: str, method: str = "GET") -> EndpointValidation:
        """Valida um endpoint espec?fico"""
        url = f"{self.base_url}{endpoint}"
        
        try:
            # Fazer requisi??o
            start_time = time.time()
            
            if method == "GET":
                response = self.session.get(url, timeout=5)
            else:
                response = self.session.request(method, url, timeout=5)
            
            response_time_ms = (time.time() - start_time) * 1000
            
            # Validar headers
            headers_valid = self._validate_headers(response.headers)
            
            critical_failures = sum(
                1 for h in headers_valid
                if h.status == HeaderStatus.MISSING and REQUIRED_HEADERS[h.name]["critical"]
            )
            
            return EndpointValidation(
                endpoint=endpoint,
                method=method,
                status_code=response.status_code,
                response_time_ms=response_time_ms,
                headers_valid=headers_valid,
                critical_failures=critical_failures
            )
        except requests.exceptions.RequestException as e:
            print(f"? Error requesting {url}: {e}")
            return EndpointValidation(
                endpoint=endpoint,
                method=method,
                status_code=0,
                response_time_ms=0,
                headers_valid=[],
                critical_failures=len(REQUIRED_HEADERS)
            )
    
    def _validate_headers(self, response_headers: Dict) -> List[HeaderValidation]:
        """Valida headers na resposta"""
        validations = []
        
        for header_name, config in REQUIRED_HEADERS.items():
            validation = HeaderValidation(
                name=header_name,
                description=config["description"],
                status=HeaderStatus.MISSING,
                actual_value=""
            )
            
            if header_name in response_headers:
                actual_value = response_headers[header_name]
                validation.actual_value = actual_value
                
                if not actual_value.strip():
                    validation.status = HeaderStatus.EMPTY
                elif "expected_value" in config:
                    if config["expected_value"] in actual_value:
                        validation.status = HeaderStatus.PRESENT
                        validation.expected = config["expected_value"]
                    else:
                        validation.status = HeaderStatus.INVALID_VALUE
                        validation.expected = config["expected_value"]
                elif "expected_pattern" in config:
                    if config["expected_pattern"] in actual_value:
                        validation.status = HeaderStatus.PRESENT
                        validation.expected = f"contains '{config['expected_pattern']}'"
                    else:
                        validation.status = HeaderStatus.INVALID_VALUE
                        validation.expected = f"contains '{config['expected_pattern']}'"
            
            validations.append(validation)
        
        return validations
    
    def run_performance_test(self):
        """Testa performance sob m?ltiplas requisi??es"""
        print(f"\n??  TESTE DE PERFORMANCE")
        print(f"Realizando {NUM_REQUESTS_PER_ENDPOINT} requisi??es por endpoint...\n")
        
        for endpoint, method in ENDPOINTS_TO_TEST:
            times = []
            
            for i in range(NUM_REQUESTS_PER_ENDPOINT):
                result = self.validate_endpoint(endpoint, method)
                times.append(result.response_time_ms)
            
            self.timing_results[endpoint] = times
            
            avg_time = statistics.mean(times)
            median_time = statistics.median(times)
            max_time = max(times)
            min_time = min(times)
            
            print(f"? {method} {endpoint}")
            print(f"   M?dio:   {avg_time:.2f}ms")
            print(f"   Mediana: {median_time:.2f}ms")
            print(f"   Max:     {max_time:.2f}ms")
            print(f"   Min:     {min_time:.2f}ms\n")
    
    def run_full_test(self) -> bool:
        """Executa teste completo"""
        print(f"{'='*70}")
        print(f"? SECURITY HEADERS VALIDATION TEST")
        print(f"{'='*70}\n")
        
        all_passed = True
        
        # 1. Testar cada endpoint
        print(f"? VALIDANDO ENDPOINTS\n")
        
        for endpoint, method in ENDPOINTS_TO_TEST:
            print(f"? [{method}] {endpoint}")
            
            result = self.validate_endpoint(endpoint, method)
            self.results.append(result)
            
            if result.status_code == 0:
                print(f"   ? Falha ao conectar\n")
                all_passed = False
                continue
            
            print(f"   Status: {result.status_code}")
            print(f"   Tempo: {result.response_time_ms:.2f}ms")
            print(f"   Headers:")
            
            for validation in result.headers_valid:
                status_emoji = validation.status.value.split()[0]
                print(f"     {status_emoji} {validation.name}: {validation.description}")
                
                if validation.actual_value:
                    value_preview = validation.actual_value[:50]
                    if len(validation.actual_value) > 50:
                        value_preview += "..."
                    print(f"        Value: {value_preview}")
                
                if validation.status == HeaderStatus.INVALID_VALUE:
                    print(f"        Expected: {validation.expected}")
                    print(f"        Got: {validation.actual_value}")
                    all_passed = False
                
                if validation.status == HeaderStatus.MISSING and REQUIRED_HEADERS[validation.name]["critical"]:
                    all_passed = False
            
            if result.critical_failures > 0:
                all_passed = False
            
            print()
        
        # 2. Testar performance
        self.run_performance_test()
        
        # 3. Gerar relat?rio
        self._print_report()
        
        return all_passed
    
    def _print_report(self):
        """Imprime relat?rio final"""
        print(f"\n{'='*70}")
        print(f"? RELAT?RIO FINAL")
        print(f"{'='*70}\n")
        
        # Contar status
        total_headers = len(self.results) * len(REQUIRED_HEADERS)
        present_count = 0
        missing_count = 0
        invalid_count = 0
        
        for result in self.results:
            for validation in result.headers_valid:
                if validation.status == HeaderStatus.PRESENT:
                    present_count += 1
                elif validation.status == HeaderStatus.MISSING:
                    missing_count += 1
                else:
                    invalid_count += 1
        
        print(f"? Headers Presentes: {present_count}/{total_headers}")
        print(f"? Headers Faltando: {missing_count}/{total_headers}")
        print(f"??  Headers Inv?lidos: {invalid_count}/{total_headers}")
        
        # Performance
        if self.timing_results:
            print(f"\n??  PERFORMANCE")
            for endpoint, times in self.timing_results.items():
                avg = statistics.mean(times)
                max_time = max(times)
                
                # Verificar se h? overhead significativo
                status = "?" if max_time < 100 else "??" if max_time < 500 else "?"
                print(f"   {status} {endpoint}: {avg:.1f}ms avg, {max_time:.1f}ms max")
        
        # Valida??o cr?tica
        print(f"\n? VALIDA??O CR?TICA")
        critical_failures = sum(r.critical_failures for r in self.results)
        if critical_failures == 0:
            print(f"   ? Nenhuma falha cr?tica")
        else:
            print(f"   ? {critical_failures} falhas cr?ticas encontradas")
        
        print(f"\n{'='*70}\n")


async def main():
    """Entry point"""
    validator = SecurityHeaderValidator(BASE_URL)
    
    try:
        result = validator.run_full_test()
        return 0 if result else 1
    except KeyboardInterrupt:
        print("\n??  Teste interrompido")
        return 2
    except Exception as e:
        print(f"? Erro: {e}")
        return 3


if __name__ == "__main__":
    import asyncio
    exit_code = asyncio.run(main())
    exit(exit_code)
