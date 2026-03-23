import { useState, useRef, useEffect } from 'react';
import { Send, MessageCircle, X, ChevronDown, HelpCircle, HeadphonesIcon, Zap } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { CryptoTicker } from '../layout/CryptoTicker';
import { API_BASE_URL } from '@/config/constants';
import { authService } from '@/services/authService';

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

interface RobotsChatProps {
  onExchangeRegistered?: (registered: boolean) => void;
  onSelectRobot?: (robotId: string) => void;
  isOpen?: boolean;
  onClose?: () => void;
}

const FAQ_ITEMS = [
  {
    question: '❓ Como configurar meu robô?',
    answer: 'Clique no robô desejado, siga as 4 etapas de configuração de API da Binance e pronto! Seu robô estará ativo.',
  },
  {
    question: '🔒 É seguro conectar minha API?',
    answer: 'Sim! Use API Keys com permissões restritas. Recomendamos ativar whitelist de IP na Binance.',
  },
  {
    question: '💰 Qual é o lucro médio?',
    answer: 'Varia por estratégia (6-15% ao mês). Depende do capital, volatilidade e configuração do robô.',
  },
  {
    question: '⏱️ Posso pausar um robô?',
    answer: 'Sim! Use o botão "Pausar" no dashboard. Você pode reiniciar a qualquer momento sem perder configurações.',
  },
  {
    question: '🌍 Quais corretoras são suportadas?',
    answer: 'Atualmente suportamos Binance 🇺🇸 - a maior plataforma de trading do mundo!',
  },
  {
    question: '⚡ Como começo?',
    answer: 'Primeiro, confirme se tem conta na Binance. Depois escolha um robô e configure sua API.',
  },
];

const SUPPORT_LINKS = [
  { icon: '📖', label: 'Documentação', url: 'https://docs.pro-trader-ea.com', color: 'bg-blue-600/30 hover:bg-blue-600/50 text-blue-300 border-blue-500/30' },
  { icon: '💬', label: 'Discord', url: 'https://discord.gg/pro-trader-ea', color: 'bg-purple-600/30 hover:bg-purple-600/50 text-purple-300 border-purple-500/30' },
  { icon: '📧', label: 'Email', url: 'mailto:suporte@pro-trader-ea.com', color: 'bg-orange-600/30 hover:bg-orange-600/50 text-orange-300 border-orange-500/30' },
  { icon: '🎥', label: 'Tutoriais', url: 'https://youtube.com/@pro-trader-ea', color: 'bg-red-600/30 hover:bg-red-600/50 text-red-300 border-red-500/30' },
  { icon: '🐦', label: 'Twitter', url: 'https://twitter.com/pro_trader_ea', color: 'bg-sky-600/30 hover:bg-sky-600/50 text-sky-300 border-sky-500/30' },
  { icon: '🌐', label: 'Website', url: 'https://pro-trader-ea.com', color: 'bg-green-600/30 hover:bg-green-600/50 text-green-300 border-green-500/30' },
];

