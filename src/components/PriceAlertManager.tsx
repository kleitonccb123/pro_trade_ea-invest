/**
 * PriceAlertManager - Componente para gerenciar alertas de preço
 */
import React, { useState, useEffect } from 'react';
import { Bell, Plus, Trash2, Edit, Check, X, TrendingUp, TrendingDown, Activity } from 'lucide-react';
import { notificationsApi, PriceAlert, PriceAlertCreate } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Badge } from '@/components/ui/badge';
import { useToast } from '@/hooks/use-toast';
import { cn } from '@/lib/utils';

const POPULAR_SYMBOLS = [
  'BTCUSDT',
  'ETHUSDT',
  'BNBUSDT',
  'SOLUSDT',
  'XRPUSDT',
  'ADAUSDT',
  'DOGEUSDT',
  'MATICUSDT',
  'DOTUSDT',
  'AVAXUSDT',
];

const CONDITION_OPTIONS = [
  { value: 'above', label: 'Acima de', icon: TrendingUp },
  { value: 'below', label: 'Abaixo de', icon: TrendingDown },
  { value: 'change_percent', label: 'Variação %', icon: Activity },
];

interface PriceAlertFormData {
  symbol: string;
  condition: 'above' | 'below' | 'crosses_up' | 'crosses_down' | 'change_percent';
  target_price: string;
  percent_change: string;
  note: string;
  repeat: boolean;
}

const initialFormData: PriceAlertFormData = {
  symbol: 'BTCUSDT',
  condition: 'above',
  target_price: '',
  percent_change: '',
  note: '',
  repeat: false,
};

