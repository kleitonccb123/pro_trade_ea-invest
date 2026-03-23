# ⚡ Diagnóstico Rápido - Erro 401: invalid_client (1 Minuto)

**Execute isto agora para diagnosticar EXATAMENTE qual é o problema**

---

## 🚀 Passo 1: Terminal - Verificar Backend

```bash
# Execute isto:
cd backend
python << 'EOF'
import os
from dotenv import load_dotenv
load_dotenv()

print("\n" + "="*60)
print("🔍 DIAGNÓSTICO BACKEND")
print("="*60)

client_id = os.getenv('GOOGLE_CLIENT_ID', 'NÃO ENCONTRADO')

print(f"\n1. GOOGLE_CLIENT_ID encontrado? {'✅ SIM' if client_id != 'NÃO ENCONTRADO' else '❌ NÃO'}")
print(f"   Valor: {client_id[:40]}..." if len(client_id) > 40 else f"   Valor: {client_id}")

# Validações
is_empty = not client_id or client_id == 'NÃO ENCONTRADO'
has_format = '.apps.googleusercontent.com' in client_id if not is_empty else False
has_dash = '-' in client_id if not is_empty else False

print(f"\n2. Tem formato correto? {'✅ SIM' if has_format else '❌ NÃO'}")
print(f"   (deve conter: .apps.googleusercontent.com)")

print(f"\n3. Tem o padrão correto? {'✅ SIM' if has_dash and has_format else '❌ NÃO'}")
print(f"   (deve ser: números-letras.apps.googleusercontent.com)")

# Resultado
if is_empty:
    print("\n" + "!"*60)
    print("🔴 PROBLEMA #1: Client ID está VAZIO ou FALTANDO")
    print("!"*60)
    print("\nSolução:")
    print("1. Abrir: https://console.cloud.google.com/")
    print("2. APIs & Services → Credentials")
    print("3. Copiar o Client ID")
    print("4. Adicionar em backend/.env:")
    print("   GOOGLE_CLIENT_ID=seu_client_id_aqui")
    print("5. Salvar e executar este script novamente")
elif not has_format:
    print("\n" + "!"*60)
    print("🔴 PROBLEMA #2: Client ID está com FORMATO ERRADO")
    print("!"*60)
    print(f"\nSeu valor: {client_id}")
    print("Formato esperado: 123456789-abc123.apps.googleusercontent.com")
    print("\nSolução:")
    print("1. Copiar EXATAMENTE do Google Cloud Console")
    print("2. Colar em backend/.env (sem espaços extras)")
    print("3. Salvar arquivo")
else:
    print("\n" + "="*60)
    print("✅ BACKEND OK - Client ID está correto!")
    print("="*60)

EOF
```

**Salve a saída deste comando!** (screenshot ou copie o resultado)

---

## 🎨 Passo 2: DevTools - Verificar Frontend

```javascript
// Abrir navegador: http://localhost:8081
// Pressionar F12
// Aba Console
// Copiar e colar isto:

console.clear();
console.log("="*60);
console.log("🔍 DIAGNÓSTICO FRONTEND");
console.log("="*60);

const CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID || "NÃO ENCONTRADO";
const IS_EMPTY = !CLIENT_ID || CLIENT_ID === "NÃO ENCONTRADO";
const HAS_FORMAT = CLIENT_ID.includes('.apps.googleusercontent.com');

console.log(`\n1. VITE_GOOGLE_CLIENT_ID encontrado? ${IS_EMPTY ? '❌ NÃO' : '✅ SIM'}`);
console.log(`   Valor: ${CLIENT_ID.substring(0, 40)}...`);

console.log(`\n2. Tem formato correto? ${HAS_FORMAT ? '✅ SIM' : '❌ NÃO'}`);
console.log(`   (deve conter: .apps.googleusercontent.com)`);

if (IS_EMPTY) {
    console.error("\n🔴 PROBLEMA #3: Frontend .env está VAZIO ou NÃO CARREGADO");
    console.log("\nSolução:");
    console.log("1. Criar/editar arquivo .env (na raiz do projeto)");
    console.log("2. Adicionar: VITE_GOOGLE_CLIENT_ID=seu_client_id");
    console.log("3. Salvar arquivo");
    console.log("4. Restart Vite: npm run dev");
    console.log("5. F5 no navegador");
} else if (!HAS_FORMAT) {
    console.error("\n🔴 PROBLEMA #4: Frontend .env com FORMATO ERRADO");
    console.log(`\nSeu valor: ${CLIENT_ID}`);
    console.log("Esperado: 123456789-abc123.apps.googleusercontent.com");
} else {
    console.log("\n✅ FRONTEND OK - Client ID está correto!");
}

// Verificação adicional
if (window.google) {
    console.log("\n✅ Google API library carregada");
} else {
    console.warn("\n⚠️ Google API library NÃO carregada - verificar index.html");
}
```

**Execute isto no DevTools e salve o resultado!**

---

## ✅ Interpretando os Resultados

### Cenário 1: Backend ❌, Frontend ❌

```
🔴 PROBLEMA: Ambos não têm Client ID

AÇÃO IMEDIATA:
1. Abrir Google Cloud Console: https://console.cloud.google.com/
2. Copiar seu Client ID
3. Adicionar em AMBOS os arquivos:
   - backend/.env: GOOGLE_CLIENT_ID=seu_id
   - .env (raiz): VITE_GOOGLE_CLIENT_ID=seu_id
4. Restart servidores
5. Testar novamente
```

### Cenário 2: Backend ✅, Frontend ❌

