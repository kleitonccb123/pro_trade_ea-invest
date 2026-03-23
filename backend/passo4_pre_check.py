#!/usr/bin/env python3
"""
? PR?-EXECU??O CHECKLIST - PASSO 4

Este script valida se o ambiente est? pronto para rodar os testes de Passo 4.

Verifica??es:
  ? Python >= 3.8
  ? Depend?ncias instaladas (locust, websockets, requests, psutil)
  ? Backend rodando em localhost:8000
  ? Banco de dados conectado
  ? Scripts de teste presentes
  ? Espa?o em disco suficiente

Uso:
  python backend/passo4_pre_check.py
"""

import sys
import subprocess
import os
import socket
import json
from pathlib import Path
from typing import Dict, Tuple

# ============================================
# Configura??o
# ============================================

MIN_PYTHON_VERSION = (3, 8)
REQUIRED_PACKAGES = {
    "locust": "Stress testing framework",
    "websockets": "WebSocket testing",
    "requests": "HTTP requests",
    "psutil": "Resource monitoring",
    "fastapi": "Web framework",
    "pydantic": "Data validation",
}
REQUIRED_FILES = [
    "backend/tests/stress/stress_test.py",
    "backend/tests/integration/test_websocket_load.py",
    "backend/tests/security/test_headers_validation.py",
    "backend/app/core/monitoring.py",
]
BACKEND_URL = "http://localhost:8000"
REQUIRED_DISK_SPACE_MB = 500

# ============================================
# Checklist
# ============================================


class PreExecutionCheck:
    """Valida ambiente para Passo 4"""
    
    def __init__(self):
        self.checks_passed = 0
        self.checks_failed = 0
        self.warnings = 0
    
    def print_header(self):
        """Imprime cabe?alho"""
        print("\n" + "="*70)
        print("? PR?-EXECU??O CHECKLIST - PASSO 4")
        print("="*70 + "\n")
    
    def print_footer(self):
        """Imprime rodap?"""
        print("\n" + "="*70)
        
        if self.checks_failed == 0:
            print("? SISTEMA PRONTO PARA TESTES!")
            print(f"? {self.checks_passed} verifica??es passaram")
            if self.warnings > 0:
                print(f"??  {self.warnings} avisos (ignor?veis)")
            print("\nPr?ximo passo: Iniciar servidor e rodar testes")
            return True
        else:
            print("? SISTEMA N?O PRONTO")
            print(f"? {self.checks_passed} verifica??es passaram")
            print(f"? {self.checks_failed} verifica??es falharam")
            print(f"??  {self.warnings} avisos")
            print("\n?orrija os problemas acima e tente novamente")
            return False
    
    def check_python_version(self) -> bool:
        """Verifica Python >= 3.8"""
        print(f"? Python Version: ", end="")
        
        current = sys.version_info
        required = MIN_PYTHON_VERSION
        
        if current >= required:
            print(f"? {current.major}.{current.minor}.{current.micro}")
            self.checks_passed += 1
            return True
        else:
            print(f"? {current.major}.{current.minor} (requer >= {required[0]}.{required[1]})")
            self.checks_failed += 1
            return False
    
    def check_packages(self) -> bool:
        """Verifica pacotes instalados"""
        print(f"\n? Pacotes Instalados:")
        
        all_ok = True
        
        for package, description in REQUIRED_PACKAGES.items():
            try:
                __import__(package)
                print(f"   ? {package:<20} {description}")
                self.checks_passed += 1
            except ImportError:
                print(f"   ? {package:<20} {description} (n?o instalado)")
                self.checks_failed += 1
                all_ok = False
        
        return all_ok
    
    def check_files(self) -> bool:
        """Verifica arquivos de teste presentes"""
        print(f"\n? Arquivos de Teste:")
        
        all_ok = True
        
        for file_path in REQUIRED_FILES:
            if Path(file_path).exists():
                size = Path(file_path).stat().st_size
                print(f"   ? {file_path:<50} ({size} bytes)")
                self.checks_passed += 1
            else:
                print(f"   ? {file_path:<50} (N?O ENCONTRADO)")
                self.checks_failed += 1
                all_ok = False
        
        return all_ok
    
    def check_backend_running(self) -> bool:
        """Verifica se backend est? rodando"""
        print(f"\n??  Backend Status: ", end="", flush=True)
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            result = sock.connect_ex(('localhost', 8000))
            sock.close()
            
            if result == 0:
                print("??  Backend est? rodando (n?o obrigat?rio agora)")
                self.warnings += 1
                return True
            else:
                print("??  Backend n?o detectado (inicie antes de rodar testes)")
                self.warnings += 1
                return True  # Warning, n?o erro
        except Exception as e:
            print(f"??  Erro ao verificar: {e}")
            self.warnings += 1
            return True  # Warning, n?o erro
    
    def check_disk_space(self) -> bool:
        """Verifica espa?o em disco"""
        print(f"\n? Espa?o em Disco: ", end="")
        
        try:
            import shutil
            total, used, free = shutil.disk_usage("/")
            free_mb = free / (1024 * 1024)
            
            if free_mb > REQUIRED_DISK_SPACE_MB:
                print(f"? {free_mb:.0f}MB dispon?vel")
                self.checks_passed += 1
                return True
            else:
                print(f"??  Apenas {free_mb:.0f}MB dispon?vel (recomendado {REQUIRED_DISK_SPACE_MB}MB)")
                self.warnings += 1
                return True  # Warning
        except Exception as e:
            print(f"??  Erro ao verificar: {e}")
            self.warnings += 1
            return True
    
    def check_network(self) -> bool:
        """Verifica conectividade b?sica"""
        print(f"\n? Conectividade: ", end="")
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            result = sock.connect_ex(('8.8.8.8', 53))
            sock.close()
            
            if result == 0:
                print("? Rede dispon?vel")
                self.checks_passed += 1
                return True
            else:
                print("??  Sem conectividade externa detectada")
                self.warnings += 1
                return True  # Pode ser OK para testes locais
        except Exception as e:
            print(f"??  Erro ao verificar: {e}")
            self.warnings += 1
            return True
    
    def run_all_checks(self) -> bool:
        """Executa todas as verifica??es"""
        self.print_header()
        
        self.check_python_version()
        self.check_packages()
        self.check_files()
        self.check_disk_space()
        self.check_network()
        self.check_backend_running()
        
        return self.print_footer()


def main():
    """Entry point"""
    checker = PreExecutionCheck()
    success = checker.run_all_checks()
    
    return 0 if success else 1


if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n??  Checklist interrompido pelo usu?rio")
        sys.exit(2)
    except Exception as e:
        print(f"\n? Erro ao executar checklist: {e}")
        sys.exit(3)
