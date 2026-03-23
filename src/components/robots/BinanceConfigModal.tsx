import React, { useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Rocket, Shield, AlertTriangle, Zap, TrendingUp } from 'lucide-react';
import { cn } from '@/lib/utils';

interface BinanceConfig {
  api_key: string;
  api_secret: string;
  symbol: string;
  testnet: boolean;
}

interface BinanceConfigModalProps {
  robotName: string;
  robotSymbol: string;
  onStart: (config: BinanceConfig) => Promise<void>;
  isStarting?: boolean;
}

const POPULAR_SYMBOLS = [
  { value: 'BTCUSDT', label: 'BTC/USDT', icon: '₿' },
  { value: 'ETHUSDT', label: 'ETH/USDT', icon: 'Ξ' },
  { value: 'ADAUSDT', label: 'ADA/USDT', icon: '₳' },
  { value: 'BNBUSDT', label: 'BNB/USDT', icon: '🟡' },
  { value: 'SOLUSDT', label: 'SOL/USDT', icon: '◎' },
  { value: 'DOTUSDT', label: 'DOT/USDT', icon: '●' },
];

export function BinanceConfigModal({
  robotName,
  robotSymbol,
  onStart,
  isStarting = false
}: BinanceConfigModalProps) {
  const [open, setOpen] = useState(false);
  const [config, setConfig] = useState<BinanceConfig>({
    api_key: '',
    api_secret: '',
    symbol: robotSymbol || 'BTCUSDT',
    testnet: true
  });
  const [mode, setMode] = useState<'simulation' | 'live'>('simulation');
  const [errors, setErrors] = useState<string[]>([]);

  const validateConfig = (): boolean => {
    const newErrors: string[] = [];
    
    if (mode === 'live') {
      if (!config.api_key.trim()) {
        newErrors.push('API Key é obrigatória para trading ao vivo');
      }
      if (!config.api_secret.trim()) {
        newErrors.push('API Secret é obrigatória para trading ao vivo');
      }
      if (config.api_key.length < 10) {
        newErrors.push('API Key parece muito curta');
      }
      if (config.api_secret.length < 10) {
        newErrors.push('API Secret parece muito curta');
      }
    }
    
    if (!config.symbol.trim()) {
      newErrors.push('Símbolo de trading é obrigatório');
    }
    
    setErrors(newErrors);
    return newErrors.length === 0;
  };

  const handleStart = async () => {
    if (!validateConfig()) return;
    
    try {
      if (mode === 'simulation') {
        // Start in simulation mode (no Binance config needed)
        await onStart(null as any);
      } else {
        // Start in live mode with Binance config
        await onStart(config);
      }
      setOpen(false);
      setConfig({
        api_key: '',
        api_secret: '',
        symbol: robotSymbol || 'BTCUSDT',
        testnet: true
      });
      setErrors([]);
    } catch (error) {
      console.error('Failed to start robot:', error);
      setErrors(['Falha ao iniciar robô. Verifique suas credenciais.']);
    }
  };

  const selectedSymbol = POPULAR_SYMBOLS.find(s => s.value === config.symbol);

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="premium" className="gap-2">
          <Rocket className="h-4 w-4" />
          Iniciar Robô
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-primary/10">
              <TrendingUp className="h-6 w-6 text-primary" />
            </div>
            <div>
              <div className="gradient-text text-xl">Configurar {robotName}</div>
              <div className="text-sm text-muted-foreground font-normal">
                Configure o modo de operação do seu robô
              </div>
            </div>
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-6">
          {/* Mode Selection */}
          <div className="grid grid-cols-2 gap-4">
            <div 
              className={cn(
                "glass-card p-4 cursor-pointer transition-all duration-200 border-2",
                mode === 'simulation' 
                  ? "border-primary/50 bg-primary/5" 
                  : "border-transparent hover:border-border/50"
              )}
              onClick={() => setMode('simulation')}
            >
              <div className="flex items-start gap-3">
                <div className={cn(
                  "p-2 rounded-lg",
                  mode === 'simulation' ? "bg-primary/20 text-primary" : "bg-muted text-muted-foreground"
                )}>
                  <Zap className="h-5 w-5" />
                </div>
                <div>
                  <div className="font-semibold">Simulação</div>
                  <div className="text-xs text-muted-foreground">
                    Teste estratégias sem risco
                  </div>
                </div>
              </div>
            </div>
            
            <div 
              className={cn(
                "glass-card p-4 cursor-pointer transition-all duration-200 border-2",
                mode === 'live' 
                  ? "border-primary/50 bg-primary/5" 
                  : "border-transparent hover:border-border/50"
              )}
              onClick={() => setMode('live')}
            >
              <div className="flex items-start gap-3">
                <div className={cn(
                  "p-2 rounded-lg",
                  mode === 'live' ? "bg-primary/20 text-primary" : "bg-muted text-muted-foreground"
                )}>
                  <Shield className="h-5 w-5" />
                </div>
                <div>
                  <div className="font-semibold">Trading Ao Vivo</div>
                  <div className="text-xs text-muted-foreground">
                    Operações reais na Binance
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Symbol Selection */}
          <div className="space-y-2">
            <Label htmlFor="symbol" className="text-sm font-semibold">Símbolo de Trading</Label>
            <Select value={config.symbol} onValueChange={(value) => setConfig({...config, symbol: value})}>
              <SelectTrigger className="glass-card">
                <SelectValue>
                  <div className="flex items-center gap-2">
                    <span className="text-lg">{selectedSymbol?.icon}</span>
                    <span>{selectedSymbol?.label || config.symbol}</span>
                  </div>
                </SelectValue>
              </SelectTrigger>
              <SelectContent>
                {POPULAR_SYMBOLS.map((symbol) => (
                  <SelectItem key={symbol.value} value={symbol.value}>
                    <div className="flex items-center gap-2">
                      <span className="text-lg">{symbol.icon}</span>
                      <span>{symbol.label}</span>
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Binance Configuration (only for live mode) */}
          {mode === 'live' && (
            <div className="space-y-4 p-4 rounded-xl bg-accent/5 border border-accent/20">
              <div className="flex items-center gap-2">
                <Shield className="h-5 w-5 text-accent" />
                <span className="font-semibold text-accent">Configuração Binance</span>
              </div>
              
              <div className="space-y-3">
                <div>
                  <Label htmlFor="api_key" className="text-sm">API Key *</Label>
                  <Input
                    id="api_key"
                    type="password"
                    placeholder="Sua Binance API Key"
                    value={config.api_key}
                    onChange={(e) => setConfig({...config, api_key: e.target.value})}
                    className="mt-1"
                  />
                </div>
                
                <div>
                  <Label htmlFor="api_secret" className="text-sm">API Secret *</Label>
                  <Input
                    id="api_secret"
                    type="password"
                    placeholder="Sua Binance API Secret"
                    value={config.api_secret}
                    onChange={(e) => setConfig({...config, api_secret: e.target.value})}
                    className="mt-1"
                  />
                </div>
                
                <div className="flex items-center justify-between">
                  <div>
                    <Label className="text-sm font-medium">Testnet (Recomendado)</Label>
                    <p className="text-xs text-muted-foreground">
                      Use ambiente de teste para operações seguras
                    </p>
                  </div>
                  <Switch
                    checked={config.testnet}
                    onCheckedChange={(checked) => setConfig({...config, testnet: checked})}
                  />
                </div>
              </div>
              
              <Alert>
                <AlertTriangle className="h-4 w-4" />
                <AlertDescription className="text-xs">
                  <strong>Importante:</strong> Certifique-se de que suas chaves API têm apenas permissões de trading.
                  Nunca compartilhe suas credenciais.
                </AlertDescription>
              </Alert>
            </div>
          )}

          {/* Errors */}
          {errors.length > 0 && (
            <Alert variant="destructive">
              <AlertTriangle className="h-4 w-4" />
              <AlertDescription>
                <ul className="list-disc list-inside space-y-1">
                  {errors.map((error, index) => (
                    <li key={index} className="text-xs">{error}</li>
                  ))}
                </ul>
              </AlertDescription>
            </Alert>
          )}

          {/* Action Buttons */}
          <div className="flex items-center gap-3 pt-4">
            <Button
              onClick={handleStart}
              disabled={isStarting}
              className="flex-1 gap-2"
              variant={mode === 'live' ? "premium" : "default"}
            >
              {isStarting ? (
                <div className="animate-spin rounded-full h-4 w-4 border-2 border-current border-t-transparent" />
              ) : (
                <Rocket className="h-4 w-4" />
              )}
              {mode === 'live' ? 'Iniciar Trading Ao Vivo' : 'Iniciar Simulação'}
            </Button>
            
            <div className="flex items-center gap-2">
              <Badge variant={mode === 'live' ? 'destructive' : 'secondary'} className="text-xs">
                {mode === 'live' 
                  ? (config.testnet ? 'Testnet' : '⚠️ Mainnet') 
                  : 'Simulação'
                }
              </Badge>
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}