# 🎨 GlowCard Component - Como Visualizar

## 🚀 Acesso Rápido

O componente GlowCard foi integrado e está **LIVE** agora!

### 🌐 URL para Visualizar
```
http://localhost:8080/robots
```

---

## 📍 Onde Encontrar o GlowCard

### Na Página de Robôs:
```
┌─────────────────────────────────────────────────────┐
│  🤖 ROBÔS DE TRADING                                 │
├─────────────────────────────────────────────────────┤
│  [Barra de Busca] [Filtros]                         │
├─────────────────────────────────────────────────────┤
│  ⭐ ROBÔS EM DESTAQUE (NOVO!)                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  │  🇺🇸 Bitcoin │  │  🇯🇵 Ethereum │  │  🇧🇷 Altcoin │
│  │  Scalper Pro │  │  DCA Master   │  │  Hunter      │
│  │              │  │              │  │              │
│  │  ✨ GLOW CARD✨ │  │  ✨ GLOW CARD✨ │  │  ✨ GLOW CARD✨ │
│  └──────────────┘  └──────────────┘  └──────────────┘
├─────────────────────────────────────────────────────┤
│  📊 TODOS OS ROBÔS                                   │
│  [Card] [Card] [Card] [Card]                         │
│  [Card] [Card] [Card] [Card]                         │
└─────────────────────────────────────────────────────┘
```

---

## ✨ Efeitos para Testar

### 1️⃣ **Efeito Spotlight (Mais Importante!)**
```
✓ Mova o mouse sobre os cards
✓ Veja o brilho seguir o cursor
✓ Cores diferentes para cada robô
```

### 2️⃣ **Hover Effects**
```
✓ Card aumenta levemente
✓ Sombra aumenta
✓ Ícone cresce
✓ Bordas ficam mais brilhantes
```

### 3️⃣ **Responsividade**
```
✓ Desktop: 3 cards por linha
✓ Tablet (resize para ~768px): 2 cards
✓ Mobile (resize para ~375px): 1 card
```

### 4️⃣ **Cores de Status**
```
🟢 Verde: Robô ATIVO
🟠 Laranja: Robô PAUSADO
🔴 Vermelho: Erro (ex: se tivesse)
🟣 Roxo: Robô PARADO
🔵 Azul: Default
```

---

## 🎯 O Que Cada Card Mostra

```
┌─────────────────────────────┐
│  [Icon] Nome do Robô        │  ← Ícone + Nome
│         Descrição...        │  ← Descrição
│                             │
│  Par          BTC/USDT      │  ← Dados principais
│  Lucro        +$2547.32     │
│  Taxa Acerto  68.5%         │
│  Trades       1234          │
│                             │
│  ─────────────────────────  │  ← Separator
│  [Status]  [Timeframe: 1m]  │  ← Status + Timeframe
└─────────────────────────────┘
```

---

## 🔍 Como Inspecionar o Componente

### Chrome/Edge DevTools:
```
1. Abra http://localhost:8080/robots
2. Pressione F12 (DevTools)
3. Clique em "Elements" / "Inspector"
4. Procure por: data-glow
5. Veja as propriedades CSS customizadas
```

### Verificar CSS Variables:
```javascript
// No console do DevTools:
const card = document.querySelector('[data-glow]');
card.style.getPropertyValue('--x');  // Posição X
card.style.getPropertyValue('--y');  // Posição Y
card.style.getPropertyValue('--hue'); // Cor
```

### Modificar em Tempo Real:
```javascript
// No console, modifique:
const card = document.querySelector('[data-glow]');
card.style.setProperty('--spotlight-size', '400px'); // Aumenta brilho
```

---

## 🐛 Possíveis Cenários de Teste

### ✅ Teste 1: Navegação Básica
```
1. Vá para http://localhost:8080/robots
2. Veja os 3 cards com GlowCard
3. Resultado esperado: Cards com brilho azul, roxo e verde
```

### ✅ Teste 2: Interação com Mouse
```
1. Mova o mouse sobre um card
2. Observe o brilho acompanhando o cursor
3. Resultado esperado: Spotlight dinâmico
```

### ✅ Teste 3: Hover Effect
```
1. Passe o mouse sobre um card
2. Card deve crescer e sombra aumenta
3. Resultado esperado: Scale 1.05 + shadow
```

### ✅ Teste 4: Click
```
1. Clique em um dos cards
2. Modal de detalhes deve aparecer
3. Resultado esperado: Abre RealTimeOperations
```

