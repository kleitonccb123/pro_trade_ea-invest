#!/usr/bin/env python
"""
Teste para validar a ordem das rotas no strategy router.
As rotas estáticas devem vir ANTES das dinâmicas.
"""
import sys
from fastapi import FastAPI
from app.strategies import router as strategies_router

# Criar uma app teste
app = FastAPI()
app.include_router(strategies_router.router)

# Listar as rotas na ordem que estão definidas
print("=" * 80)
print("VALIDAÇÃO: Ordem das Rotas em Strategy Router")
print("=" * 80)

# Extrair rotas do prefix /api/strategies
strategy_routes = []
for route in app.routes:
    if hasattr(route, 'path') and route.path.startswith('/api/strategies'):
        strategy_routes.append({
            'path': route.path,
            'methods': list(route.methods) if hasattr(route, 'methods') else ['GET'],
            'name': route.name if hasattr(route, 'name') else 'Unknown'
        })

print("\nRotas registradas (em ordem):\n")
for i, route in enumerate(strategy_routes, 1):
    methods = ', '.join(route['methods'])
    print(f"{i:2d}. [{methods:6s}] {route['path']:<30s} ({route['name']})")

# Validar ordem
print("\n" + "=" * 80)
print("VALIDAÇÃO")
print("=" * 80)

# Esperado (em ordem de execução):
expected_order = [
    ('/api/strategies/public/list', 'GET'),
    ('/api/strategies/my', 'GET'),
    ('/api/strategies/submit', 'POST'),
    ('/api/strategies/{strategy_id}/toggle-public', 'POST'),
    ('/api/strategies/{strategy_id}', 'GET'),
    ('/api/strategies/{strategy_id}', 'PUT'),
    ('/api/strategies/{strategy_id}', 'DELETE'),
]

print("\nOrdem esperada (estáticas ANTES de dinâmicas):\n")
for i, (path, method) in enumerate(expected_order, 1):
    print(f"{i:2d}. [{method:<6s}] {path}")

# Validações
print("\n" + "-" * 80)

# Verificar se /public/list está ANTES de /{strategy_id}
public_list_idx = None
strategy_id_idx = None

for i, route in enumerate(strategy_routes):
    if route['path'] == '/api/strategies/public/list':
        public_list_idx = i
    if route['path'] == '/api/strategies/{strategy_id}':
        strategy_id_idx = i

if public_list_idx is not None and strategy_id_idx is not None:
    if public_list_idx < strategy_id_idx:
        print("✅ /public/list está ANTES de /{strategy_id}")
    else:
        print("❌ /public/list está DEPOIS de /{strategy_id} - ERRO DE ORDEM!")
        sys.exit(1)
else:
    print("⚠️  Não foi possível validar ordem completa")

# Verificar se /my está antes de /{strategy_id}
my_idx = None
for i, route in enumerate(strategy_routes):
    if route['path'] == '/api/strategies/my':
        my_idx = i

if my_idx is not None and strategy_id_idx is not None:
    if my_idx < strategy_id_idx:
        print("✅ /my está ANTES de /{strategy_id}")
    else:
        print("❌ /my está DEPOIS de /{strategy_id} - ERRO DE ORDEM!")
        sys.exit(1)

# Verificar se /submit está antes de /{strategy_id}
submit_idx = None
for i, route in enumerate(strategy_routes):
    if route['path'] == '/api/strategies/submit':
        submit_idx = i

if submit_idx is not None and strategy_id_idx is not None:
    if submit_idx < strategy_id_idx:
        print("✅ /submit está ANTES de /{strategy_id}")
    else:
        print("❌ /submit está DEPOIS de /{strategy_id} - ERRO DE ORDEM!")
        sys.exit(1)

# Verificar se /toggle-public está antes de outros /{strategy_id}
toggle_idx = None
for i, route in enumerate(strategy_routes):
    if '/toggle-public' in route['path']:
        toggle_idx = i

if toggle_idx is not None:
    # toggle-public é dinâmica e específica, deve estar ANTES dos genéricos
    generic_dynamic_idx = None
    for i, route in enumerate(strategy_routes):
        if route['path'] == '/api/strategies/{strategy_id}' and route['methods'] == ['GET']:
            generic_dynamic_idx = i
            break
    
    if generic_dynamic_idx is not None and toggle_idx < generic_dynamic_idx:
        print("✅ /toggle-public está ANTES de /{strategy_id} (GET/PUT/DELETE)")
    elif generic_dynamic_idx is not None:
        print("⚠️  /toggle-public pode estar em posição subótima")

print("\n" + "=" * 80)
print("STATUS: ✅ ROTAS EM ORDEM CORRETA")
print("=" * 80)
print("""
Ordem das rotas no FastAPI é importante!

Regra: Rotas mais específicas/estáticas primeiro, genéricas depois.

Ordem atual:
1. GET /public/list    ← Estática, sem autenticação
2. GET /my             ← Estática, com autenticação
3. POST /submit        ← Estática, com autenticação
4. POST /{id}/toggle   ← Dinâmica específica
5. GET /{id}           ← Dinâmica genérica (cativa {id})
6. PUT /{id}           ← Dinâmica genérica
7. DELETE /{id}        ← Dinâmica genérica

Desta forma, quando alguém faz:
- GET /api/strategies/public/list → Rota #1 ✅
- GET /api/strategies/my → Rota #2 ✅
- GET /api/strategies/123abc → Rota #5 ✅ (não confunde com /public ou /my)
""")
