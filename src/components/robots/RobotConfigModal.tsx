import { useState } from 'react';
import { X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';

interface RobotConfigModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSave?: (config: any) => void;
  marketType?: 'crypto';
  robot?: {
    id: string;
    name: string;
    pair: string;
    amount: number;
    stopLoss: number;
    takeProfit: number;
  } | null;
}

const cryptoPairs = [
  'BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT', 
  'ADA/USDT', 'DOGE/USDT', 'DOT/USDT', 'LINK/USDT', 'AVAX/USDT'
];

export function RobotConfigModal({ isOpen, onClose, onSave, marketType = 'crypto', robot }: RobotConfigModalProps) {
  const tradingPairs = cryptoPairs;
  const [pair, setPair] = useState(robot?.pair || 'BTC/USDT');
  const [amount, setAmount] = useState(robot?.amount?.toString() || '1000');
  const [stopLoss, setStopLoss] = useState(robot?.stopLoss?.toString() || '2');
  const [takeProfit, setTakeProfit] = useState(robot?.takeProfit?.toString() || '5');
  const [trailingStop, setTrailingStop] = useState(false);
  const [compoundProfits, setCompoundProfits] = useState(true);

  if (!isOpen) return null;

  const handleSave = () => {
    const config = {
      pair,
      amount: parseFloat(amount),
      stopLoss: parseFloat(stopLoss),
      takeProfit: parseFloat(takeProfit),
      trailingStop,
      compoundProfits,
      marketType,
    };
    
    if (onSave) {
      onSave(config);
    } else {
      onClose();
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div 
        className="absolute inset-0 bg-background/80 backdrop-blur-sm"
        onClick={onClose}
      />
      
      {/* Modal */}
      <div className="relative z-10 w-full max-w-lg glass-card p-6 m-4 animate-scale-in">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-xl font-bold text-foreground">
              {robot ? 'Configurar Robô' : 'Novo Robô'}
            </h2>
            <p className="text-sm text-muted-foreground">
              {robot?.name || 'Configure os parâmetros do robô'}
            </p>
          </div>
          <button 
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-muted transition-colors"
          >
            <X className="w-5 h-5 text-muted-foreground" />
          </button>
        </div>

        {/* Form */}
        <div className="space-y-5">
          {/* Trading pair */}
          <div className="space-y-2">
            <Label>Par de negociação</Label>
            <Select value={pair} onValueChange={setPair}>
              <SelectTrigger className="bg-muted/50 border-border h-12">
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="bg-popover border-border">
                {tradingPairs.map((p) => (
                  <SelectItem key={p} value={p}>{p}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Amount per operation */}
          <div className="space-y-2">
            <Label>Valor por operação (USDT)</Label>
            <Input
              type="number"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              className="bg-muted/50 border-border h-12"
              placeholder="100"
            />
          </div>

          {/* Stop Loss and Take Profit */}
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>Stop Loss (%)</Label>
              <Input
                type="number"
                value={stopLoss}
                onChange={(e) => setStopLoss(e.target.value)}
                className="bg-muted/50 border-border h-12"
                placeholder="2"
              />
            </div>
            <div className="space-y-2">
              <Label>Take Profit (%)</Label>
              <Input
                type="number"
                value={takeProfit}
                onChange={(e) => setTakeProfit(e.target.value)}
                className="bg-muted/50 border-border h-12"
                placeholder="5"
              />
            </div>
          </div>

          {/* Switches */}
          <div className="space-y-4 pt-2">
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium text-foreground">Trailing Stop</p>
                <p className="text-sm text-muted-foreground">Ajustar stop automaticamente</p>
              </div>
              <Switch 
                checked={trailingStop} 
                onCheckedChange={setTrailingStop}
              />
            </div>
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium text-foreground">Reinvestir Lucros</p>
                <p className="text-sm text-muted-foreground">Compor ganhos automaticamente</p>
              </div>
              <Switch 
                checked={compoundProfits} 
                onCheckedChange={setCompoundProfits}
              />
            </div>
          </div>
        </div>

        {/* Actions */}
        <div className="flex gap-3 mt-8">
          <Button 
            variant="outline" 
            onClick={onClose}
            className="flex-1 h-12 border-border"
          >
            Cancelar
          </Button>
          <Button 
            onClick={handleSave}
            className="flex-1 h-12 bg-gradient-primary text-primary-foreground hover:opacity-90"
          >
            Salvar Configurações
          </Button>
        </div>
      </div>
    </div>
  );
}
