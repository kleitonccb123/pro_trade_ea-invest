import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { 
  Settings,
  TrendingUp,
  Shield,
  DollarSign,
  Zap,
  Eye,
  EyeOff,
  Activity,
  BarChart3,
  AlertTriangle,
  CheckCircle,
  Play,
  Pause,
  Square
} from 'lucide-react';
import { Robot, TrendGridSettings } from '@/types/robot';

interface TrendGridDetailsProps {
  robot: Robot;
  onToggle: () => void;
  onConfigure: () => void;
}

export function TrendGridDetails({ robot, onToggle, onConfigure }: TrendGridDetailsProps) {
  const [showAdvanced, setShowAdvanced] = useState(false);
  
  if (!robot.advancedSettings) {
    return null;
  }

  const settings = robot.advancedSettings;
  const isActive = robot.status === 'active';
  const isBlocked = settings.dailyBlocked || settings.emergencyBlocked;

  const getStatusColor = () => {
    if (isBlocked) return 'destructive';
    if (isActive) return 'success';
    return 'secondary';
  };

  const getStatusIcon = () => {
    if (isBlocked) return <AlertTriangle className="w-4 h-4" />;
    if (isActive) return <Activity className="w-4 h-4 animate-pulse" />;
    return <Pause className="w-4 h-4" />;
  };

  const getStatusText = () => {
    if (settings.dailyBlocked) return 'Bloqueado - Meta/Limite Diário';
    if (settings.emergencyBlocked) return 'Bloqueado - Emergência';
    if (isActive) return 'Ativo - Trading';
    return robot.status === 'paused' ? 'Pausado' : 'Parado';
  };

  return (
    <div className="space-y-4">
      {/* Header com Status */}
      <Card className="glass-card border-primary/20">
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-primary to-accent flex items-center justify-center">
                <TrendingUp className="w-6 h-6 text-white" />
              </div>
              <div>
                <CardTitle className="text-xl gradient-text">{robot.name}</CardTitle>
                <p className="text-sm text-muted-foreground">{robot.strategy} • {robot.pair} • {robot.timeframe}</p>
              </div>
            </div>
            <div className="text-right">
              <Badge variant={getStatusColor()} className="mb-2">
                {getStatusIcon()}
                <span className="ml-1">{getStatusText()}</span>
              </Badge>
              <div className="text-sm text-muted-foreground">
                {robot.trades} trades • {robot.winRate}% win rate
              </div>
            </div>
          </div>
        </CardHeader>
        
        <CardContent className="space-y-4">
          {/* Métricas Principais */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="text-center p-3 bg-muted/10 rounded-lg">
              <div className={`text-2xl font-bold ${robot.profit >= 0 ? 'text-emerald-500' : 'text-red-500'}`}>
                {robot.profit > 0 ? '+' : ''}{robot.profit}%
              </div>
              <div className="text-xs text-muted-foreground">Lucro Total</div>
            </div>
            <div className="text-center p-3 bg-muted/10 rounded-lg">
              <div className="text-2xl font-bold text-primary">${robot.amount}</div>
              <div className="text-xs text-muted-foreground">Capital</div>
            </div>
            <div className="text-center p-3 bg-muted/10 rounded-lg">
              <div className="text-2xl font-bold text-blue-500">{robot.maxDrawdown}%</div>
              <div className="text-xs text-muted-foreground">Max DD</div>
            </div>
            <div className="text-center p-3 bg-muted/10 rounded-lg">
              <div className="text-2xl font-bold text-purple-500">{robot.sharpeRatio}</div>
              <div className="text-xs text-muted-foreground">Sharpe</div>
            </div>
          </div>

          {/* Grid de Proteções - Apenas quando houver proteções reais ativas */}
          {settings.protectionsOpened > 0 && (
            <div className="flex items-center gap-2 p-3 bg-warning/10 border border-warning/20 rounded-lg">
              <Shield className="w-5 h-5 text-warning" />
              <span className="text-sm">
                <strong>{settings.protectionsOpened}</strong> proteções ativas de <strong>{settings.maxProtections}</strong>
              </span>
            </div>
          )}

          {/* Alertas de Bloqueio */}
          {isBlocked && (
            <div className="flex items-center gap-2 p-3 bg-destructive/10 border border-destructive/20 rounded-lg">
              <AlertTriangle className="w-5 h-5 text-destructive" />
              <span className="text-sm text-destructive">
                {settings.dailyBlocked && 'Meta diária atingida ou limite de perda excedido'}
                {settings.emergencyBlocked && 'Drawdown de emergência acionado'}
              </span>
            </div>
          )}

          {/* Controles */}
          <div className="flex gap-2">
            <Button
              variant={isActive ? "destructive" : "premium"}
              size="sm"
              onClick={onToggle}
              disabled={isBlocked}
            >
              {isActive ? (
                <>
                  <Square className="w-4 h-4 mr-1" />
                  Parar
                </>
              ) : (
                <>
                  <Play className="w-4 h-4 mr-1" />
                  Iniciar
                </>
              )}
            </Button>
            <Button variant="outline" size="sm" onClick={onConfigure}>
              <Settings className="w-4 h-4 mr-1" />
              Configurar
            </Button>
            <Button 
              variant="ghost" 
              size="sm" 
              onClick={() => setShowAdvanced(!showAdvanced)}
            >
              {showAdvanced ? <EyeOff className="w-4 h-4 mr-1" /> : <Eye className="w-4 h-4 mr-1" />}
              Detalhes
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Configurações Avançadas */}
      {showAdvanced && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {/* Filtros de Entrada */}
          <Card className="glass-card">
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-lg">
                <BarChart3 className="w-5 h-5 text-primary" />
                Filtros de Entrada
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm">Média Móvel (EMA {settings.movingAveragePeriod})</span>
                <Badge variant={settings.enableMovingAverage ? "success" : "secondary"}>
                  {settings.enableMovingAverage ? <CheckCircle className="w-3 h-3" /> : '●'}
                </Badge>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm">RSI ({settings.rsiOversold}-{settings.rsiOverbought})</span>
                <Badge variant={settings.useRSI ? "success" : "secondary"}>
                  {settings.useRSI ? <CheckCircle className="w-3 h-3" /> : '●'}
                </Badge>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm">Força Candle ({settings.minimumCandleBody}%)</span>
                <Badge variant={settings.useCandleStrength ? "success" : "secondary"}>
                  {settings.useCandleStrength ? <CheckCircle className="w-3 h-3" /> : '●'}
                </Badge>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm">Volume (min {settings.minimumVolumeRatio}x)</span>
                <Badge variant={settings.useVolume ? "success" : "secondary"}>
                  {settings.useVolume ? <CheckCircle className="w-3 h-3" /> : '●'}
                </Badge>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm">Range Adaptativo</span>
                <Badge variant={settings.useAdaptiveRange ? "success" : "secondary"}>
                  {settings.useAdaptiveRange ? <CheckCircle className="w-3 h-3" /> : '●'}
                </Badge>
              </div>
            </CardContent>
          </Card>

          {/* Sistema de Proteções */}
          <Card className="glass-card">
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-lg">
                <Shield className="w-5 h-5 text-blue-500" />
                Sistema de Proteções
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm">Grid de Proteções</span>
                <Badge variant={settings.enableProtections ? "success" : "secondary"}>
                  {settings.enableProtections ? 'ATIVO' : 'INATIVO'}
                </Badge>
              </div>
              <div className="text-sm space-y-1">
                <div>Máximo: <strong>{settings.maxProtections}</strong> níveis</div>
                <div>Ativas: <strong className="text-warning">{settings.protectionsOpened}</strong></div>
                <div>Intervalo: <strong>{settings.timeBetweenProtections}s</strong></div>
              </div>
              <div className="text-xs text-muted-foreground">
                Primeiros níveis: {settings.protectionDistances.slice(0, 5).join(', ')}...
              </div>
            </CardContent>
          </Card>

          {/* Gestão Financeira */}
          <Card className="glass-card">
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-lg">
                <DollarSign className="w-5 h-5 text-emerald-500" />
                Gestão Financeira
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-sm">Meta Diária</span>
                  <span className="text-sm font-medium text-emerald-500">
                    ${settings.dailyGoal}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm">Limite Perda</span>
                  <span className="text-sm font-medium text-red-500">
                    ${settings.dailyLossLimit}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm">Drawdown Emergência</span>
                  <span className="text-sm font-medium text-warning">
                    {settings.emergencyDrawdown}%
                  </span>
                </div>
              </div>
              <div className="pt-2 border-t border-muted/20">
                <div className="flex items-center justify-between text-xs">
                  <span>SL/TP por operação</span>
                  <span className="font-medium">
                    ${settings.stopLossUSD} / ${settings.takeProfitUSD}
                  </span>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Scalper */}
          <Card className="glass-card">
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-lg">
                <Zap className="w-5 h-5 text-yellow-500" />
                Scalper
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm">Sistema Scalper</span>
                <Badge variant={settings.enableScalper ? "success" : "secondary"}>
                  {settings.enableScalper ? 'ATIVO' : 'INATIVO'}
                </Badge>
              </div>
              {settings.enableScalper && (
                <div className="text-sm space-y-1">
                  <div>Intervalo: <strong>{settings.scalperInterval}s</strong></div>
                  <div className="text-xs text-muted-foreground">
                    Operações rápidas dentro do candle seguinte após candle de força
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Filtros Avançados */}
          <Card className="glass-card">
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-lg">
                <Settings className="w-5 h-5 text-purple-500" />
                Filtros Avançados
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm">Maturidade Candle</span>
                <Badge variant={settings.useCandleMaturity ? "success" : "secondary"}>
                  {settings.useCandleMaturity ? `${settings.maturitySeconds}s` : 'OFF'}
                </Badge>
              </div>
              <div className="text-sm space-y-1">
                <div>Dist. Rompimento: <strong>{settings.breakoutMinDistance}</strong> pontos</div>
                <div className="text-xs text-muted-foreground">
                  Distância mínima após rompimento da EMA
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Indicadores Técnicos */}
          <Card className="glass-card">
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-lg">
                <BarChart3 className="w-5 h-5 text-blue-500" />
                Indicadores
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex flex-wrap gap-1">
                {robot.indicators.map((indicator, index) => (
                  <Badge key={index} variant="outline" className="text-xs">
                    {indicator}
                  </Badge>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}