export function RobotsChat({ onExchangeRegistered, onSelectRobot, isOpen = true, onClose }: RobotsChatProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [exchangeRegistered, setExchangeRegistered] = useState<boolean | null>(null);
  const [showFAQ, setShowFAQ] = useState(false);
  const [showSupport, setShowSupport] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [minimized, setMinimized] = useState(false);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Initial greeting message + fetch history
  useEffect(() => {
    const initChat = async () => {
      try {
        // Try to fetch chat history from backend
        const token = await authService.getAccessToken();
        
        // Assuming there's a GET /api/bots/chat-history endpoint
        // If the endpoint doesn't exist yet, the fetch will fail gracefully
        const response = await fetch(`${API_BASE_URL}/api/bots/chat-history?limit=50`, {
          method: 'GET',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
        });

        let historyMessages: ChatMessage[] = [];
        
        if (response.ok) {
          const data = await response.json();
          // Transform backend messages to component format
          historyMessages = (data.messages || []).map((msg: any) => ({
            id: msg.id || `msg_${Date.now()}`,
            role: msg.role || 'assistant',
            content: msg.content || '',
            timestamp: msg.timestamp ? new Date(msg.timestamp) : new Date(),
          }));
          console.log(`[✓] Loaded ${historyMessages.length} chat messages from server`);
        } else {
          console.warn('[⚠] Chat history endpoint not available, using default greeting');
        }

        // Add initial greeting if no history
        const greeting: ChatMessage = {
          id: '0',
          role: 'assistant',
          content: '👋 Olá! Bem-vindo ao nosso sistema de robôs de trading!\n\n💡 Posso ajudá-lo com:\n• Perguntas frequentes (FAQ)\n• Links de suporte\n• Configuração de robôs\n• Dúvidas sobre API\n\nDigite "faq" ou "suporte" ou faça uma pergunta! 🚀',
          timestamp: new Date(),
        };

        // Set messages: greeting first, then history
        if (historyMessages.length > 0) {
          setMessages(historyMessages);
        } else {
          setMessages([greeting]);
        }
      } catch (error) {
        console.error('[✗] Error loading chat history:', error);
        // Fallback to greeting
        const greeting: ChatMessage = {
          id: '0',
          role: 'assistant',
          content: '👋 Olá! Bem-vindo ao nosso sistema de robôs de trading!\n\n💡 Posso ajudá-lo com:\n• Perguntas frequentes (FAQ)\n• Links de suporte\n• Configuração de robôs\n• Dúvidas sobre API\n\nDigite "faq" ou "suporte" ou faça uma pergunta! 🚀',
          timestamp: new Date(),
        };
        setMessages([greeting]);
      }
    };

    if (messages.length === 0) {
      initChat();
    }
  }, []);

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim()) return;

    // Add user message
    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: input,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    const userInput = input;
    setInput('');
    setIsLoading(true);

    // Save user message to backend
    try {
      const token = await authService.getAccessToken();
      await fetch(`${API_BASE_URL}/api/bots/chat-message`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          role: 'user',
          content: userInput,
        }),
      }).catch(() => {
        // Silently fail - don't block user experience
        console.warn('[⚠] Failed to save user message to backend');
      });
    } catch (err) {
      console.error('[✗] Error saving message:', err);
    }

    // Simulate bot response
    setTimeout(async () => {
      let responseContent = '';
      const lowerInput = userInput.toLowerCase();

      // Check for special commands
      if (lowerInput.includes('faq') || lowerInput.includes('frequente')) {
        setShowFAQ(true);
        responseContent = '📚 Mostrando perguntas frequentes abaixo! Clique em qualquer uma para ver a resposta completa.';
      } else if (lowerInput.includes('suporte') || lowerInput.includes('ajuda') || lowerInput.includes('help')) {
        setShowSupport(true);
        responseContent = '🆘 Aqui estão os canais de suporte disponíveis! Escolha o que preferir para entrar em contato.';
      } else if (lowerInput.includes('configurar') || lowerInput.includes('setup')) {
        responseContent =
          '⚙️ **Para configurar um robô:**\n\n' +
          '1️⃣ Clique no robô na grade\n' +
          '2️⃣ Vá para guia de API (Binance)\n' +
          '3️⃣ Cole sua API Key e Secret\n' +
          '4️⃣ Teste a conexão\n' +
          '✅ Pronto! O robô está ativo\n\n' +
          'Tem dúvidas? Digite "faq" ou "suporte"';
      } else if (lowerInput.includes('segurança') || lowerInput.includes('api')) {
        responseContent =
          '🔒 **Segurança de API:**\n\n' +
          '✅ Use permissões restritas (Trading apenas)\n' +
          '✅ Ative whitelist de IP\n' +
          '✅ Nunca compartilhe suas credenciais\n' +
          '✅ Nós não armazenamos suas chaves\n' +
          '✅ Use chaves secundárias, não mestras\n\n' +
          'Mais info em suporte! 🆘';
      } else if (lowerInput.includes('corretora') || lowerInput.includes('exchange')) {
        responseContent =
          '🌍 **Corretora Suportada:**\n\n' +
          '🇺🇸 Binance - A maior plataforma de trading do mundo\n' +
          '- Maior volume de negociação\n' +
          '- Pares mais variados\n' +
          '- Taxas competitivas\n' +
          '- Segurança robusta\n\n' +
          'Acesse: https://binance.com';
      } else if (lowerInput.includes('lucro') || lowerInput.includes('retorno') || lowerInput.includes('ganho')) {
        responseContent =
          '💰 **Rentabilidade esperada:**\n\n' +
          '📊 Scalping: 6-12% ao mês\n' +
          '📈 Trend Following: 10-15% ao mês\n' +
          '🔄 Grid Trading: 8-10% ao mês\n' +
          '💎 DCA: 7-9% ao mês\n\n' +
          '⚠️ Resultados variam com mercado e configuração\n' +
          '⚠️ Passado não garante futuro';
      } else if (lowerInput.includes('começar') || lowerInput.includes('iniciar') || lowerInput.includes('start')) {
        responseContent =
          '🚀 **Como começar:**\n\n' +
          '1. Confirme sua conta em uma corretora\n' +
          '2. Escolha um robô da grade\n' +
          '3. Configure a API (4 etapas)\n' +
          '4. Veja operações em tempo real!\n\n' +
          'Qual robô você quer tentar primeiro?';
      } else {
        responseContent = '💬 Entendi sua dúvida! Para respostas rápidas:\n\n📚 Digite "faq" para perguntas frequentes\n🆘 Digite "suporte" para links de ajuda\n\nOu continue perguntando! 😊';
      }

      const assistantMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: responseContent,
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, assistantMessage]);
      
      // Save assistant message to backend
      try {
        const token = await authService.getAccessToken();
        await fetch(`${API_BASE_URL}/api/bots/chat-message`, {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            role: 'assistant',
            content: responseContent,
          }),
        }).catch(() => {
          console.warn('[⚠] Failed to save assistant message to backend');
        });
      } catch (err) {
        console.error('[✗] Error saving assistant message:', err);
      }
      
      setIsLoading(false);
    }, 500);
  };

  if (!isOpen) return null;

  return (
    <div className={`fixed bottom-4 right-4 rounded-2xl border border-primary/40 transition-all duration-300 z-50 ${minimized ? 'w-72 h-14' : 'w-80 h-[420px]'} flex flex-col overflow-hidden bg-gradient-to-b from-slate-900/95 via-slate-900/98 to-black/95 backdrop-blur-xl shadow-[0_0_60px_-15px_rgba(0,200,255,0.3),0_25px_50px_-12px_rgba(0,0,0,0.8),inset_0_1px_0_0_rgba(255,255,255,0.05)]`}>
      {/* Header */}
      <div className="bg-gradient-to-r from-primary/30 via-accent/20 to-primary/30 border-b border-primary/40 p-4 flex items-center justify-between flex-shrink-0 shadow-[inset_0_-1px_0_0_rgba(0,200,255,0.1),0_4px_20px_-5px_rgba(0,0,0,0.5)]">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-full bg-gradient-to-br from-primary via-cyan-400 to-accent flex items-center justify-center shadow-[0_0_20px_rgba(0,200,255,0.5),inset_0_1px_0_0_rgba(255,255,255,0.3)] animate-pulse">
            <MessageCircle className="w-4 h-4 text-white drop-shadow-lg" />
          </div>
          <div>
            <h3 className="font-bold text-sm bg-gradient-to-r from-white to-cyan-200 bg-clip-text text-transparent">Robô Assistant</h3>
            <p className="text-xs text-emerald-400 flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse shadow-[0_0_8px_rgba(52,211,153,0.8)]"></span> Online agora</p>
          </div>
        </div>
        <div className="flex gap-2">
          <Button variant="ghost" size="sm" onClick={() => setMinimized(!minimized)}>
            <ChevronDown className={`w-4 h-4 transition-transform ${minimized ? 'rotate-180' : ''}`} />
          </Button>
          <Button variant="ghost" size="sm" onClick={onClose}>
            <X className="w-4 h-4" />
          </Button>
        </div>
      </div>

      {/* Content Area */}
      {!minimized && (
        <>
          <CryptoTicker compact />

          {/* FAQ Section */}
          {showFAQ && (
            <div className="border-b border-primary/30 bg-slate-800/50 p-3 max-h-48 overflow-y-auto">
              <div className="flex items-center justify-between mb-3">
                <h4 className="text-white font-semibold text-sm flex items-center gap-2">
                  <HelpCircle className="w-4 h-4" /> Perguntas Frequentes
                </h4>
                <button
                  onClick={() => setShowFAQ(false)}
                  className="text-xs text-muted-foreground hover:text-foreground"
                >
                  ✕ Fechar
                </button>
              </div>
              <div className="space-y-2">
                {FAQ_ITEMS.map((item, idx) => (
                  <button
                    key={idx}
                    onClick={() => {
                      handleSendMessage(new Event('submit') as any);
                      setInput(item.question);
                      setShowFAQ(false);
                    }}
                    className="w-full text-left text-xs bg-slate-700 hover:bg-slate-600 text-slate-100 p-2 rounded transition"
                  >
                    {item.question}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Support Links Section */}
          {showSupport && (
            <div className="border-b border-primary/30 bg-slate-800/50 p-3 max-h-48 overflow-y-auto">
              <div className="flex items-center justify-between mb-3">
                <h4 className="text-white font-semibold text-sm flex items-center gap-2">
                  <HeadphonesIcon className="w-4 h-4" /> Links de Suporte
                </h4>
                <button
                  onClick={() => setShowSupport(false)}
                  className="text-xs text-muted-foreground hover:text-foreground"
                >
                  ✕ Fechar
                </button>
              </div>
              <div className="grid grid-cols-2 gap-2">
                {SUPPORT_LINKS.map((link, idx) => (
                  <a
                    key={idx}
                    href={link.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className={`text-xs ${link.color} border p-2 rounded transition flex items-center gap-1 justify-center`}
                  >
                    <span>{link.icon}</span>
                    <span>{link.label}</span>
                  </a>
                ))}
              </div>
            </div>
          )}

          {/* Messages Area */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-gradient-to-b from-transparent via-slate-900/30 to-slate-900/50">
            {messages.map((message) => (
              <div key={message.id} className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div
                  className={`max-w-[85%] px-4 py-3 rounded-xl text-sm leading-relaxed ${
                    message.role === 'user'
                      ? 'bg-gradient-to-br from-primary via-cyan-500 to-accent text-white rounded-br-none shadow-[0_4px_15px_-3px_rgba(0,200,255,0.4),inset_0_1px_0_0_rgba(255,255,255,0.2)]'
                      : 'bg-gradient-to-br from-slate-800/90 to-slate-900/90 text-foreground rounded-bl-none border border-slate-700/50 shadow-[0_4px_15px_-3px_rgba(0,0,0,0.3),inset_0_1px_0_0_rgba(255,255,255,0.05)]'
                  }`}
                >
                  <p className="whitespace-pre-wrap">{message.content}</p>
                  <span className="text-xs opacity-70 mt-1 block">{message.timestamp.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })}</span>
                </div>
              </div>
            ))}
            {isLoading && (
              <div className="flex justify-start">
                <div className="bg-muted px-4 py-3 rounded-lg text-sm">
                  <div className="flex gap-2">
                    <div className="w-2 h-2 rounded-full bg-primary animate-bounce"></div>
                    <div className="w-2 h-2 rounded-full bg-primary animate-bounce" style={{ animationDelay: '0.1s' }}></div>
                    <div className="w-2 h-2 rounded-full bg-primary animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                  </div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Quick Actions */}
          <div className="border-t border-primary/40 p-2 flex gap-1.5 flex-wrap justify-center bg-gradient-to-r from-slate-900/50 via-slate-800/30 to-slate-900/50 shadow-[inset_0_1px_0_0_rgba(255,255,255,0.03)]">
            <button
              onClick={() => setShowFAQ(!showFAQ)}
              className="text-xs bg-gradient-to-br from-blue-600/40 to-blue-700/40 hover:from-blue-500/50 hover:to-blue-600/50 text-blue-200 border border-blue-400/30 px-2.5 py-1.5 rounded-lg transition-all duration-200 flex items-center gap-1.5 shadow-[0_2px_10px_-3px_rgba(59,130,246,0.4)] hover:shadow-[0_4px_15px_-3px_rgba(59,130,246,0.5)] hover:scale-105"
            >
              <HelpCircle className="w-3 h-3" /> FAQ
            </button>
            <button
              onClick={() => setShowSupport(!showSupport)}
              className="text-xs bg-gradient-to-br from-emerald-600/40 to-emerald-700/40 hover:from-emerald-500/50 hover:to-emerald-600/50 text-emerald-200 border border-emerald-400/30 px-2.5 py-1.5 rounded-lg transition-all duration-200 flex items-center gap-1.5 shadow-[0_2px_10px_-3px_rgba(52,211,153,0.4)] hover:shadow-[0_4px_15px_-3px_rgba(52,211,153,0.5)] hover:scale-105"
            >
              <HeadphonesIcon className="w-3 h-3" /> Suporte
            </button>
            <button
              onClick={() => {
                setInput('Como configurar?');
              }}
              className="text-xs bg-gradient-to-br from-purple-600/40 to-purple-700/40 hover:from-purple-500/50 hover:to-purple-600/50 text-purple-200 border border-purple-400/30 px-2.5 py-1.5 rounded-lg transition-all duration-200 flex items-center gap-1.5 shadow-[0_2px_10px_-3px_rgba(168,85,247,0.4)] hover:shadow-[0_4px_15px_-3px_rgba(168,85,247,0.5)] hover:scale-105"
            >
              <Zap className="w-3 h-3" /> Setup
            </button>
          </div>

          {/* Input Area */}
          <form onSubmit={handleSendMessage} className="border-t border-primary/40 p-4 bg-gradient-to-b from-slate-900/80 to-black/90 flex-shrink-0 shadow-[inset_0_1px_0_0_rgba(0,200,255,0.1)]">
            <div className="flex gap-2">
              <Input
                placeholder="Sua pergunta aqui..."
                value={input}
                onChange={(e) => setInput(e.target.value)}
                disabled={isLoading}
                className="text-sm"
              />
              <Button type="submit" size="sm" disabled={isLoading || !input.trim()} className="gap-2">
                <Send className="w-4 h-4" />
              </Button>
            </div>
          </form>
        </>
      )}
    </div>
  );
}
