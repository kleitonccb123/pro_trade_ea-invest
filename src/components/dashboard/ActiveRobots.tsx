import { useState } from 'react';
import { Bot, PlayCircle, PauseCircle, ChevronRight, Settings2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useNavigate } from 'react-router-dom';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';

interface ActiveRobot {
  id: string;
  name: string;
  pair: string;
  status: 'active' | 'paused';
  profit: number;
  trades: number;
  winRate?: number;
  avgProfit?: number;
  lastTrade?: string;
}

const activeRobots: ActiveRobot[] = [
  { id: '1', name: 'Scalper Pro', pair: 'BTC/USDT', status: 'active', profit: 8.5, trades: 156, winRate: 72.3, avgProfit: 45.20, lastTrade: '5 min atrás' },
  { id: '2', name: 'Grid Bot', pair: 'ETH/USDT', status: 'active', profit: 5.2, trades: 89, winRate: 68.5, avgProfit: 32.80, lastTrade: '12 min atrás' },
  { id: '3', name: 'Trend Follower', pair: 'SOL/USDT', status: 'paused', profit: 12.3, trades: 45, winRate: 78.2, avgProfit: 89.50, lastTrade: '2h atrás' },
];

export function ActiveRobots() {
  const navigate = useNavigate();
  const [selectedRobot, setSelectedRobot] = useState<ActiveRobot | null>(null);

  return (
    <div className="glass-card p-4 lg:p-6 h-full">
      <div className="flex items-center justify-between mb-4 lg:mb-6">
        <h3 className="text-base lg:text-lg font-semibold text-foreground">Robôs Ativos</h3>
        <button 
          className="text-sm text-primary hover:underline"
          onClick={() => navigate('/robots')}
        >
          Gerenciar
        </button>
      </div>
      
      <div className="space-y-3 lg:space-y-4">
        {activeRobots.map((robot) => (
          <div
            key={robot.id}
            onClick={() => setSelectedRobot(robot)}
            className="flex items-center justify-between p-3 lg:p-4 bg-muted/30 rounded-xl border border-border/50 hover:border-primary/30 transition-all cursor-pointer group"
          >
            <div className="flex items-center gap-3 lg:gap-4">
              <div className="w-9 h-9 lg:w-10 lg:h-10 rounded-lg bg-primary/10 flex items-center justify-center">
                <Bot className="w-4 h-4 lg:w-5 lg:h-5 text-primary" />
              </div>
              <div>
                <p className="font-medium text-sm lg:text-base text-foreground">{robot.name}</p>
                <p className="text-xs lg:text-sm text-muted-foreground">{robot.pair}</p>
              </div>
            </div>
            
            <div className="flex items-center gap-3 lg:gap-6">
              <div className="text-right">
                <p className={cn(
                  "font-mono font-medium text-sm lg:text-base",
                  robot.profit >= 0 ? "text-success" : "text-destructive"
                )}>
                  {robot.profit >= 0 ? '+' : ''}{robot.profit}%
                </p>
                <p className="text-xs text-muted-foreground">{robot.trades} trades</p>
              </div>
              
              <div className="flex items-center gap-2">
                <div className={cn(
                  "flex items-center gap-1",
                  robot.status === 'active' ? "text-success" : "text-warning"
                )}>
                  {robot.status === 'active' ? (
                    <PlayCircle className="w-4 h-4 lg:w-5 lg:h-5" />
                  ) : (
                    <PauseCircle className="w-4 h-4 lg:w-5 lg:h-5" />
                  )}
                </div>
                <ChevronRight className="w-4 h-4 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Robot Detail Modal */}
      <Dialog open={selectedRobot !== null} onOpenChange={(open) => !open && setSelectedRobot(null)}>
        <DialogContent className="max-w-md bg-card border-border">
          {selectedRobot && (
            <>
              <DialogHeader>
                <div className="flex items-center gap-3">
                  <div className="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center">
                    <Bot className="w-6 h-6 text-primary" />
                  </div>
                  <div>
                    <DialogTitle className="flex items-center gap-2">
                      {selectedRobot.name}
                      <div className={cn(
                        "flex items-center gap-1 text-xs",
                        selectedRobot.status === 'active' ? "text-success" : "text-warning"
                      )}>
                        {selectedRobot.status === 'active' ? (
                          <>
                            <PlayCircle className="w-3 h-3" />
                            Ativo
                          </>
                        ) : (
                          <>
                            <PauseCircle className="w-3 h-3" />
                            Pausado
                          </>
                        )}
                      </div>
                    </DialogTitle>
                    <DialogDescription>{selectedRobot.pair}</DialogDescription>
                  </div>
                </div>
              </DialogHeader>

              <div className="grid grid-cols-2 gap-3 mt-4">
                <div className="glass-card p-3 text-center">
                  <p className="text-xs text-muted-foreground">Lucro Total</p>
                  <p className={cn(
                    "text-xl font-bold",
                    selectedRobot.profit >= 0 ? "text-success" : "text-destructive"
                  )}>
                    {selectedRobot.profit >= 0 ? '+' : ''}{selectedRobot.profit}%
                  </p>
                </div>
                <div className="glass-card p-3 text-center">
                  <p className="text-xs text-muted-foreground">Taxa de Acerto</p>
                  <p className="text-xl font-bold text-foreground">{selectedRobot.winRate}%</p>
                </div>
                <div className="glass-card p-3 text-center">
                  <p className="text-xs text-muted-foreground">Total de Trades</p>
                  <p className="text-xl font-bold text-foreground">{selectedRobot.trades}</p>
                </div>
                <div className="glass-card p-3 text-center">
                  <p className="text-xs text-muted-foreground">Lucro Médio</p>
                  <p className="text-xl font-bold text-foreground">${selectedRobot.avgProfit}</p>
                </div>
              </div>

              <div className="p-3 bg-muted/30 rounded-xl mt-2">
                <p className="text-xs text-muted-foreground">Última Operação</p>
                <p className="text-sm text-foreground">{selectedRobot.lastTrade}</p>
              </div>

              <div className="flex gap-2 mt-4">
                <Button 
                  variant="outline" 
                  className="flex-1 border-border"
                  onClick={() => {
                    setSelectedRobot(null);
                    navigate('/robots');
                  }}
                >
                  <Settings2 className="w-4 h-4 mr-2" />
                  Configurar
                </Button>
                <Button 
                  className={cn(
                    "flex-1",
                    selectedRobot.status === 'active' 
                      ? "bg-warning text-warning-foreground hover:bg-warning/90" 
                      : "bg-success text-success-foreground hover:bg-success/90"
                  )}
                >
                  {selectedRobot.status === 'active' ? (
                    <>
                      <PauseCircle className="w-4 h-4 mr-2" />
                      Pausar
                    </>
                  ) : (
                    <>
                      <PlayCircle className="w-4 h-4 mr-2" />
                      Ativar
                    </>
                  )}
                </Button>
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
