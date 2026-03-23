#!/usr/bin/env python3
"""
🚀 Robot Data Updater Launcher
Inicializa o robô que atualiza os dados do sistema
"""

import sys
import os
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent / 'backend'
sys.path.insert(0, str(backend_path))
sys.path.insert(0, str(backend_path.parent))

# Set environment
os.chdir(backend_path)

# Import and run
from robot_data_updater import main
import asyncio

if __name__ == '__main__':
    print("""
    ╔════════════════════════════════════════════════════════════╗
    ║        🤖 Robot Data Updater - Sistema de Atualização      ║
    ║                                                            ║
    ║  • Atualiza dados dos robôs em tempo real                 ║
    ║  • Gera trades simulados com histórico realista           ║
    ║  • Atualiza taxa de acerto e rentabilidade                ║
    ║  • Muda ordem do ranking a cada atualização              ║
    ║  • Simula crescimento de usuários                         ║
    ╚════════════════════════════════════════════════════════════╝
    """)
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n✋ Updater parado pelo usuário")
    except Exception as e:
        print(f"\n❌ Erro: {e}")
        sys.exit(1)
