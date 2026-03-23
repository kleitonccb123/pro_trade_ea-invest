#!/bin/bash
# ===============================================
# Docker Entrypoint para Stress Test
# ===============================================

set -e

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}"
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  🔥 CRYPTO TRADE HUB - STRESS TEST SUITE                     ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Verificar modo de execução
case "$1" in
    --locust|locust)
        # Modo Locust com dashboard web
        shift
        echo -e "${GREEN}🦗 Iniciando Locust...${NC}"
        echo -e "${YELLOW}   Dashboard disponível em: http://localhost:8089${NC}"
        
        # Se não especificou host, usar padrão
        if [[ ! "$*" =~ "--host" ]]; then
            exec locust -f locustfile.py --host=http://host.docker.internal:8000 "$@"
        else
            exec locust -f locustfile.py "$@"
        fi
        ;;
        
    --locust-headless|locust-headless)
        # Modo Locust sem interface (CI/CD)
        shift
        echo -e "${GREEN}🦗 Iniciando Locust em modo headless...${NC}"
        
        USERS="${USERS:-50}"
        SPAWN_RATE="${SPAWN_RATE:-5}"
        RUN_TIME="${RUN_TIME:-60s}"
        HOST="${HOST:-http://host.docker.internal:8000}"
        
        exec locust -f locustfile.py \
            --host="$HOST" \
            --headless \
            --users "$USERS" \
            --spawn-rate "$SPAWN_RATE" \
            --run-time "$RUN_TIME" \
            --html=/app/report.html \
            "$@"
        ;;
        
    --asyncio|asyncio|--url|-u)
        # Modo asyncio/httpx (script personalizado)
        echo -e "${GREEN}⚡ Iniciando teste asyncio...${NC}"
        exec python stress_test.py "$@"
        ;;
        
    --quick|-q)
        # Teste rápido
        echo -e "${GREEN}🏃 Iniciando teste rápido...${NC}"
        exec python stress_test.py --quick
        ;;
        
    --help|-h|"")
        # Mostrar ajuda
        echo -e "${YELLOW}Uso:${NC}"
        echo ""
        echo "  ${GREEN}Modo Asyncio (script personalizado):${NC}"
        echo "    docker run --rm --network host crypto-stress-test --url http://localhost:8000 --users 50 --bots 100"
        echo "    docker run --rm --network host crypto-stress-test --quick"
        echo ""
        echo "  ${GREEN}Modo Locust (com dashboard):${NC}"
        echo "    docker run --rm -p 8089:8089 crypto-stress-test --locust --host http://host.docker.internal:8000"
        echo "    Depois acesse: http://localhost:8089"
        echo ""
        echo "  ${GREEN}Modo Locust Headless (para CI/CD):${NC}"
        echo "    docker run --rm -e USERS=100 -e RUN_TIME=120s crypto-stress-test --locust-headless"
        echo ""
        echo "  ${GREEN}Opções do script asyncio:${NC}"
        echo "    --url, -u       URL base do backend (default: http://localhost:8000)"
        echo "    --users, -n     Número de usuários simultâneos (default: 50)"
        echo "    --bots, -b      Número de robôs a criar (default: 100)"
        echo "    --duration, -d  Duração do teste em segundos (default: 60)"
        echo "    --quick, -q     Teste rápido (10 users, 20 bots, 30s)"
        echo ""
        echo "  ${GREEN}Variáveis de ambiente (para Locust headless):${NC}"
        echo "    USERS        Número de usuários (default: 50)"
        echo "    SPAWN_RATE   Taxa de spawn (default: 5)"
        echo "    RUN_TIME     Tempo de execução (default: 60s)"
        echo "    HOST         URL do backend"
        echo ""
        exit 0
        ;;
        
    *)
        # Passar argumentos diretamente para o script
        exec python stress_test.py "$@"
        ;;
esac
