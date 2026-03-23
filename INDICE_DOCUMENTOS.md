# 📚 ÍNDICE DE DOCUMENTOS - DEPLOYMENT GUIA

**Data:** Março 23, 2026  
**Objetivo:** Saber qual documento consultar em cada situação

---

## 🗺️ MAPA DE DOCUMENTOS

```
Documentos criados:

📄 DEPLOYMENT_GUIA_COMPLETO.md          ← Referência completa
📄 DEPLOYMENT_CHECKLIST_RAPIDO.md        ← Modelo executivo  
🔧 deploy_vps.sh                         ← Script automatizado
📄 SCRIPTS_PRODUCAO.md                   ← Scripts prontos
📄 INDICE_DOCUMENTOS.md                  ← Este arquivo
```

---

## 🎯 QUAL DOCUMENTO USAR EM CADA SITUAÇÃO?

### Situação 1️⃣: É PRIMEIRA VEZ, QUERO FAZER DEPLOY INICIAL

**Use nesta ordem:**

1. **DEPLOYMENT_CHECKLIST_RAPIDO.md** (5 min de leitura)
   - Visão geral rápida
   - Fase por fase
   - O que é esperado

2. **deploy_vps.sh** (automatizado - 4-6 horas)
   - Rodar: `bash deploy_vps.sh seu-dominio.com seu_email@dominio.com`
   - Faz 80% do trabalho automaticamente

3. **DEPLOYMENT_GUIA_COMPLETO.md** (referência detalhada)
   - Se algo der errado
   - Para entender o que foi feito
   - Troubleshooting

---

### Situação 2️⃣: JÁ TENHO DEPLOYMENT MAS PRECISO ATUALIZAR

**Use:**

- **DEPLOYMENT_GUIA_COMPLETO.md** → Seção "PARTE 10: PROCEDIMENTO PARA ATUALIZAÇÕES"
  - Modificação Frontend
  - Modificação Backend
  - Modificação Banco de Dados
  - Modificação em Ambos

**Exemplo:**
```bash
# Só frontend mudou?
git pull
npm run build
docker-compose -f docker-compose.prod.yml exec nginx nginx -s reload
# ✅ Pronto em 2-5 min
```

---

### Situação 3️⃣: APLICAÇÃO QUEBROU, PRECISO ARRUMAR RÁPIDO

**Use nesta ordem:**

1. **SCRIPTS_PRODUCAO.md** → Seção "6️⃣ SCRIPT: troubleshoot.sh"
   ```bash
   ./troubleshoot.sh
   ```
   - Mostra exatamente o que tá ruim

2. **DEPLOYMENT_GUIA_COMPLETO.md** → Seção "⚠️ PROCEDIMENTOS DE EMERGÊNCIA"
   - Rollback
   - Quick Fixes

3. **Comando rápido de rollback:**
   ```bash
   cd /home/appuser/crypto-trade-hub
   git reset --hard HEAD~1
   docker-compose -f docker-compose.prod.yml build
   docker-compose -f docker-compose.prod.yml restart
   ```

---

### Situação 4️⃣: QUERO ENTENDER COMO TUDO FUNCIONA

**Use:**

**DEPLOYMENT_GUIA_COMPLETO.md** (leitura sequencial)
- Parte 1-7: Setup inicial
- Parte 8-9: Backups e monitoramento
- Parte 10: Atualizações
- Seções finais: Troubleshooting + Referência

---

### Situação 5️⃣: PRECISO AUTOMATIZAR ALGO (Backups, Alertas, Health Checks)

**Use:**

**SCRIPTS_PRODUCAO.md**
- Health Check automático
- Backups automáticos
- Auto-restart
- Alertas por email
- Todos os scripts prontos para copiar/colar

---

### Situação 6️⃣: TENHO PROBLEMA ESPECÍFICO

