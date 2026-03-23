import { ArrowUpRight, ArrowDownRight, Clock, Bot, FileText, X } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';

interface Operation {
  id: string;
  pair: string;
  type: 'buy' | 'sell';
  amount: number;
  price: number;
  entryPrice: number;
  exitPrice: number;
  profit: number;
  date: string;
  duration: string;
  robot: string;
  fees: number;
  notes?: string;
}

interface OperationDetailModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  operation?: Operation;
}

export function OperationDetailModal({ open, onOpenChange, operation }: OperationDetailModalProps) {
  if (!operation) return null;

  const isProfit = operation.profit >= 0;
  const profitPercent = (operation.profit / (operation.amount * operation.entryPrice)) * 100;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md bg-card border-border">
        {/* Header */}
        <DialogHeader>
          <div className="flex items-center gap-4">
            <div className={cn(
              "w-12 h-12 rounded-xl flex items-center justify-center",
              operation.type === 'buy' ? "bg-success/20" : "bg-destructive/20"
            )}>
              {operation.type === 'buy' ? (
                <ArrowUpRight className="w-6 h-6 text-success" />
              ) : (
                <ArrowDownRight className="w-6 h-6 text-destructive" />
              )}
            </div>
            <div>
              <DialogTitle className="text-xl">{operation.pair}</DialogTitle>
              <DialogDescription className={cn(
                "font-medium",
                operation.type === 'buy' ? "text-success" : "text-destructive"
              )}>
                {operation.type === 'buy' ? 'Compra' : 'Venda'}
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>

        {/* Profit/Loss */}
        <div className={cn(
          "p-4 rounded-xl",
          isProfit ? "bg-success/10 border border-success/30" : "bg-destructive/10 border border-destructive/30"
        )}>
          <p className="text-sm text-muted-foreground mb-1">Resultado</p>
          <div className="flex items-baseline gap-2">
            <span className={cn(
              "text-2xl font-mono font-bold",
              isProfit ? "text-success" : "text-destructive"
            )}>
              {isProfit ? '+' : ''}${Math.abs(operation.profit).toFixed(2)}
            </span>
            <span className={cn(
              "text-sm font-mono",
              isProfit ? "text-success" : "text-destructive"
            )}>
              ({isProfit ? '+' : ''}{profitPercent.toFixed(2)}%)
            </span>
          </div>
        </div>

        {/* Details */}
        <div className="space-y-3">
          <div className="flex justify-between items-center py-2 border-b border-border/50">
            <span className="text-sm text-muted-foreground">Quantidade</span>
            <span className="font-mono text-foreground">{operation.amount}</span>
          </div>
          <div className="flex justify-between items-center py-2 border-b border-border/50">
            <span className="text-sm text-muted-foreground">Preço de Entrada</span>
            <span className="font-mono text-foreground">${operation.entryPrice.toLocaleString()}</span>
          </div>
          <div className="flex justify-between items-center py-2 border-b border-border/50">
            <span className="text-sm text-muted-foreground">Preço de Saída</span>
            <span className="font-mono text-foreground">${operation.exitPrice.toLocaleString()}</span>
          </div>
          <div className="flex justify-between items-center py-2 border-b border-border/50">
            <span className="text-sm text-muted-foreground">Taxas</span>
            <span className="font-mono text-foreground">${operation.fees.toFixed(4)}</span>
          </div>
          <div className="flex justify-between items-center py-2 border-b border-border/50">
            <span className="text-sm text-muted-foreground flex items-center gap-2">
              <Bot className="w-4 h-4" />
              Robô
            </span>
            <span className="text-foreground">{operation.robot}</span>
          </div>
          <div className="flex justify-between items-center py-2 border-b border-border/50">
            <span className="text-sm text-muted-foreground flex items-center gap-2">
              <Clock className="w-4 h-4" />
              Duração
            </span>
            <span className="text-foreground">{operation.duration}</span>
          </div>
          <div className="flex justify-between items-center py-2">
            <span className="text-sm text-muted-foreground">Data</span>
            <span className="text-foreground">{operation.date}</span>
          </div>
        </div>

        {/* Notes */}
        {operation.notes && (
          <div className="p-3 bg-muted/30 rounded-xl">
            <div className="flex items-center gap-2 mb-2 text-sm text-muted-foreground">
              <FileText className="w-4 h-4" />
              Observações
            </div>
            <p className="text-sm text-foreground">{operation.notes}</p>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
