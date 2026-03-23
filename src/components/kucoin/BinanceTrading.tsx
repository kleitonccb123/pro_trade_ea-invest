import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { 
  Play, 
  Square, 
  Settings, 
  TrendingUp, 
  TrendingDown, 
  Activity,
  Wallet,
  AlertTriangle,
  CheckCircle,
  Eye,
  EyeOff,
  ArrowUp,
  ArrowDown,
  Terminal,
  Wifi
} from 'lucide-react';
import { tradingApi, botsApi } from '@/lib/api';

interface Bot {
  id: number;
  name: string;
  strategy: string;
  symbol?: string;
  description?: string;
  is_active?: boolean;
}

interface TradingCredentials {
  api_key: string;
  api_secret: string;
}

interface TradingSession {
  id: number;
  bot_instance_id: number;
  symbol: string;
  initial_balance: number;
  current_balance: number;
  total_trades: number;
  profitable_trades: number;
  total_pnl: number;
  max_drawdown: number;
  is_active: boolean;
  started_at: string;
  ended_at?: string;
}

interface Balance {
  asset: string;
  free: number;
  locked: number;
  total: number;
}

interface Trade {
  id: number;
  symbol: string;
  side: 'BUY' | 'SELL';
  order_type: string;
  quantity: number;
  price: number;
  executed_price?: number;
  executed_quantity?: number;
  status: string;
  pnl: number;
  commission: number;
  created_at: string;
  filled_at?: string;
  entry_reason?: string;
}

