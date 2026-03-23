# 🔍 Debug: Google OAuth 401 Error

## Problema
Após clicar "Fazer Login com o Google", a página retorna **HTTP Error: 401** no frontend.

## Flow do Google Login

```
1. Frontend: Clica "Fazer Login com Google"
2. GoogleLogin Component: Abre Google login
3. Google: User seleciona conta
4. Google: Redireciona com authorization code
5. Backend: GET /google/callback (troca code por token)
6. Backend: Redireciona para frontend com tokens
7. Frontend: Recebe tokens em URL
8. Frontend: Chama POST /api/auth/google com id_token
9. ❌ Backend: Retorna 401 - "Token Google inválido"
```

## O que está acontecendo

### Cenário 1: Token Google é inválido
- O token pode estar vencido
- O token pode ser forjado
- O GOOGLE_CLIENT_ID pode estar errado/diferente do usado para gerar token

### Cenário 2: O endpoint POST /google não está pegando o token corretamente
- O frontend está enviando `{ id_token: ..., email, name }`
- A schema espera exatamente isso
- Mas algo pode estar errado na validação

## Solução: Melhorar Logs e Diagnosticar

Vou adicionar logs MUITO detalhados no endpoint POST /google para ver:
1. O que está sendo recebido
2. Qual é o erro exato da validação do token
3. Se o email/google_id estão corretos

## Checklist

- [ ] Verificar se GOOGLE_CLIENT_ID no backend/.env é igual ao do Google Console
- [ ] Verificar se VITE_GOOGLE_CLIENT_ID no frontend/.env é igual
- [ ] Verificar se o comotoken está sendo enviado corretamente
- [ ] Verificar o erro exato nos logs do backend
- [ ] Testar a validação do token com um token JWT real

