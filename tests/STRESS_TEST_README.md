# 🔥 Stress Test Suite - Crypto Trade Hub

Suite completa de testes de stress para validar a escalabilidade do sistema antes de ir para produção.

## 📋 O que está incluído

| Arquivo | Descrição |
|---------|-----------|
| `stress_test.py` | Script asyncio/httpx para testes rápidos |
| `locustfile.py` | Testes profissionais com dashboard web |
| `mongo_monitor.py` | Monitor de performance do MongoDB |
| `Dockerfile.stress` | Container para testes em produção |
| `docker-compose.stress.yml` | Orquestração de testes |
| `locust.conf` | Configuração do Locust |

## 🚀 Quick Start

### 1. Instalar dependências

```bash
cd tests
pip install -r requirements-stress.txt
```

### 2. Teste Rápido (30 segundos)

```bash
# Certifique-se que o backend está rodando na porta 8000
python stress_test.py --quick
```

### 3. Teste Completo (60 segundos)

```bash
python stress_test.py --users 50 --bots 100 --duration 60
```

## 🦗 Usando Locust (Recomendado)

Locust oferece um dashboard web em tempo real e relatórios detalhados.

### Iniciar com Dashboard Web

```bash
cd tests
locust -f locustfile.py --host http://localhost:8000
```

Depois acesse: **http://localhost:8089**

### Modo Headless (para CI/CD)

```bash
locust -f locustfile.py \
  --host http://localhost:8000 \
  --headless \
  --users 50 \
  --spawn-rate 5 \
  --run-time 60s \
  --html report.html
```

## 🐳 Usando Docker

### Build da imagem

```bash
docker build -f Dockerfile.stress -t crypto-stress-test .
```

### Teste contra ambiente local

```bash
docker run --rm --network host crypto-stress-test \
  --url http://localhost:8000 \
  --users 50 \
  --bots 100
```

### Locust com Dashboard (Docker)

```bash
docker run --rm -p 8089:8089 crypto-stress-test \
  --locust \
  --host http://host.docker.internal:8000
```

### Usando Docker Compose

```bash
# Teste rápido
docker-compose -f docker-compose.stress.yml up stress-quick

# Teste completo local
docker-compose -f docker-compose.stress.yml up stress-local

# Locust com dashboard
docker-compose -f docker-compose.stress.yml up locust
```

## 📊 Monitorando o MongoDB

Execute junto com o stress test para identificar gargalos:

```bash
# Em um terminal separado
python mongo_monitor.py --uri mongodb://localhost:27017 --db crypto_trade_hub
```

## 📈 Interpretando Resultados

### Métricas Principais

| Métrica | Bom | Médio | Crítico |
|---------|-----|-------|---------|
| **RPS** (Requests/sec) | > 50 | 20-50 | < 20 |
| **Latência Média** | < 200ms | 200-500ms | > 500ms |
| **Taxa de Erro** | < 1% | 1-5% | > 5% |
| **P95 Latency** | < 500ms | 500ms-1s | > 1s |

### Avaliação Final

- 🏆 **EXCELENTE**: Todos os indicadores no verde → Pronto para produção
- ✅ **BOM**: Maioria no verde → Pode ir para produção com monitoramento
- ⚠️ **MÉDIO**: Mix de amarelo/verde → Considere otimizações
- ❌ **CRÍTICO**: Indicadores no vermelho → Não vá para produção!

## 🔧 Otimizações Comuns

Se o teste mostrar problemas:

### Alta Latência
- Verificar índices no MongoDB
- Habilitar cache para consultas frequentes
- Usar connection pooling

### Alta Taxa de Erro
- Verificar logs do backend
- Aumentar timeouts
- Verificar rate limiting

### Baixo RPS
- Aumentar workers do uvicorn
- Usar gunicorn com workers
- Considerar load balancer

### Gargalo no MongoDB
- Aumentar `maxPoolSize`
- Adicionar índices
- Considerar sharding para alta escala

## 🔐 Testando em Produção

⚠️ **CUIDADO**: Testes em produção podem afetar usuários reais!

```bash
# Use credenciais de teste separadas
docker run --rm crypto-stress-test \
  --url https://api.seudominio.com \
  --users 20 \
  --bots 50 \
  --duration 30
```

Recomendações:
1. Faça durante horário de baixo tráfego
2. Use usuários de teste isolados
3. Monitore dashboards em tempo real
4. Tenha rollback pronto

## 📝 Exemplo de Relatório

```
╔══════════════════════════════════════════════════════════════╗
║                    📊 RELATÓRIO FINAL                        ║
╚══════════════════════════════════════════════════════════════╝

┌─────────────────────────────────────────────────┐
│ MÉTRICAS DE PERFORMANCE                         │
├─────────────────────────────────────────────────┤
│ Requests/Segundo (RPS):                   67.32 │
│ Latência Média:                         142.5ms │
│ Latência P50:                           98.2ms  │
│ Latência P95:                          287.4ms  │
│ Latência P99:                          456.1ms  │
│ Taxa de Sucesso:                         99.2%  │
│ Taxa de Erro:                             0.8%  │
├─────────────────────────────────────────────────┤
│ Total Requests:                           4039  │
│ Requests OK:                              4006  │
│ Requests Falhos:                            33  │
│ Tempo Total:                             60.0s  │
└─────────────────────────────────────────────────┘

============================================================
🏆 RESULTADO: EXCELENTE - Sistema pronto para produção!
============================================================
```

## 🤝 Contribuindo

Para adicionar novos cenários de teste, edite `locustfile.py` e adicione novas `@task` methods.

```python
@task(5)  # Peso 5 = 5x mais frequente que peso 1
def my_new_test(self):
    """Meu novo teste."""
    self.client.get("/api/my-endpoint")
```
