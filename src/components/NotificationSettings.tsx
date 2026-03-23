/**
 * NotificationSettings - Componente de configurações de notificações
 */
import React, { useState, useEffect } from 'react';
import { Bell, Mail, Smartphone, MessageCircle, Volume2, Clock, Bot, TrendingUp, FileText, Info, Send, CheckCircle } from 'lucide-react';
import { notificationsApi, NotificationPreference } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import { useToast } from '@/hooks/use-toast';
import { Skeleton } from '@/components/ui/skeleton';

export const NotificationSettings: React.FC = () => {
  const [preferences, setPreferences] = useState<NotificationPreference | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [pushSupported, setPushSupported] = useState(false);
  const [pushPermission, setPushPermission] = useState<NotificationPermission>('default');
  const { toast } = useToast();

  // Check push notification support
  useEffect(() => {
    if ('Notification' in window && 'serviceWorker' in navigator) {
      setPushSupported(true);
      setPushPermission(Notification.permission);
    }
  }, []);

  // Fetch preferences
  useEffect(() => {
    fetchPreferences();
  }, []);

  const fetchPreferences = async () => {
    try {
      setLoading(true);
      const data = await notificationsApi.getPreferences();
      setPreferences(data);
    } catch (error: any) {
      toast({
        title: 'Erro ao carregar preferências',
        description: error.message,
        variant: 'destructive',
      });
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    if (!preferences) return;

    try {
      setSaving(true);
      const updated = await notificationsApi.updatePreferences(preferences);
      setPreferences(updated);
      toast({
        title: 'Preferências salvas!',
        description: 'Suas configurações de notificação foram atualizadas.',
      });
    } catch (error: any) {
      toast({
        title: 'Erro ao salvar',
        description: error.message,
        variant: 'destructive',
      });
    } finally {
      setSaving(false);
    }
  };

  const handleToggle = (key: keyof NotificationPreference) => {
    if (!preferences) return;
    setPreferences({
      ...preferences,
      [key]: !preferences[key],
    });
  };

  const handleChange = (key: keyof NotificationPreference, value: any) => {
    if (!preferences) return;
    setPreferences({
      ...preferences,
      [key]: value,
    });
  };

  const requestPushPermission = async () => {
    try {
      const permission = await Notification.requestPermission();
      setPushPermission(permission);

      if (permission === 'granted') {
        // Fetch VAPID public key from backend
        const { public_key } = await notificationsApi.getVapidPublicKey();
        if (!public_key) {
          throw new Error('Push notifications not configured on server');
        }

        // Register service worker and subscribe
        const registration = await navigator.serviceWorker.register('/sw.js');
        const subscription = await registration.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: public_key,
        });

        await notificationsApi.registerPushSubscription(subscription.toJSON());
        
        toast({
          title: 'Push ativado!',
          description: 'Você receberá notificações push.',
        });
        
        handleChange('push_enabled', true);
      } else {
        toast({
          title: 'Permissão negada',
          description: 'Notificações push foram bloqueadas.',
          variant: 'destructive',
        });
      }
    } catch (error: any) {
      console.error('Push permission error:', error);
      toast({
        title: 'Erro ao ativar push',
        description: error.message,
        variant: 'destructive',
      });
    }
  };

  const sendTestNotification = async () => {
    try {
      await notificationsApi.sendTestNotification();
      toast({
        title: 'Notificação enviada!',
        description: 'Verifique suas notificações.',
      });
    } catch (error: any) {
      toast({
        title: 'Erro ao enviar teste',
        description: error.message,
        variant: 'destructive',
      });
    }
  };

  if (loading) {
    return (
      <Card>
        <CardHeader>
          <Skeleton className="h-6 w-48" />
          <Skeleton className="h-4 w-96 mt-2" />
        </CardHeader>
        <CardContent className="space-y-6">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="space-y-2">
              <Skeleton className="h-4 w-32" />
              <Skeleton className="h-10 w-full" />
            </div>
          ))}
        </CardContent>
      </Card>
    );
  }

  if (!preferences) {
    return (
      <Card>
        <CardContent className="py-8 text-center">
          <p className="text-muted-foreground">Erro ao carregar preferências</p>
          <Button onClick={fetchPreferences} className="mt-4">
            Tentar novamente
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {/* Canais de Notificação */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Bell className="h-5 w-5" />
            Canais de Notificação
          </CardTitle>
          <CardDescription>
            Configure como deseja receber suas notificações.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Push Notifications */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-blue-100 dark:bg-blue-900 rounded-lg">
                <Bell className="h-5 w-5 text-blue-600 dark:text-blue-400" />
              </div>
              <div className="space-y-0.5">
                <Label className="text-base">Push no Navegador</Label>
                <p className="text-sm text-muted-foreground">
                  Receba notificações em tempo real no navegador
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              {pushSupported && pushPermission !== 'granted' ? (
                <Button variant="outline" size="sm" onClick={requestPushPermission}>
                  Ativar
                </Button>
              ) : (
                <Switch
                  checked={preferences.push_enabled}
                  onCheckedChange={() => handleToggle('push_enabled')}
                  disabled={!pushSupported || pushPermission !== 'granted'}
                />
              )}
            </div>
          </div>

          <Separator />

          {/* Email */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-green-100 dark:bg-green-900 rounded-lg">
                  <Mail className="h-5 w-5 text-green-600 dark:text-green-400" />
                </div>
                <div className="space-y-0.5">
                  <Label className="text-base">Email</Label>
                  <p className="text-sm text-muted-foreground">
                    Receba notificações por email
                  </p>
                </div>
              </div>
              <Switch
                checked={preferences.email_enabled}
                onCheckedChange={() => handleToggle('email_enabled')}
              />
            </div>
            
            {preferences.email_enabled && (
              <div className="ml-12">
                <Label htmlFor="email_address">Endereço de Email</Label>
                <Input
                  id="email_address"
                  type="email"
                  placeholder="seu@email.com"
                  value={preferences.email_address || ''}
                  onChange={(e) => handleChange('email_address', e.target.value)}
                  className="mt-1"
                />
              </div>
            )}
          </div>

          <Separator />

          {/* WhatsApp */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-emerald-100 dark:bg-emerald-900 rounded-lg">
                  <MessageCircle className="h-5 w-5 text-emerald-600 dark:text-emerald-400" />
                </div>
                <div className="space-y-0.5">
                  <Label className="text-base">WhatsApp</Label>
                  <p className="text-sm text-muted-foreground">
                    Receba notificações via WhatsApp
                  </p>
                </div>
              </div>
              <Switch
                checked={preferences.whatsapp_enabled}
                onCheckedChange={() => handleToggle('whatsapp_enabled')}
              />
            </div>
            
            {preferences.whatsapp_enabled && (
              <div className="ml-12">
                <Label htmlFor="whatsapp_number">Número do WhatsApp</Label>
                <Input
                  id="whatsapp_number"
                  type="tel"
                  placeholder="+55 11 99999-9999"
                  value={preferences.whatsapp_number || ''}
                  onChange={(e) => handleChange('whatsapp_number', e.target.value)}
                  className="mt-1"
                />
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Tipos de Notificação */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Volume2 className="h-5 w-5" />
            Tipos de Notificação
          </CardTitle>
          <CardDescription>
            Escolha quais tipos de eventos devem gerar notificações.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Price Alerts */}
          <div className="flex items-center justify-between py-2">
            <div className="flex items-center gap-3">
              <TrendingUp className="h-5 w-5 text-yellow-500" />
              <div className="space-y-0.5">
                <Label>Alertas de Preço</Label>
                <p className="text-sm text-muted-foreground">
                  Quando um preço atingir seu alerta configurado
                </p>
              </div>
            </div>
            <Switch
              checked={preferences.price_alerts_enabled}
              onCheckedChange={() => handleToggle('price_alerts_enabled')}
            />
          </div>

          <Separator />

          {/* Bot Trades */}
          <div className="flex items-center justify-between py-2">
            <div className="flex items-center gap-3">
              <Bot className="h-5 w-5 text-blue-500" />
              <div className="space-y-0.5">
                <Label>Trades dos Robôs</Label>
                <p className="text-sm text-muted-foreground">
                  Quando um robô executar uma operação
                </p>
              </div>
            </div>
            <Switch
              checked={preferences.bot_trades_enabled}
              onCheckedChange={() => handleToggle('bot_trades_enabled')}
            />
          </div>

          {/* Bot Status */}
          <div className="flex items-center justify-between py-2">
            <div className="flex items-center gap-3">
              <Bot className="h-5 w-5 text-purple-500" />
              <div className="space-y-0.5">
                <Label>Status dos Robôs</Label>
                <p className="text-sm text-muted-foreground">
                  Início, parada ou erros dos robôs
                </p>
              </div>
            </div>
            <Switch
              checked={preferences.bot_status_enabled}
              onCheckedChange={() => handleToggle('bot_status_enabled')}
            />
          </div>

          <Separator />

          {/* Reports */}
          <div className="flex items-center justify-between py-2">
            <div className="flex items-center gap-3">
              <FileText className="h-5 w-5 text-green-500" />
              <div className="space-y-0.5">
                <Label>Relatórios</Label>
                <p className="text-sm text-muted-foreground">
                  Quando um relatório estiver pronto
                </p>
              </div>
            </div>
            <Switch
              checked={preferences.reports_enabled}
              onCheckedChange={() => handleToggle('reports_enabled')}
            />
          </div>

          {/* Daily Summary */}
          <div className="flex items-center justify-between py-2">
            <div className="flex items-center gap-3">
              <FileText className="h-5 w-5 text-orange-500" />
              <div className="space-y-0.5">
                <Label>Resumo Diário</Label>
                <p className="text-sm text-muted-foreground">
                  Receba um resumo das atividades do dia
                </p>
              </div>
            </div>
            <Switch
              checked={preferences.daily_summary_enabled}
              onCheckedChange={() => handleToggle('daily_summary_enabled')}
            />
          </div>

          {/* Weekly Summary */}
          <div className="flex items-center justify-between py-2">
            <div className="flex items-center gap-3">
              <FileText className="h-5 w-5 text-indigo-500" />
              <div className="space-y-0.5">
                <Label>Resumo Semanal</Label>
                <p className="text-sm text-muted-foreground">
                  Receba um resumo semanal de performance
                </p>
              </div>
            </div>
            <Switch
              checked={preferences.weekly_summary_enabled}
              onCheckedChange={() => handleToggle('weekly_summary_enabled')}
            />
          </div>

          <Separator />

          {/* System Updates */}
          <div className="flex items-center justify-between py-2">
            <div className="flex items-center gap-3">
              <Info className="h-5 w-5 text-cyan-500" />
              <div className="space-y-0.5">
                <Label>Atualizações do Sistema</Label>
                <p className="text-sm text-muted-foreground">
                  Novas funcionalidades e manutenções
                </p>
              </div>
            </div>
            <Switch
              checked={preferences.system_updates_enabled}
              onCheckedChange={() => handleToggle('system_updates_enabled')}
            />
          </div>
        </CardContent>
      </Card>

      {/* Horário de Silêncio */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Clock className="h-5 w-5" />
            Horário de Silêncio
          </CardTitle>
          <CardDescription>
            Configure um período em que notificações push/email não serão enviadas.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label>Ativar horário de silêncio</Label>
              <p className="text-sm text-muted-foreground">
                Notificações serão silenciadas durante este período
              </p>
            </div>
            <Switch
              checked={preferences.quiet_hours_enabled}
              onCheckedChange={() => handleToggle('quiet_hours_enabled')}
            />
          </div>

          {preferences.quiet_hours_enabled && (
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label htmlFor="quiet_start">Início</Label>
                <Input
                  id="quiet_start"
                  type="time"
                  value={preferences.quiet_hours_start}
                  onChange={(e) => handleChange('quiet_hours_start', e.target.value)}
                  className="mt-1"
                />
              </div>
              <div>
                <Label htmlFor="quiet_end">Fim</Label>
                <Input
                  id="quiet_end"
                  type="time"
                  value={preferences.quiet_hours_end}
                  onChange={(e) => handleChange('quiet_hours_end', e.target.value)}
                  className="mt-1"
                />
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Ações */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex flex-col sm:flex-row gap-3 justify-between">
            <Button variant="outline" onClick={sendTestNotification}>
              <Send className="h-4 w-4 mr-2" />
              Enviar Notificação de Teste
            </Button>
            
            <Button onClick={handleSave} disabled={saving}>
              {saving ? (
                <>
                  <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2" />
                  Salvando...
                </>
              ) : (
                <>
                  <CheckCircle className="h-4 w-4 mr-2" />
                  Salvar Preferências
                </>
              )}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default NotificationSettings;