```
🟠 PROBLEMA: Frontend .env não carregado

AÇÃO IMEDIATA:
1. Verificar se arquivo .env existe na raiz do projeto
2. Se não existe, criar
3. Adicionar: VITE_GOOGLE_CLIENT_ID=seu_client_id
4. Terminal: Ctrl+C para parar Vite
5. Terminal: npm run dev para restart
6. Browser: F5 (refresh)
7. Testar novamente
```

### Cenário 3: Backend ✅, Frontend ✅

```
🟡 PROBLEMA: Tudo OK no lado nosso, probably Google Cloud config

AÇÃO IMEDIATA:
1. Abrir Google Cloud: https://console.cloud.google.com/
2. Navegar: APIs & Services → Credentials
3. Clicar no seu OAuth Client
4. Verificar seção "Authorized JavaScript origins"
   - Deve conter: http://localhost:8081
5. Verificar seção "Authorized redirect URIs"
   - Deve conter: http://localhost:8081
   - Deve conter: http://localhost:8081/auth/callback
6. Salvar alterações
7. Testar novamente
```

---

## 🔐 Verificação Google Cloud

Se backend + frontend OK, mas ainda tem erro, execute isto:

```
1. Abrir: https://console.cloud.google.com/
2. Clicar projeto
3. APIs & Services → Credentials
4. Procurar seu OAuth Client (Web application)
5. Clicar nele

VERIFICAR ISTO:

☐ Authorized JavaScript origins NÃO está vazio?
   └─ Se vazio: Adicionar http://localhost:8081
   
☐ Contém http://localhost:8081?
   └─ Se não: Adicionar agora
   
☐ Authorized redirect URIs NÃO está vazio?
   └─ Se vazio: Adicionar http://localhost:8081/auth/callback
   
☐ Contém http://localhost:8081 E http://localhost:8081/auth/callback?
   └─ Se não: Adicionar ambos

6. Clicar "Save"
7. Voltar ao navegador, F5 (refresh)
8. Testar login novamente
```

---

## 📋 Checklist Rápido de 2 Minutos

- [ ] Backend .env tem GOOGLE_CLIENT_ID = valor_correto_com_dots_googleapis
- [ ] Frontend .env tem VITE_GOOGLE_CLIENT_ID = mesmo_valor
- [ ] Ambos têm formato: número-letras.apps.googleusercontent.com
- [ ] Google Cloud: OAuth Client criado e ativo
- [ ] Google Cloud: Authorized JavaScript origins = localhost:8081
- [ ] Google Cloud: Authorized redirect URIs inclui localhost:8081
- [ ] Backend reiniciado (python -m uvicorn ...)
- [ ] Frontend reiniciado (npm run dev)
- [ ] Browser refresh (F5)
- [ ] DevTools Console limpa (sem erros 401)

---

## 🎯 Se Ainda Assim Não Funcionar

```bash
# Execute isto para gerar um "bug report"

cat > GOOGLE_OAUTH_DIAGNOSTIC.txt << 'EOF'
=== DIAGNÓSTICO GOOGLE OAUTH ERROR 401 ===
Data: $(date)

BACKEND:
$(cd backend && python << 'PYEOF'
import os
from dotenv import load_dotenv
load_dotenv()
print(f"GOOGLE_CLIENT_ID: {os.getenv('GOOGLE_CLIENT_ID', 'VAZIO')[:40]}...")
PYEOF
)

FRONTEND ENV FILE EXISTS:
$(test -f .env && echo "✅ SIM" || echo "❌ NÃO")

FRONTEND ENV CONTENT:
$(grep VITE_GOOGLE_CLIENT_ID .env 2>/dev/null || echo "NÃO ENCONTRADO")

GOOGLE CLOUD STATUS:
- Abrir console.cloud.google.com
- Verificar se OAuth Client está ativo
- Verificar origins/redirects

PRÓXIMA AÇÃO:
Envie este arquivo e uma screenshot do erro DevTools
EOF

cat GOOGLE_OAUTH_DIAGNOSTIC.txt
```

---

## 🆘 Último Recurso (Nuclear Option)

Se NADA funcionou, faça isto:

```bash
# 1. Parar tudo
# Ctrl+C em todos os terminais

# 2. Deletar caches
rm -r backend/__pycache__
rm -r node_modules/.vite

# 3. Criar novo .env do zero
cat > backend/.env << 'EOF'
GOOGLE_CLIENT_ID=COPIE_AQUI_SEU_CLIENT_ID_EXATAMENTE
ENVIRONMENT=development
EOF

# 4. Criar novo frontend .env
cat > .env << 'EOF'
VITE_GOOGLE_CLIENT_ID=COPIE_AQUI_SEU_CLIENT_ID_EXATAMENTE
EOF

# 5. Restart completo
cd backend
python -m uvicorn app.main:app --reload

# Terminal 2:
npm run dev

# Browser: http://localhost:8081
# F12 Console: testar novamente
```

---

## 📞 Resultado

| Situação | Próxima Ação |
|----------|-------------|
| ✅ Login Google funciona | Ler: GOOGLE_OAUTH_CSP_QUICK_START.md |
| ❌ Ainda 401 error | Enviar screenshot + GOOGLE_OAUTH_DIAGNOSTIC.txt |
| ❌ Erro diferente | Documentar exato erro + enviar |

---

**Tempo total:** ~2 minutos  
**Deve resolver:** 90% dos casos de "401: invalid_client"

**Data:** 19 de Fevereiro de 2026  
**Versão:** 1.0 - Diagnóstico Rápido