const BinanceTrading: React.FC = () => {
  const [activeTab, setActiveTab] = useState('setup');
  const [credentials, setCredentials] = useState<TradingCredentials>({
    api_key: '',
    api_secret: ''
  });
  const [showApiSecret, setShowApiSecret] = useState(false);
  const [credentialsValid, setCredentialsValid] = useState<boolean | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [balances, setBalances] = useState<Balance[]>([]);
  const [sessions, setSessions] = useState<TradingSession[]>([]);
  const [selectedSession, setSelectedSession] = useState<TradingSession | null>(null);
  const [trades, setTrades] = useState<Trade[]>([]);
  const [wsConnection, setWsConnection] = useState<WebSocket | null>(null);
  const [executionLogs, setExecutionLogs] = useState<string[]>([]);
  const [isWebSocketConnected, setIsWebSocketConnected] = useState(false);
  const [availableBots, setAvailableBots] = useState<Bot[]>([]);
  const [loadingBots, setLoadingBots] = useState(false);

  // Configuração inicial
  const [selectedSymbol, setSelectedSymbol] = useState('BTCUSDT');
  const [initialBalance, setInitialBalance] = useState(100);
  const [selectedBot, setSelectedBot] = useState<number | null>(null);

  const symbols = [
    'BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'ADAUSDT', 'DOTUSDT',
    'XRPUSDT', 'LTCUSDT', 'LINKUSDT', 'BCHUSDT', 'XLMUSDT'
  ];

  useEffect(() => {
    loadTradingSessions();
    loadAvailableBots();
    return () => {
      if (wsConnection) {
        wsConnection.close();
      }
    };
  }, []);

  const testCredentials = async () => {
    if (!credentials.api_key || !credentials.api_secret) {
      setError('Por favor, preencha as credenciais da Binance');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await tradingApi.testCredentials(credentials);
      setCredentialsValid(response.valid);
      
      if (response.valid) {
        // Salvar credenciais se válidas
        await tradingApi.createCredentials(credentials);
        await loadBalances();
      } else {
        setError(response.error || 'Credenciais inválidas');
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Erro ao testar credenciais');
      setCredentialsValid(false);
    } finally {
      setLoading(false);
    }
  };

  const loadBalances = async () => {
    try {
      const response = await tradingApi.getBalances();
      setBalances(response);
    } catch (err: any) {
      console.error('Erro ao carregar saldos:', err);
    }
  };

  const loadTradingSessions = async () => {
    try {
      const response = await tradingApi.getSessions();
      setSessions(response);
    } catch (err: any) {
      console.error('Erro ao carregar sessões:', err);
    }
  };

  const createTradingSession = async () => {
    if (!selectedBot) {
      setError('Selecione um bot primeiro');
      return;
    }

    if (!credentials.api_key || !credentials.api_secret) {
      setError('Configure as credenciais da Binance primeiro');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const sessionData = {
        bot_instance_id: selectedBot,
        symbol: selectedSymbol,
        initial_balance: initialBalance,
        api_key: credentials.api_key,
        api_secret: credentials.api_secret
      };

      const response = await tradingApi.createSession(sessionData);
      const newSession = response;
      
      setSessions([...sessions, newSession]);
      setSelectedSession(newSession);
      setActiveTab('monitor');
      
      // Conectar WebSocket para dados em tempo real
      connectWebSocket(newSession.id);
      
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Erro ao criar sessão de trading');
    } finally {
      setLoading(false);
    }
  };

  const addExecutionLog = (message: string) => {
    const timestamp = new Date().toLocaleTimeString();
    const logEntry = `[${timestamp}] ${message}`;
    setExecutionLogs(prev => [logEntry, ...prev.slice(0, 49)]); // Manter apenas últimos 50 logs
  };

  const loadAvailableBots = async () => {
    setLoadingBots(true);
    try {
      const bots = await botsApi.list();
      setAvailableBots(bots);
    } catch (err: any) {
      console.error('Erro ao carregar bots:', err);
      addExecutionLog('🔴 Erro ao carregar lista de robôs');
    } finally {
      setLoadingBots(false);
    }
  };

  const connectWebSocket = (sessionId: number) => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/api/trading/ws/${sessionId}`;
    
    const ws = new WebSocket(wsUrl);
    
    ws.onopen = () => {
      console.log('WebSocket conectado');
      setWsConnection(ws);
      setIsWebSocketConnected(true);
      addExecutionLog('🟢 WebSocket conectado - Dados ao vivo iniciados');
    };
    
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      
      if (data.type === 'performance_update') {
        // Atualizar dados em tempo real
        if (selectedSession && selectedSession.id === sessionId) {
          setTrades(data.data.latest_trades || []);
          // Atualizar outras métricas conforme necessário
        }
      } else if (data.type === 'order_executed') {
        addExecutionLog(`📊 Ordem executada: ${data.side} ${data.quantity} ${data.symbol} @ ${data.price}`);
      } else if (data.type === 'order_placed') {
        addExecutionLog(`🎯 Nova ordem: ${data.side} ${data.quantity} ${data.symbol} - ${data.order_type}`);
      } else if (data.type === 'signal_generated') {
        addExecutionLog(`🔍 Sinal detectado: ${data.signal} para ${data.symbol} - Força: ${data.strength}`);
      }
    };
    
    ws.onerror = (error) => {
      console.error('Erro no WebSocket:', error);
      addExecutionLog('🔴 Erro na conexão WebSocket');
    };
    
    ws.onclose = () => {
      console.log('WebSocket desconectado');
      setWsConnection(null);
      setIsWebSocketConnected(false);
      addExecutionLog('🔴 WebSocket desconectado');
    };
  };

  const stopTradingSession = async (sessionId: number) => {
    try {
      await tradingApi.stopSession(sessionId);
      await loadTradingSessions();
      
      if (wsConnection) {
        wsConnection.close();
        setWsConnection(null);
      }
      
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Erro ao parar sessão');
    }
  };

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('pt-BR', {
      style: 'currency',
      currency: 'USD'
    }).format(value);
  };

  const formatPercent = (value: number) => {
    return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`;
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="font-display text-3xl font-bold gradient-text">
          Trading Real - Binance Live
        </h1>
        <div className="flex items-center gap-3">
          {/* Status WebSocket */}
          {isWebSocketConnected && (
            <div className="flex items-center gap-2 text-sm text-emerald-600">
              <div className="w-2 h-2 bg-emerald-500 rounded-full animate-pulse"></div>
              <Wifi className="w-4 h-4" />
              <span>Conectado via WebSocket</span>
            </div>
          )}
          
          {/* Status Credenciais */}
          <Badge variant={credentialsValid ? "success" : "destructive"} className="text-sm">
            {credentialsValid ? "Conectado" : "Desconectado"}
          </Badge>
        </div>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="setup">
            <Settings className="w-4 h-4 mr-2" />
            Configuração
          </TabsTrigger>
          <TabsTrigger value="monitor">
            <Activity className="w-4 h-4 mr-2" />
            Monitoramento
          </TabsTrigger>
          <TabsTrigger value="console">
            <Terminal className="w-4 h-4 mr-2" />
            Console
          </TabsTrigger>
          <TabsTrigger value="history">
            <TrendingUp className="w-4 h-4 mr-2" />
            Histórico
          </TabsTrigger>
        </TabsList>

        <TabsContent value="setup" className="space-y-6">
          {/* Aviso de Trading Real */}
          <Alert variant="destructive" className="border-red-500/50 bg-red-500/10">
            <AlertTriangle className="h-5 w-5" />
            <div className="space-y-2">
              <div className="font-semibold text-red-500">
                🚨 TRADING REAL ATIVO - ALTO RISCO
              </div>
              <div className="text-sm">
                <p>• Este sistema opera com <strong>dinheiro real</strong> na Binance</p>
                <p>• Perdas financeiras são possíveis e podem ser significativas</p>
                <p>• Apenas use fundos que você pode se dar ao luxo de perder</p>
                <p>• Monitore suas posições constantemente</p>
              </div>
            </div>
          </Alert>

          {/* Configuração de Credenciais */}
          <Card className="glass-card">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Wallet className="w-5 h-5" />
                Credenciais Binance
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="api-key">API Key</Label>
                  <Input
                    id="api-key"
                    type="text"
                    placeholder="Sua API Key da Binance"
                    value={credentials.api_key}
                    onChange={(e) => setCredentials({...credentials, api_key: e.target.value})}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="api-secret">API Secret</Label>
                  <div className="relative">
                    <Input
                      id="api-secret"
                      type={showApiSecret ? "text" : "password"}
                      placeholder="Sua API Secret da Binance"
                      value={credentials.api_secret}
                      onChange={(e) => setCredentials({...credentials, api_secret: e.target.value})}
                    />
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      className="absolute right-2 top-1/2 -translate-y-1/2 h-7 w-7"
                      onClick={() => setShowApiSecret(!showApiSecret)}
                    >
                      {showApiSecret ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                    </Button>
                  </div>
                </div>
              </div>
              
              <Button 
                onClick={testCredentials} 
                disabled={loading}
                className="w-full"
              >
                {loading ? 'Testando...' : 'Testar Credenciais'}
              </Button>

              {error && (
                <Alert variant="destructive">
                  <AlertTriangle className="h-4 w-4" />
                  <AlertDescription>{error}</AlertDescription>
                </Alert>
              )}

              {credentialsValid === true && (
                <Alert>
                  <CheckCircle className="h-4 w-4" />
                  <AlertDescription>
                    ✅ Credenciais válidas! Conexão estabelecida com a Binance.
                    <br />
                    <span className="text-yellow-600 font-semibold">⚠️ ATENÇÃO: Trading Real Ativo - Operações usarão dinheiro real!</span>
                  </AlertDescription>
                </Alert>
              )}
            </CardContent>
          </Card>

          {/* Saldos da Conta */}
          {balances.length > 0 && (
            <Card className="glass-card">
              <CardHeader>
                <CardTitle>Saldos da Conta</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  {balances.slice(0, 8).map((balance) => (
                    <div key={balance.asset} className="text-center p-3 bg-muted/20 rounded-lg">
                      <div className="font-semibold">{balance.asset}</div>
                      <div className="text-sm text-muted-foreground">{balance.total.toFixed(6)}</div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Configuração de Sessão */}
          {credentialsValid && (
            <Card className="glass-card">
              <CardHeader>
                <CardTitle>Nova Sessão de Trading</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div className="space-y-2">
                    <Label>Símbolo</Label>
                    <select 
                      className="w-full p-2 rounded border bg-background"
                      value={selectedSymbol}
                      onChange={(e) => setSelectedSymbol(e.target.value)}
                    >
                      {symbols.map(symbol => (
                        <option key={symbol} value={symbol}>{symbol}</option>
                      ))}
                    </select>
                  </div>
                  <div className="space-y-2">
                    <Label>Saldo Inicial</Label>
                    <Input
                      type="number"
                      value={initialBalance}
                      onChange={(e) => setInitialBalance(Number(e.target.value))}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Robô de Trading</Label>
                    <div className="relative">
                      <select 
                        className="w-full p-3 rounded-lg border bg-background text-foreground disabled:opacity-50 disabled:cursor-not-allowed"
                        value={selectedBot || ''}
                        onChange={(e) => setSelectedBot(Number(e.target.value))}
                        disabled={loadingBots}
                      >
                        <option value="" disabled>
                          {loadingBots ? 'Carregando robôs...' : 'Selecione um robô'}
                        </option>
                        {availableBots.map(bot => (
                          <option key={bot.id} value={bot.id}>
                            {bot.name} {bot.strategy && `(${bot.strategy})`}
                            {bot.symbol && ` - ${bot.symbol}`}
                          </option>
                        ))}
                      </select>
                      {loadingBots && (
                        <div className="absolute right-3 top-1/2 -translate-y-1/2">
                          <div className="w-4 h-4 border-2 border-primary border-t-transparent rounded-full animate-spin"></div>
                        </div>
                      )}
                    </div>
                    {selectedBot && availableBots.find(b => b.id === selectedBot) && (
                      <div className="text-sm text-muted-foreground p-2 bg-muted/20 rounded">
                        <strong>Descrição:</strong> {availableBots.find(b => b.id === selectedBot)?.description || 'Robô de trading automatizado'}
                      </div>
                    )}
                    
                    <div className="flex gap-2">
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={loadAvailableBots}
                        disabled={loadingBots}
                      >
                        🔄 Atualizar Lista
                      </Button>
                      {availableBots.length === 0 && !loadingBots && (
                        <div className="text-sm text-yellow-600 flex items-center gap-1">
                          <AlertTriangle className="w-4 h-4" />
                          Nenhum robô encontrado
                        </div>
                      )}
                    </div>
                  </div>
                </div>
                
                <Button 
                  onClick={createTradingSession}
                  disabled={loading || !credentialsValid}
                  className="w-full"
                  variant="premium"
                >
                  <Play className="w-4 h-4 mr-2" />
                  Iniciar Sessão de Trading
                </Button>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        <TabsContent value="monitor" className="space-y-6">
          {/* Sessões Ativas */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {sessions.filter(s => s.is_active).map(session => (
              <Card key={session.id} className="glass-card">
                <CardHeader className="pb-3">
                  <CardTitle className="flex items-center justify-between text-lg">
                    {session.symbol}
                    <Badge variant={session.total_pnl >= 0 ? "success" : "destructive"}>
                      {formatPercent(((session.current_balance - session.initial_balance) / session.initial_balance) * 100)}
                    </Badge>
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="grid grid-cols-2 gap-2 text-sm">
                    <div>
                      <span className="text-muted-foreground">Saldo Atual:</span>
                      <div className="font-semibold">{formatCurrency(session.current_balance)}</div>
                    </div>
                    <div>
                      <span className="text-muted-foreground">P&L Total:</span>
                      <div className={`font-semibold flex items-center gap-1 ${
                        session.total_pnl >= 0 
                          ? 'text-emerald-600' 
                          : 'text-red-600'
                      }`}>
                        {session.total_pnl >= 0 
                          ? <ArrowUp className="w-4 h-4 text-emerald-500" />
                          : <ArrowDown className="w-4 h-4 text-red-500" />
                        }
                        {formatCurrency(session.total_pnl)}
                      </div>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Trades:</span>
                      <div className="font-semibold">{session.total_trades}</div>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Win Rate:</span>
                      <div className="font-semibold">
                        {session.total_trades > 0 ? Math.round((session.profitable_trades / session.total_trades) * 100) : 0}%
                      </div>
                    </div>
                  </div>
                  
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => {
                        setSelectedSession(session);
                        connectWebSocket(session.id);
                      }}
                    >
                      <Eye className="w-4 h-4 mr-1" />
                      Ver Detalhes
                    </Button>
                    <Button
                      size="sm"
                      variant="destructive"
                      onClick={() => stopTradingSession(session.id)}
                    >
                      <Square className="w-4 h-4 mr-1" />
                      Parar
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>

          {sessions.filter(s => s.is_active).length === 0 && (
            <Card className="glass-card">
              <CardContent className="text-center py-12">
                <Activity className="w-12 h-12 mx-auto mb-4 text-muted-foreground" />
                <h3 className="text-lg font-semibold mb-2">Nenhuma sessão ativa</h3>
                <p className="text-muted-foreground mb-4">
                  Configure suas credenciais e inicie uma nova sessão de trading
                </p>
                <Button onClick={() => setActiveTab('setup')}>
                  Configurar Trading
                </Button>
              </CardContent>
            </Card>
          )}

          {/* Trades em Tempo Real */}
          {trades.length > 0 && (
            <Card className="glass-card">
              <CardHeader>
                <CardTitle>Trades Recentes</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {trades.slice(0, 10).map(trade => (
                    <div key={trade.id} className="flex items-center justify-between p-3 bg-muted/20 rounded-lg">
                      <div className="flex items-center gap-3">
                        <Badge variant={trade.side === 'BUY' ? 'success' : 'destructive'}>
                          {trade.side}
                        </Badge>
                        <div>
                          <div className="font-semibold">{trade.symbol}</div>
                          <div className="text-sm text-muted-foreground">
                            {new Date(trade.created_at).toLocaleTimeString()}
                          </div>
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="font-semibold">
                          {formatCurrency(trade.executed_price || trade.price)}
                        </div>
                        <div className="text-sm text-muted-foreground">
                          Qty: {trade.executed_quantity || trade.quantity}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        <TabsContent value="console" className="space-y-6">
          {/* Console de Logs de Execução */}
          <Card className="glass-card">
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2">
                <Terminal className="w-5 h-5" />
                Console de Execução
                {isWebSocketConnected && (
                  <div className="flex items-center gap-2 text-sm text-emerald-600 ml-auto">
                    <div className="w-2 h-2 bg-emerald-500 rounded-full animate-pulse"></div>
                    <span>Dados Ao Vivo</span>
                  </div>
                )}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="bg-gray-950 rounded-lg p-4 h-96 overflow-y-auto font-mono text-sm border border-gray-800">
                {executionLogs.length === 0 ? (
                  <div className="text-gray-500 text-center py-8">
                    <Terminal className="w-8 h-8 mx-auto mb-2 opacity-50" />
                    <p>Aguardando logs de execução...</p>
                    <p className="text-xs mt-1">Os logs aparecerão aqui quando uma sessão estiver ativa</p>
                  </div>
                ) : (
                  <div className="space-y-1">
                    {executionLogs.map((log, index) => (
                      <div 
                        key={index} 
                        className={`text-gray-300 leading-relaxed ${
                          log.includes('🟢') ? 'text-emerald-400' :
                          log.includes('🔴') ? 'text-red-400' :
                          log.includes('📊') ? 'text-blue-400' :
                          log.includes('🎯') ? 'text-yellow-400' :
                          log.includes('🔍') ? 'text-purple-400' :
                          'text-gray-300'
                        }`}
                      >
                        {log}
                      </div>
                    ))}
                  </div>
                )}
              </div>
              
              {/* Controles do Console */}
              <div className="flex items-center justify-between mt-4 pt-4 border-t border-gray-800">
                <div className="text-sm text-gray-500">
                  {executionLogs.length > 0 && (
                    <span>{executionLogs.length} entradas registradas</span>
                  )}
                </div>
                <Button 
                  variant="outline" 
                  size="sm"
                  onClick={() => setExecutionLogs([])}
                  disabled={executionLogs.length === 0}
                >
                  Limpar Console
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* Estatísticas de Performance em Tempo Real */}
          {selectedSession && isWebSocketConnected && (
            <Card className="glass-card">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Activity className="w-5 h-5" />
                  Performance em Tempo Real
                  <div className="w-2 h-2 bg-emerald-500 rounded-full animate-pulse ml-2"></div>
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div className="text-center p-4 bg-muted/10 rounded-lg border">
                    <div className="text-2xl font-bold gradient-text">
                      {formatCurrency(selectedSession.current_balance)}
                    </div>
                    <div className="text-sm text-muted-foreground">Saldo Atual</div>
                  </div>
                  
                  <div className="text-center p-4 bg-muted/10 rounded-lg border">
                    <div className={`text-2xl font-bold flex items-center justify-center gap-1 ${
                      selectedSession.total_pnl >= 0 
                        ? 'text-emerald-600' 
                        : 'text-red-600'
                    }`}>
                      {selectedSession.total_pnl >= 0 
                        ? <ArrowUp className="w-6 h-6 text-emerald-500" />
                        : <ArrowDown className="w-6 h-6 text-red-500" />
                      }
                      {formatCurrency(selectedSession.total_pnl)}
                    </div>
                    <div className="text-sm text-muted-foreground">P&L Total</div>
                  </div>
                  
                  <div className="text-center p-4 bg-muted/10 rounded-lg border">
                    <div className="text-2xl font-bold text-blue-600">
                      {selectedSession.total_trades}
                    </div>
                    <div className="text-sm text-muted-foreground">Total de Trades</div>
                  </div>
                  
                  <div className="text-center p-4 bg-muted/10 rounded-lg border">
                    <div className="text-2xl font-bold text-purple-600">
                      {selectedSession.total_trades > 0 
                        ? Math.round((selectedSession.profitable_trades / selectedSession.total_trades) * 100) 
                        : 0}%
                    </div>
                    <div className="text-sm text-muted-foreground">Taxa de Sucesso</div>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        <TabsContent value="history">
          <Card className="glass-card">
            <CardHeader>
              <CardTitle>Histórico de Trading</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-center py-8">
                <TrendingUp className="w-12 h-12 mx-auto mb-4 text-muted-foreground" />
                <p className="text-muted-foreground">
                  Histórico detalhado de trading será implementado aqui
                </p>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default BinanceTrading;