export const PriceAlertManager: React.FC = () => {
  const [alerts, setAlerts] = useState<PriceAlert[]>([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingAlert, setEditingAlert] = useState<PriceAlert | null>(null);
  const [formData, setFormData] = useState<PriceAlertFormData>(initialFormData);
  const [submitting, setSubmitting] = useState(false);
  const { toast } = useToast();

  // Fetch alerts
  useEffect(() => {
    fetchAlerts();
  }, []);

  const fetchAlerts = async () => {
    try {
      setLoading(true);
      const data = await notificationsApi.getPriceAlerts(false); // Include inactive
      setAlerts(data);
    } catch (error: any) {
      toast({
        title: 'Erro ao carregar alertas',
        description: error.message,
        variant: 'destructive',
      });
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);

    try {
      const alertData: PriceAlertCreate = {
        symbol: formData.symbol,
        condition: formData.condition,
        target_price: parseFloat(formData.target_price),
        percent_change: formData.condition === 'change_percent' ? parseFloat(formData.percent_change) : undefined,
        note: formData.note || undefined,
        repeat: formData.repeat,
      };

      if (editingAlert) {
        await notificationsApi.updatePriceAlert(editingAlert.id, alertData);
        toast({
          title: 'Alerta atualizado!',
          description: `Alerta para ${alertData.symbol} atualizado com sucesso.`,
        });
      } else {
        await notificationsApi.createPriceAlert(alertData);
        toast({
          title: 'Alerta criado!',
          description: `Você será notificado quando ${alertData.symbol} ${getConditionText(alertData.condition)} $${alertData.target_price.toLocaleString()}.`,
        });
      }

      setDialogOpen(false);
      setEditingAlert(null);
      setFormData(initialFormData);
      fetchAlerts();
    } catch (error: any) {
      toast({
        title: 'Erro ao salvar alerta',
        description: error.response?.data?.detail || error.message,
        variant: 'destructive',
      });
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (alertId: number) => {
    try {
      await notificationsApi.deletePriceAlert(alertId);
      setAlerts((prev) => prev.filter((a) => a.id !== alertId));
      toast({
        title: 'Alerta excluído',
        description: 'O alerta de preço foi removido.',
      });
    } catch (error: any) {
      toast({
        title: 'Erro ao excluir',
        description: error.message,
        variant: 'destructive',
      });
    }
  };

  const handleToggleActive = async (alert: PriceAlert) => {
    try {
      await notificationsApi.updatePriceAlert(alert.id, { is_active: !alert.is_active });
      setAlerts((prev) =>
        prev.map((a) =>
          a.id === alert.id ? { ...a, is_active: !a.is_active } : a
        )
      );
    } catch (error: any) {
      toast({
        title: 'Erro ao atualizar',
        description: error.message,
        variant: 'destructive',
      });
    }
  };

  const openEditDialog = (alert: PriceAlert) => {
    setEditingAlert(alert);
    setFormData({
      symbol: alert.symbol,
      condition: alert.condition,
      target_price: alert.target_price.toString(),
      percent_change: alert.percent_change?.toString() || '',
      note: alert.note || '',
      repeat: alert.repeat,
    });
    setDialogOpen(true);
  };

  const openCreateDialog = () => {
    setEditingAlert(null);
    setFormData(initialFormData);
    setDialogOpen(true);
  };

  const getConditionText = (condition: string) => {
    switch (condition) {
      case 'above': return 'atingir ou ultrapassar';
      case 'below': return 'cair para';
      case 'change_percent': return 'variar';
      default: return '';
    }
  };

  const getConditionIcon = (condition: string) => {
    switch (condition) {
      case 'above': return <TrendingUp className="h-4 w-4 text-green-500" />;
      case 'below': return <TrendingDown className="h-4 w-4 text-red-500" />;
      case 'change_percent': return <Activity className="h-4 w-4 text-yellow-500" />;
      default: return <Bell className="h-4 w-4" />;
    }
  };

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-4">
        <div>
          <CardTitle className="flex items-center gap-2">
            <Bell className="h-5 w-5" />
            Alertas de Preço
          </CardTitle>
          <CardDescription>
            Configure alertas para ser notificado quando criptomoedas atingirem determinados preços.
          </CardDescription>
        </div>
        
        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogTrigger asChild>
            <Button onClick={openCreateDialog}>
              <Plus className="h-4 w-4 mr-2" />
              Novo Alerta
            </Button>
          </DialogTrigger>
          
          <DialogContent className="sm:max-w-[425px]">
            <form onSubmit={handleSubmit}>
              <DialogHeader>
                <DialogTitle>
                  {editingAlert ? 'Editar Alerta' : 'Criar Alerta de Preço'}
                </DialogTitle>
                <DialogDescription>
                  Configure um alerta para ser notificado sobre mudanças de preço.
                </DialogDescription>
              </DialogHeader>
              
              <div className="grid gap-4 py-4">
                {/* Symbol */}
                <div className="grid gap-2">
                  <Label htmlFor="symbol">Símbolo</Label>
                  <Select
                    value={formData.symbol}
                    onValueChange={(value) => setFormData((prev) => ({ ...prev, symbol: value }))}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Selecione um par" />
                    </SelectTrigger>
                    <SelectContent>
                      {POPULAR_SYMBOLS.map((symbol) => (
                        <SelectItem key={symbol} value={symbol}>
                          {symbol}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                
                {/* Condition */}
                <div className="grid gap-2">
                  <Label htmlFor="condition">Condição</Label>
                  <Select
                    value={formData.condition}
                    onValueChange={(value) => setFormData((prev) => ({ ...prev, condition: value as any }))}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {CONDITION_OPTIONS.map((opt) => (
                        <SelectItem key={opt.value} value={opt.value}>
                          <span className="flex items-center gap-2">
                            <opt.icon className="h-4 w-4" />
                            {opt.label}
                          </span>
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                
                {/* Target Price */}
                {formData.condition !== 'change_percent' && (
                  <div className="grid gap-2">
                    <Label htmlFor="target_price">Preço Alvo (USD)</Label>
                    <Input
                      id="target_price"
                      type="number"
                      step="0.01"
                      placeholder="0.00"
                      value={formData.target_price}
                      onChange={(e) => setFormData((prev) => ({ ...prev, target_price: e.target.value }))}
                      required
                    />
                  </div>
                )}
                
                {/* Percent Change */}
                {formData.condition === 'change_percent' && (
                  <div className="grid gap-2">
                    <Label htmlFor="percent_change">Variação (%)</Label>
                    <Input
                      id="percent_change"
                      type="number"
                      step="0.1"
                      placeholder="5.0"
                      value={formData.percent_change}
                      onChange={(e) => setFormData((prev) => ({ ...prev, percent_change: e.target.value }))}
                      required
                    />
                  </div>
                )}
                
                {/* Note */}
                <div className="grid gap-2">
                  <Label htmlFor="note">Nota (opcional)</Label>
                  <Input
                    id="note"
                    placeholder="Lembrete pessoal..."
                    value={formData.note}
                    onChange={(e) => setFormData((prev) => ({ ...prev, note: e.target.value }))}
                  />
                </div>
                
                {/* Repeat */}
                <div className="flex items-center justify-between">
                  <div className="space-y-0.5">
                    <Label htmlFor="repeat">Repetir alerta</Label>
                    <p className="text-xs text-muted-foreground">
                      Alertar novamente após ser acionado
                    </p>
                  </div>
                  <Switch
                    id="repeat"
                    checked={formData.repeat}
                    onCheckedChange={(checked) => setFormData((prev) => ({ ...prev, repeat: checked }))}
                  />
                </div>
              </div>
              
              <DialogFooter>
                <Button type="button" variant="outline" onClick={() => setDialogOpen(false)}>
                  Cancelar
                </Button>
                <Button type="submit" disabled={submitting}>
                  {submitting ? 'Salvando...' : editingAlert ? 'Atualizar' : 'Criar Alerta'}
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      </CardHeader>
      
      <CardContent>
        {loading ? (
          <div className="flex items-center justify-center h-32">
            <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary" />
          </div>
        ) : alerts.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-32 text-muted-foreground">
            <Bell className="h-8 w-8 mb-2 opacity-50" />
            <p className="text-sm">Nenhum alerta configurado</p>
            <Button variant="link" onClick={openCreateDialog} className="mt-2">
              Criar seu primeiro alerta
            </Button>
          </div>
        ) : (
          <div className="space-y-2">
            {alerts.map((alert) => (
              <div
                key={alert.id}
                className={cn(
                  'flex items-center justify-between p-3 border rounded-lg',
                  !alert.is_active && 'opacity-50 bg-muted/50'
                )}
              >
                <div className="flex items-center gap-3">
                  {getConditionIcon(alert.condition)}
                  
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-medium">{alert.symbol}</span>
                      <Badge variant={alert.is_active ? 'default' : 'secondary'} className="text-xs">
                        {alert.condition === 'above' && `≥ $${alert.target_price.toLocaleString()}`}
                        {alert.condition === 'below' && `≤ $${alert.target_price.toLocaleString()}`}
                        {alert.condition === 'change_percent' && `±${alert.percent_change}%`}
                      </Badge>
                      {alert.is_triggered && (
                        <Badge variant="outline" className="text-xs text-green-500 border-green-500">
                          <Check className="h-3 w-3 mr-1" />
                          Acionado
                        </Badge>
                      )}
                      {alert.repeat && (
                        <Badge variant="outline" className="text-xs">
                          Repetir
                        </Badge>
                      )}
                    </div>
                    {alert.note && (
                      <p className="text-xs text-muted-foreground mt-0.5">{alert.note}</p>
                    )}
                  </div>
                </div>
                
                <div className="flex items-center gap-2">
                  <Switch
                    checked={alert.is_active}
                    onCheckedChange={() => handleToggleActive(alert)}
                    aria-label="Ativar/Desativar alerta"
                  />
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => openEditDialog(alert)}
                    aria-label="Editar alerta"
                  >
                    <Edit className="h-4 w-4" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="text-destructive hover:text-destructive"
                    onClick={() => handleDelete(alert.id)}
                    aria-label="Excluir alerta"
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default PriceAlertManager;