| Problema | Use |
|----------|-----|
| 502 Bad Gateway | SCRIPTS_PRODUCAO.md → Quick Fixes |
| Certificado SSL expirou | DEPLOYMENT_GUIA_COMPLETO.md → Parte 4 OU SCRIPTS_PRODUCAO.md → Quick Fixes |
| Disco cheio | DEPLOYMENT_GUIA_COMPLETO.md → Procedimentos de Emergência |
| Memória alta | DEPLOYMENT_GUIA_COMPLETO.md → Procedimentos de Emergência |
| Conexão recusada | DEPLOYMENT_GUIA_COMPLETO.md → Troubleshooting |
| Aplicação lenta | SCRIPTS_PRODUCAO.md → 6️⃣ troubleshoot.sh |

---

## 📋 CHECKLIST ANTES DE COMEÇAR

**Você tem tudo isto pronto?**

```
☐ VPS Hostinger contratada (4GB RAM, 2vCPU, Ubuntu 22.04)
☐ Acesso SSH root à VPS
☐ Domínio registrado + DNS preparado
☐ Código git atualizado no seu PC
☐ Arquivo .env.production preparado localmente
☐ Backup local feito (se tinha dados anteriores)
☐ Email de contato pronto (para certificado SSL)
```

---

## 🚀 FLUXO RÁPIDO - DEPLOYMENT PELA PRIMEIRA VEZ

```
Passo 1: Contratar VPS Hostinger com Ubuntu 22.04 LTS
         ↓
Passo 2: Apontar Domínio para IP da VPS (5-15 min propagação)
         ↓
Passo 3: Conectar SSH na VPS como root
         ↓
Passo 4: Copiar deploy_vps.sh para VPS
         ↓
Passo 5: Rodar: bash deploy_vps.sh seu-dominio.com seu_email@dominio.com
         ↓
Passo 6: Aguardar 4-6 horas (automatizado)
         ↓
Passo 7: Testar: https://seu-dominio.com
         ↓
Passo 8: ✅ ONLINE!
```

---

## 🔄 FLUXO RÁPIDO - ATUALIZAÇÕES FUTURAS

```
Mudança no código → git push

Se mudou só FRONTEND:
  git pull
  npm run build
  nginx reload
  ✅ 2-5 min, zero downtime

Se mudou só BACKEND:
  git pull
  docker build
  docker restart backend
  ✅ 1-3 min, ~30 seg downtime

Se mudou FRONT + BACK:
  git pull
  npm build + docker build
  restart backend + nginx reload
  ✅ 3-5 min
```

---

## 📞 PERGUNTAS FREQUENTES

**P: Qual documento começo a ler?**  
**R:** DEPLOYMENT_CHECKLIST_RAPIDO.md (5 min) → deploy_vps.sh (rodar)

**P: Quanto tempo leva na primeira vez?**  
**R:** 4-6 horas (com script automatizado: 80% fica automático)

**P: E depois, quanto tempo para atualizar?**  
**R:** 2-5 minutos (só frontend) até 3-5 minutos (front + back)

**P: Preciso ler TUDO?**  
**R:** Não! Só o CHECKLIST_RAPIDO.md na primeira vez. Os outros são referência.

**P: Onde guardo as senhas?**  
**R:** O script salva tudo em `/root/deployment_*.log`. Guardar em lugar seguro!

**P: Posso automatizar backups?**  
**R:** Sim! Ver SCRIPTS_PRODUCAO.md → seção "backup.sh"

**P: Como testar antes de fazer deploy real?**  
**R:** Setup staging em outro subdomain ou environment variável diferente

---

## 📊 CRONOGRAMA RECOMENDADO

### Dia 1 (2-3 horas)
```
☐ Ler DEPLOYMENT_CHECKLIST_RAPIDO.md
☐ Contratar VPS Hostinger
☐ Apontar domínio
☐ Conectar SSH
☐ Rodar deploy_vps.sh
```

### Dia 2 (1 hora)
```
☐ Testar acesso
☐ Configurar backups
☐ Configurar health checks
☐ Documentar senhas
```