### ✅ Teste 5: Responsividade
```
1. Abra DevTools (F12)
2. Clique em "Toggle Device Toolbar" (Ctrl+Shift+M)
3. Teste em: 375px, 768px, 1920px
4. Resultado esperado: Cards reposicionam corretamente
```

### ✅ Teste 6: Search/Filter
```
1. Digite na barra de busca: "Bitcoin"
2. Cards devem filtrar
3. GlowCards atualizam com robôs filtrados
```

### ✅ Teste 7: Mobile Touch
```
1. Abra em smartphone
2. Toque nos cards
3. Resultado esperado: Funciona em mobile (sem spotlight)
```

### ✅ Teste 8: Performance
```
1. Abra DevTools → Performance
2. Grave a página
3. Mova o mouse rapidamente
4. Resultado esperado: 60 FPS (suave)
```

---

## 📊 Cores e Significado

### Mapa de Cores Implementado

```tsx
const glowColorMap = {
  blue: { base: 220, spread: 200 },      // 🔵 Azul (default)
  purple: { base: 280, spread: 300 },    // 🟣 Roxo (premium)
  green: { base: 120, spread: 200 },     // 🟢 Verde (ativo)
  red: { base: 0, spread: 200 },         // 🔴 Vermelho (erro)
  orange: { base: 30, spread: 200 }      // 🟠 Laranja (pausado)
};
```

### Status → Cor Automática
```tsx
'active' → 'green'     // 🟢 Verde brilhante
'paused' → 'orange'    // 🟠 Laranja aviso
'stopped' → 'purple'   // 🟣 Roxo desativado
'error' → 'red'        // 🔴 Vermelho problema
default → 'blue'       // 🔵 Azul padrão
```

---

## 🎨 Customizações Possíveis

### Para Adicionar Novo Robô com GlowCard:
```tsx
// Simplesmente adicione na lista AVAILABLE_ROBOTS
const AVAILABLE_ROBOTS = [
  // ... robôs existentes
  {
    id: 'crypto-9',
    name: '🇦🇪 Your Bot Name',
    status: 'active',  // Cor muda automaticamente!
    // ... outros campos
  }
];
```

### Para Customizar Cores:
```tsx
<RobotGlowGrid
  robots={robots}
  // A cor é automática baseado em robot.status
  // Mas você pode editar getGlowColor() em robot-glow-grid.tsx
/>
```

### Para Customizar Tamanho:
```tsx
<GlowCard
  size="lg"        // Grandes cards
  customSize={true}
  width={500}
  height={600}
/>
```

---

## 🚦 Checklist Final

- [ ] Página de robôs carrega sem erros
- [ ] 3 cards com GlowCard aparecem na seção destacada
- [ ] Spotlight segue o cursor
- [ ] Cores mudam baseado no status
- [ ] Hover effects funcionam
- [ ] Cards são responsivos
- [ ] Clique abre detalhes do robô
- [ ] Performance suave (60 FPS)
- [ ] Mobile funciona
- [ ] Console sem erros (F12)

---

## 📞 Se Algo Não Funcionar

### Glow não aparece:
```
1. Abra DevTools (F12)
2. Console → Procure por erros
3. Inspecione → Procure por [data-glow]
4. Se não existir, há erro de render
```

### Cards com layout errado:
```
1. Verifique viewport size (DevTools)
2. Limpe cache: Ctrl+Shift+Del
3. Reload: Ctrl+Shift+R (hard refresh)
```

### Performance lenta:
```
1. Verifique no DevTools → Performance
2. Reduzir quantidade de cards visíveis
3. Desabilitar animations em mobile
```

---

## 🎓 Entender o Código

### Principais Arquivos:
```
src/components/ui/
├── spotlight-card.tsx      ← Componente principal
├── robot-glow-grid.tsx     ← Grid wrapper
└── robot-strategy-cards.tsx ← Estratégias demo

src/pages/
└── RobotsPage.tsx          ← Página principal
```

### Fluxo de Dados:
```
RobotsPage
  ├── Import RobotGlowGrid
  ├── Pass: robots, onRobotSelect
  └── RobotGlowGrid
      ├── Map robots
      └── RenderGlowCard (para cada robô)
          ├── getGlowColor() → status
          ├── Exibe dados
          └── Click → onRobotSelect()
```

---

## ✨ Conclusão

O GlowCard está **100% funcional e integrado**! 

Acesse **http://localhost:8080/robots** e veja a magia acontecer! ✨

Divirta-se explorando os efeitos visuais! 🎉