### Dia 3+ (contínuo)
```
☐ Fazer atualizações usando DEPLOYMENT_GUIA_COMPLETO.md
☐ Monitorar logs via health_check.sh
☐ Manutenção rotineira
```

---

## 🎓 ESTRUTURA DOS DOCUMENTOS

### DEPLOYMENT_GUIA_COMPLETO.md
```
└── 10 Partes principais
    ├── Parte 1: Preparar VPS
    ├── Parte 2: Configurar Domínio
    ├── Parte 3: Clonar Projeto
    ├── Parte 4: Certificado SSL
    ├── Parte 5: Docker Compose
    ├── Parte 6: Nginx com SSL
    ├── Parte 7: Validação
    ├── Parte 8: Backups
    ├── Parte 9: Monitoramento
    ├── Parte 10: Atualizações Futuras
    ├── Procedimentos de Emergência
    ├── Troubleshooting
    └── Referência Rápida
```

### DEPLOYMENT_CHECKLIST_RAPIDO.md
```
└── 8 Fases rápidas
    ├── Fase 1: Preparar VPS (30-45 min)
    ├── Fase 2: Configurar Domínio (5-15 min)
    ├── Fase 3: Clonar Projeto (10-20 min)
    ├── Fase 4: Certificado SSL (10-15 min)
    ├── Fase 5: Docker (5 min)
    ├── Fase 6: Subir Docker (5-10 min)
    ├── Fase 7: Validar Acesso (5-10 min)
    └── Fase 8: Backups (5 min)
```

### SCRIPTS_PRODUCAO.md
```
└── 8 Scripts prontos
    ├── 1: health_check.sh
    ├── 2: update_frontend.sh
    ├── 3: update_backend.sh
    ├── 4: update_all.sh
    ├── 5: rollback.sh
    ├── 6: troubleshoot.sh
    ├── 7: auto_restart.sh
    └── 8: Crontab jobs
```

---

## 🎬 PASSO A PASSO ULTRA-RÁPIDO

**Você tem 30 minutos disponível?**

```bash
# 1. Conectar SSH
ssh root@seu_ip_vps

# 2. Clonar este repo
git clone https://seu-github.com/crypto-trade-hub.git /tmp/deploy
cd /tmp/deploy

# 3. Rodar script
bash deploy_vps.sh seu-dominio.com seu_email@dominio.com

# 4. Aguardar ~4 horas (pode fechar e voltar depois)

# 5. Verificar
curl https://seu-dominio.com

# ✅ PRONTO
```

---

## ⚠️ CUIDADOS IMPORTANTES

1. **Nunca commitar .env com dados reais**  
   - Usar `.env.example` no git
   - `.env.production` fica localmente na VPS

2. **Fazer backup antes de qualquer mudança**  
   ```bash
   /home/appuser/backup.sh
   ```

3. **Sempre testar rollback em staging primeiro**  
   - Depois aplicar em produção

4. **SSL é obrigatório em produção**  
   - Let's Encrypt gratuito + auto-renovação

5. **Manter logs atualizados**  
   - Health checks a cada 5 min
   - Backups diários

---

## 📞 SUPORTE

### Se tiver dúvidas:
1. Procurar no DEPLOYMENT_GUIA_COMPLETO.md
2. Procurar no SCRIPTS_PRODUCAO.md
3. Executar `troubleshoot.sh`
4. Revisar logs: `docker-compose logs -f backend`

### Se quebrar:
1. Executar `./troubleshoot.sh` para diagnosticar
2. Se não descobrir, fazer `./rollback.sh`
3. Depois investigar os logs com calma

---

**Data de Criação:** Março 23, 2026  
**Versão:** 1.0  
**Status:** ✅ Pronto para Produção  

---

Quer começar? ➡️ Leia [DEPLOYMENT_CHECKLIST_RAPIDO.md](DEPLOYMENT_CHECKLIST_RAPIDO.md) agora!
