import { useState, useEffect } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import { User, Shield, Link2, Bell, Save, Eye, EyeOff, AlertTriangle, CheckCircle2, Sparkles, Globe, Zap, Lock, Mail, Smartphone, Loader, Download, Trash2, FileText, KeyRound, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { cn } from '@/lib/utils';
import { toast } from 'sonner';
import { NotificationSettings } from '@/components/NotificationSettings';
import { PriceAlertManager } from '@/components/PriceAlertManager';
import { useLanguage } from '@/hooks/use-language';
import { userService } from '@/services/userService';
import { exchangeService, ExchangeCredentialInfo } from '@/services/exchangeService';
import { AvatarSelectorModal } from '@/components/AvatarSelectorModal';
import { LanguageSelector } from '@/components/LanguageSelector';
import { apiCall } from '@/services/apiClient';
import TwoFactorSetup from '@/components/auth/TwoFactorSetup';
import { twoFactorApi } from '@/lib/api';

export default function Settings() {
  const [searchParams] = useSearchParams();
  const tabParam = searchParams.get('tab');
  const [activeTab, setActiveTab] = useState(tabParam || 'profile');
  const { language, setLanguage, availableLanguages, t } = useLanguage();
  
  const [showApiKey, setShowApiKey] = useState(false);
  const [showApiSecret, setShowApiSecret] = useState(false);
  const [useSystemLanguage, setUseSystemLanguage] = useState(() => {
    return localStorage.getItem('use-system-language') === 'true';
  });
  
  // Loading state
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [selectedAvatar, setSelectedAvatar] = useState('avatar-1');
  const [openAvatarModal, setOpenAvatarModal] = useState(false);
  const availableAvatars = userService.getAvailableAvatars();
  
  // Update tab when URL param changes
  useEffect(() => {
    if (tabParam && ['profile', 'language', 'security', 'exchange', 'notifications', 'privacy'].includes(tabParam)) {
      setActiveTab(tabParam);
    }
  }, [tabParam]);

  // Monitorar mudanças de idioma
  useEffect(() => {
    const handleLanguageChange = (e: CustomEvent) => {
      console.log('[Settings] Idioma alterado para:', e.detail.language);
      // Force component to re-render by updating state
    };
    
    window.addEventListener('languageChanged', handleLanguageChange as EventListener);
    return () => window.removeEventListener('languageChanged', handleLanguageChange as EventListener);
  }, []);
  
  // Profile state
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [timezone, setTimezone] = useState('America/Sao_Paulo');
  
  // Security state
  const [twoFactor, setTwoFactor] = useState(false);
  const [emailNotifications, setEmailNotifications] = useState(true);
  const [smsAlerts, setSmsAlerts] = useState(false);
  const [show2FASetup, setShow2FASetup] = useState(false);
  const [disabling2FA, setDisabling2FA] = useState(false);
  const [disable2FACode, setDisable2FACode] = useState('');
  const [showDisable2FADialog, setShowDisable2FADialog] = useState(false);
  const [regeneratingCodes, setRegeneratingCodes] = useState(false);
  const [regenCode, setRegenCode] = useState('');
  const [showRegenDialog, setShowRegenDialog] = useState(false);
  const [backupCodesRemaining, setBackupCodesRemaining] = useState<number | null>(null);
  
  // Exchange state
  const [apiKey, setApiKey] = useState('');
  const [apiSecret, setApiSecret] = useState('');
  const [passphrase, setPassphrase] = useState('');
  const [showPassphrase, setShowPassphrase] = useState(false);
  const [testMode, setTestMode] = useState(true);
  const [savingExchange, setSavingExchange] = useState(false);
  const [testingConnection, setTestingConnection] = useState(false);
  const [kucoinInfo, setKucoinInfo] = useState<ExchangeCredentialInfo | null>(null);

  // LGPD state
  const [deletePassword, setDeletePassword] = useState('');
  const [deleteReason, setDeleteReason] = useState('');
  const [deletingAccount, setDeletingAccount] = useState(false);
  const [exportingData, setExportingData] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  // Carregar dados do usuário ao montar o componente
  useEffect(() => {
    const loadUserData = async () => {
      try {
        setLoading(true);
        const [profile, kucoin] = await Promise.all([
          userService.getProfile(),
          exchangeService.getCredential('kucoin'),
        ]);
        if (profile) {
          setName(profile.name || '');
          setEmail(profile.email || '');
          setPhone(profile.phone || '');
          setTimezone(profile.timezone || 'America/Sao_Paulo');
          setSelectedAvatar(profile.avatar || 'avatar-1');
          setTwoFactor(profile.two_factor_enabled || false);
        }
        if (kucoin) {
          setKucoinInfo(kucoin);
          setTestMode(kucoin.sandbox);
        }
      } catch (error) {
        console.error('Erro ao carregar perfil:', error);
        toast.error(t('settings.errorLoadProfile'));
      } finally {
        setLoading(false);
      }
    };
    
    loadUserData();
  }, []);

  // Load 2FA status
  useEffect(() => {
    const load2FAStatus = async () => {
      try {
        const status = await twoFactorApi.getStatus();
        setTwoFactor(status.enabled);
        if (status.enabled) {
          // Use a simple fetch to get backup_codes_remaining from the status endpoint
          setBackupCodesRemaining(null); // will be fetched if needed
        }
      } catch {
        // Not critical
      }
    };
    load2FAStatus();
  }, []);

  const handle2FAToggle = (checked: boolean) => {
    if (checked) {
      setShow2FASetup(true);
    } else {
      setShowDisable2FADialog(true);
    }
  };

  const handle2FASetupComplete = () => {
    setShow2FASetup(false);
    setTwoFactor(true);
    toast.success(t('settings.twoFactorEnabled') || '2FA ativado com sucesso!');
  };

  const handleDisable2FA = async () => {
    if (!disable2FACode || disable2FACode.length !== 6) {
      toast.error('Digite o código de 6 dígitos do autenticador');
      return;
    }
    setDisabling2FA(true);
    try {
      await twoFactorApi.disable(disable2FACode, '');
      setTwoFactor(false);
      setShowDisable2FADialog(false);
      setDisable2FACode('');
      toast.success(t('settings.twoFactorDisabled') || '2FA desativado com sucesso');
    } catch (err: any) {
      toast.error(err?.message || 'Código inválido');
    } finally {
      setDisabling2FA(false);
    }
  };

  const handleRegenerateBackupCodes = async () => {
    if (!regenCode || regenCode.length !== 6) {
      toast.error('Digite o código de 6 dígitos do autenticador');
      return;
    }
    setRegeneratingCodes(true);
    try {
      const result = await twoFactorApi.generateBackupCodes(regenCode);
      setShowRegenDialog(false);
      setRegenCode('');
      // Show new codes in a toast or dialog
      const codesText = result.backup_codes.join('\n');
      toast.success(`Novos backup codes gerados! Copie-os:\n${codesText}`, { duration: 15000 });
    } catch (err: any) {
      toast.error(err?.message || 'Código inválido');
    } finally {
      setRegeneratingCodes(false);
    }
  };

  const handleSaveProfile = async () => {
    try {
      setSaving(true);
      await userService.updateProfile({
        name,
        phone,
        timezone,
        avatar: selectedAvatar,
      });
      toast.success(t('settings.profileUpdated'), {
        description: t('settings.changesSaved'),
        icon: <CheckCircle2 className="w-4 h-4 text-emerald-500" />,
      });
    } catch (error) {
      console.error('Erro ao salvar perfil:', error);
      toast.error(t('settings.errorSaveProfile'));
    } finally {
      setSaving(false);
    }
  };

  const handleSaveExchange = async () => {
    if (!apiKey && !kucoinInfo?.connected) {
      toast.error('Preencha a API Key');
      return;
    }
    // If fields are empty it means user wants to keep existing credentials
    if (!apiKey && !apiSecret && kucoinInfo?.connected) {
      toast.info('Nenhuma alteração — credenciais já salvas.');
      return;
    }
    if (!passphrase) {
      toast.error('KuCoin requer Passphrase');
      return;
    }
    try {
      setSavingExchange(true);
      const result = await exchangeService.saveCredentials({
        exchange: 'kucoin',
        api_key: apiKey,
        api_secret: apiSecret,
        passphrase,
        sandbox: testMode,
      });
      setKucoinInfo(result);
      setApiKey('');
      setApiSecret('');
      setPassphrase('');
      toast.success('Credenciais KuCoin salvas com sucesso!', {
        description: `Conectado · saldo USDT: $${result.balance_usd ?? 0}`,
        icon: <CheckCircle2 className="w-4 h-4 text-emerald-500" />,
      });
    } catch (err: any) {
      const msg = err?.message || 'Erro ao salvar credenciais';
      toast.error(msg.includes('401') ? 'Credenciais inválidas — verifique API Key, Secret e Passphrase.' : msg);
    } finally {
      setSavingExchange(false);
    }
  };

  const handleTestConnection = async () => {
    if (!kucoinInfo?.connected) {
      toast.error('Salve as credenciais primeiro.');
      return;
    }
    try {
      setTestingConnection(true);
      // Re-lista para verificar status atual
      const updated = await exchangeService.getCredential('kucoin');
      if (updated?.connected) {
        toast.success('Conexão OK!', { description: `API Key: ${updated.api_key_masked}` });
      } else {
        toast.error('Conexão falhou.');
      }
    } catch {
      toast.error('Erro ao testar conexão.');
    } finally {
      setTestingConnection(false);
    }
  };

  const handleSave = (section: string) => {
    toast.success(`${section} ${t('settings.saved')}`, {
      description: t('settings.changesApplied'),
      icon: <CheckCircle2 className="w-4 h-4 text-emerald-500" />,
    });
  };

  const handleExportData = async () => {
    try {
      setExportingData(true);
      const response = await apiCall('/api/lgpd/export');
      const data = await response.json();
      if (data.success) {
        const blob = new Blob([JSON.stringify(data.data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `meus-dados-${new Date().toISOString().slice(0, 10)}.json`;
        a.click();
        URL.revokeObjectURL(url);
        toast.success('Dados exportados com sucesso!');
      } else {
        toast.error(data.message || 'Erro ao exportar dados');
      }
    } catch {
      toast.error('Erro ao exportar dados');
    } finally {
      setExportingData(false);
    }
  };

  const handleExportCSV = async () => {
    try {
      const response = await apiCall('/analytics/export/csv');
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `trades-${new Date().toISOString().slice(0, 10)}.csv`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success('Relatório CSV exportado!');
    } catch {
      toast.error('Erro ao exportar CSV');
    }
  };

  const handleExportPDF = async () => {
    try {
      const response = await apiCall('/analytics/export/pdf');
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `performance-${new Date().toISOString().slice(0, 10)}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success('Relatório PDF exportado!');
    } catch {
      toast.error('Erro ao exportar PDF');
    }
  };

  const handleExportFiscalPDF = async () => {
    try {
      const year = new Date().getFullYear();
      const response = await apiCall(`/analytics/export/pdf/fiscal?year=${year}`);
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `fiscal-${year}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success('Relatório fiscal PDF exportado!');
    } catch {
      toast.error('Erro ao exportar relatório fiscal');
    }
  };

  const handleDeleteAccount = async () => {
    if (!deletePassword) {
      toast.error('Digite sua senha para confirmar');
      return;
    }
    try {
      setDeletingAccount(true);
      const response = await apiCall('/api/lgpd/account', {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password: deletePassword, reason: deleteReason }),
      });
      const data = await response.json();
      if (data.success) {
        toast.success(data.message);
        setTimeout(() => { window.location.href = '/login'; }, 3000);
      } else {
        toast.error(data.detail || data.message || 'Erro ao excluir conta');
      }
    } catch {
      toast.error('Erro ao excluir conta');
    } finally {
      setDeletingAccount(false);
      setConfirmDelete(false);
      setDeletePassword('');
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 space-y-6 animate-fade-up">
      {/* Decorative Elements */}
      <div className="fixed top-0 right-0 w-72 h-72 bg-gradient-to-br from-indigo-500/10 to-transparent rounded-full blur-3xl opacity-30 pointer-events-none" />
      <div className="fixed bottom-0 left-0 w-72 h-72 bg-gradient-to-tr from-brand-primary/10 to-transparent rounded-full blur-3xl opacity-30 pointer-events-none" />

      {/* Header Premium */}
      <div className="relative z-10 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 px-4 md:px-8 py-8 md:py-12">
        <div className="space-y-2">
          <h1 className="text-4xl md:text-5xl font-bold bg-gradient-to-r from-indigo-400 via-purple-400 to-pink-400 bg-clip-text text-transparent">
            {t('settings.title')}
          </h1>
          <p className="text-slate-400 text-lg">
            {t('settings.subtitle')}
          </p>
        </div>
        <div className="flex items-center gap-3 px-4 py-3 glass-card rounded-xl border border-indigo-500/30 bg-gradient-to-br from-indigo-900/20 to-indigo-700/10 self-start md:self-end">
          <Zap className="w-5 h-5 text-indigo-400 animate-pulse" />
          <span className="text-sm text-slate-300 font-semibold">{t('settings.proAccount')}</span>
        </div>
      </div>

      {/* Tabs Container */}
      <div className="relative z-10 px-4 md:px-8 space-y-6">
        <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
          {/* Premium Tabs Design */}
          <TabsList className="grid grid-cols-2 md:grid-cols-6 gap-2 bg-gradient-to-br from-slate-800/50 to-slate-900/50 border border-slate-700 p-1.5 rounded-xl backdrop-blur-sm">
            <TabsTrigger 
              value="profile"
              className="data-[state=active]:bg-gradient-to-br data-[state=active]:from-indigo-600 data-[state=active]:to-indigo-700 data-[state=active]:text-white data-[state=active]:shadow-lg data-[state=active]:shadow-indigo-500/50 rounded-lg transition-all hover:text-indigo-400 text-xs md:text-sm font-medium"
            >
              <User className="w-4 h-4 mr-1 md:mr-2" />
              <span className="hidden sm:inline">{t('settings.profile')}</span>
              <span className="sm:hidden">{t('settings.profile')}</span>
            </TabsTrigger>
            <TabsTrigger 
              value="language"
              className="data-[state=active]:bg-brand-primary/20 data-[state=active]:text-brand-primary data-[state=active]:shadow-lg data-[state=active]:shadow-brand-primary/30 rounded-lg transition-all hover:text-brand-primary text-xs md:text-sm font-medium"
            >
              <Globe className="w-4 h-4 mr-1 md:mr-2" />
              <span className="hidden sm:inline">{t('settings.language')}</span>
              <span className="sm:hidden">{t('settings.language')}</span>
            </TabsTrigger>
            <TabsTrigger 
              value="security"
              className="data-[state=active]:bg-gradient-to-br data-[state=active]:from-emerald-600 data-[state=active]:to-emerald-700 data-[state=active]:text-white data-[state=active]:shadow-lg data-[state=active]:shadow-emerald-500/50 rounded-lg transition-all hover:text-emerald-400 text-xs md:text-sm font-medium"
            >
              <Shield className="w-4 h-4 mr-1 md:mr-2" />
              <span className="hidden sm:inline">{t('settings.security')}</span>
              <span className="sm:hidden">{t('settings.security')}</span>
            </TabsTrigger>
            <TabsTrigger 
              value="exchange"
              className="data-[state=active]:bg-gradient-to-br data-[state=active]:from-purple-600 data-[state=active]:to-purple-700 data-[state=active]:text-white data-[state=active]:shadow-lg data-[state=active]:shadow-purple-500/50 rounded-lg transition-all hover:text-purple-400 text-xs md:text-sm font-medium"
            >
              <Link2 className="w-4 h-4 mr-1 md:mr-2" />
              <span className="hidden sm:inline">Exchange</span>
              <span className="sm:hidden">Exch.</span>
            </TabsTrigger>
            <TabsTrigger 
              value="notifications"
              className="data-[state=active]:bg-gradient-to-br data-[state=active]:from-rose-600 data-[state=active]:to-rose-700 data-[state=active]:text-white data-[state=active]:shadow-lg data-[state=active]:shadow-rose-500/50 rounded-lg transition-all hover:text-rose-400 text-xs md:text-sm font-medium"
            >
              <Bell className="w-4 h-4 mr-1 md:mr-2" />
              <span className="hidden sm:inline">{t('settings.notifications')}</span>
              <span className="sm:hidden">{t('settings.notifications')}</span>
            </TabsTrigger>
            <TabsTrigger 
              value="privacy"
              className="data-[state=active]:bg-gradient-to-br data-[state=active]:from-amber-600 data-[state=active]:to-amber-700 data-[state=active]:text-white data-[state=active]:shadow-lg data-[state=active]:shadow-amber-500/50 rounded-lg transition-all hover:text-amber-400 text-xs md:text-sm font-medium"
            >
              <FileText className="w-4 h-4 mr-1 md:mr-2" />
              <span className="hidden sm:inline">Privacidade</span>
              <span className="sm:hidden">LGPD</span>
            </TabsTrigger>
          </TabsList>

        {/* Profile Tab */}
        <TabsContent value="profile" className="space-y-6">
          {loading ? (
            <div className="glass-card p-6 lg:p-8 rounded-xl border border-slate-700 bg-gradient-to-br from-slate-800/50 to-slate-900/50 flex items-center justify-center h-96">
              <Loader className="w-8 h-8 text-indigo-400 animate-spin" />
            </div>
          ) : (
            <div className="glass-card p-6 lg:p-8 rounded-xl border border-slate-700 bg-gradient-to-br from-slate-800/50 to-slate-900/50 hover:border-indigo-500/30 transition-all duration-300 backdrop-blur-sm space-y-8">
              {/* Section Header */}
              <div className="flex items-center gap-4 pb-6 border-b border-slate-700">
                <div className="w-14 h-14 rounded-lg bg-gradient-to-br from-indigo-600 to-indigo-700 flex items-center justify-center shadow-lg shadow-indigo-500/50">
                  <User className="w-7 h-7 text-white" />
                </div>
                <div>
                  <h2 className="text-2xl font-bold text-white">{t('settings.personalInfo')}</h2>
                  <p className="text-sm text-slate-400">{t('settings.personalInfoDesc')}</p>
                </div>
              </div>
              
              {/* Avatar Selection */}
              <div className="space-y-4">
                <h3 className="text-lg font-bold text-white">{t('settings.traderAvatar')}</h3>
                <p className="text-sm text-slate-400">{t('settings.avatarDesc')}</p>
                
                <button
                  onClick={() => setOpenAvatarModal(true)}
                  className="w-full flex items-center justify-center gap-4 p-6 bg-gradient-to-br from-slate-800/50 to-slate-900/50 border border-slate-700 hover:border-indigo-500/50 rounded-xl transition-all duration-300 hover:shadow-lg hover:shadow-indigo-500/20"
                >
                  <span className="text-6xl">{userService.getAvatarById(selectedAvatar)?.emoji}</span>
                  <div className="text-left">
                    <p className="text-sm text-slate-400">{t('settings.selectedAvatar')}</p>
                    <p className="text-2xl font-bold text-white">{userService.getAvatarById(selectedAvatar)?.name}</p>
                  </div>
                  <span className="ml-auto text-indigo-400">{t('settings.clickToChange')}</span>
                </button>
              </div>

              {/* Form Grid */}
              <div className="space-y-6">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div className="space-y-3">
                    <Label htmlFor="name" className="text-base font-semibold text-white">{t('settings.fullName')}</Label>
                    <Input
                      id="name"
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      placeholder={t('settings.namePlaceholder')}
                      className="bg-slate-800/50 border-slate-700 h-12 text-white placeholder:text-slate-500 focus:border-indigo-500 focus:ring-indigo-500/20"
                    />
                  </div>
                  <div className="space-y-3">
                    <Label htmlFor="email" className="text-base font-semibold text-white">{t('settings.emailReadOnly')}</Label>
                    <Input
                      id="email"
                      type="email"
                      value={email}
                      disabled
                      className="bg-slate-800/50 border-slate-700 h-12 text-slate-400 cursor-not-allowed opacity-60"
                    />
                  </div>
                  <div className="space-y-3">
                    <Label htmlFor="phone" className="text-base font-semibold text-white">{t('settings.phone')}</Label>
                    <Input
                      id="phone"
                      type="tel"
                      value={phone}
                      onChange={(e) => setPhone(e.target.value)}
                      placeholder="+55 11 99999-9999"
                      className="bg-slate-800/50 border-slate-700 h-12 text-white placeholder:text-slate-500 focus:border-indigo-500 focus:ring-indigo-500/20"
                    />
                  </div>
                  <div className="space-y-3">
                    <Label htmlFor="timezone" className="text-base font-semibold text-white">{t('settings.timezone')}</Label>
                    <select
                      id="timezone"
                      value={timezone}
                      onChange={(e) => setTimezone(e.target.value)}
                      className="w-full bg-slate-800/50 border border-slate-700 h-12 text-white rounded-lg focus:border-indigo-500 focus:ring-indigo-500/20 px-3"
                    >
                      <option value="America/Sao_Paulo">São Paulo (UTC-3)</option>
                      <option value="America/New_York">Nova York (UTC-4/-5)</option>
                      <option value="Europe/London">Londres (UTC+0/+1)</option>
                      <option value="Asia/Tokyo">Tóquio (UTC+9)</option>
                      <option value="Australia/Sydney">Sydney (UTC+10/+11)</option>
                    </select>
                  </div>
                </div>
              </div>

              <div className="flex justify-end pt-4 border-t border-slate-700">
                <Button 
                  disabled={saving}
                  className="bg-gradient-to-r from-indigo-600 to-indigo-700 hover:from-indigo-500 hover:to-indigo-600 text-white font-semibold shadow-lg shadow-indigo-500/30 px-8 h-12 disabled:opacity-50 disabled:cursor-not-allowed"
                  onClick={handleSaveProfile}
                >
                  {saving ? (
                    <>
                      <Loader className="w-5 h-5 mr-2 animate-spin" />
                      {t('settings.saving')}
                    </>
                  ) : (
                    <>
                      <Save className="w-5 h-5 mr-2" />
                      {t('settings.saveChanges')}
                    </>
                  )}
                </Button>
              </div>
            </div>
          )}
        </TabsContent>

        {/* Language Tab */}
        <TabsContent value="language" className="space-y-6">
          <div className="glass-card p-6 lg:p-8 rounded-xl border border-slate-700 bg-gradient-to-br from-slate-800/50 to-slate-900/50 hover:border-brand-primary/20 transition-all duration-300 backdrop-blur-sm">
            {/* Section Header */}
            <div className="flex items-center gap-4 mb-8 pb-6 border-b border-slate-700">
              <div className="w-14 h-14 rounded-lg bg-brand-primary/15 border border-brand-primary/30 flex items-center justify-center shadow-lg shadow-brand-primary/20">
                <Globe className="w-7 h-7 text-white" />
              </div>
              <div>
                <h2 className="text-2xl font-bold text-white">{t('settings.langAndLocation')}</h2>
                <p className="text-sm text-slate-400">{t('settings.langAndLocationDesc')}</p>
              </div>
            </div>

            <div className="space-y-8">
              {/* System Language Toggle */}
              <div className="p-4 md:p-6 bg-brand-primary/5 rounded-lg border border-brand-primary/20 hover:border-brand-primary/40 transition-all group">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                  <div className="flex-1">
                    <p className="font-bold text-content-primary group-hover:text-brand-primary transition-colors">{t('settings.autoDetectLang')}</p>
                    <p className="text-sm text-slate-400 mt-2">{t('settings.autoDetectDesc')}</p>
                  </div>
                  <Switch 
                    checked={useSystemLanguage}
                    onCheckedChange={(checked) => {
                      setUseSystemLanguage(checked);
                      if (checked) {
                        localStorage.setItem('use-system-language', 'true');
                        localStorage.removeItem('language');
                        toast.success(t('settings.autoDetectEnabled'), {
                          description: t('settings.pageReloading'),
                        });
                        setTimeout(() => window.location.reload(), 500);
                      } else {
                        localStorage.removeItem('use-system-language');
                      }
                    }}
                    className="h-6 w-11"
                  />
                </div>
              </div>

              {/* Language Selection */}
              <div>
                <h3 className="text-lg font-bold text-white mb-6 flex items-center gap-2">
                  <span className="text-2xl">🌐</span>
                  {t('settings.selectLanguage')}
                </h3>
                <LanguageSelector />
              </div>

              {/* Current Language Preview */}
              <div className="p-6 bg-gradient-to-br from-indigo-900/30 to-purple-900/20 rounded-xl border-l-4 border-indigo-500 backdrop-blur-sm">
                <div className="flex items-start gap-4">
                  <div className="w-12 h-12 rounded-lg bg-gradient-to-br from-indigo-600 to-purple-600 flex items-center justify-center flex-shrink-0">
                    <span className="text-2xl">{availableLanguages.find(l => l.code === language)?.flag}</span>
                  </div>
                  <div className="flex-1">
                    <p className="text-xs text-indigo-300 uppercase tracking-wider font-bold mb-1">{t('settings.currentLanguage')}</p>
                    <p className="text-2xl font-bold text-white mb-2">
                      {availableLanguages.find(l => l.code === language)?.name}
                    </p>
                    <p className="text-sm text-slate-300">
                      {t('settings.code')}: <code className="bg-surface-elevated px-3 py-1 rounded text-brand-primary font-mono font-bold ml-1">{language.toUpperCase()}</code>
                    </p>
                  </div>
                </div>
              </div>

              {/* Info Banner */}
              <div className="p-4 bg-brand-primary/5 border border-brand-primary/25 rounded-lg flex items-start gap-3">
                <span className="text-xl mt-1">💡</span>
                <div>
                  <p className="text-sm font-semibold text-brand-primary">{t('settings.instantChange')}</p>
                  <p className="text-xs text-slate-400 mt-1">{t('settings.instantChangeDesc')}</p>
                </div>
              </div>
            </div>
          </div>
        </TabsContent>
        <TabsContent value="security" className="space-y-6">
          <div className="glass-card p-6 lg:p-8 rounded-xl border border-slate-700 bg-gradient-to-br from-slate-800/50 to-slate-900/50 hover:border-emerald-500/30 transition-all duration-300 backdrop-blur-sm">
            {/* Section Header */}
            <div className="flex items-center gap-4 mb-8 pb-6 border-b border-slate-700">
              <div className="w-14 h-14 rounded-lg bg-gradient-to-br from-emerald-600 to-emerald-700 flex items-center justify-center shadow-lg shadow-emerald-500/50">
                <Shield className="w-7 h-7 text-white" />
              </div>
              <div>
                <h2 className="text-2xl font-bold text-white">{t('settings.accountSecurity')}</h2>
                <p className="text-sm text-slate-400">{t('settings.accountSecurityDesc')}</p>
              </div>
            </div>
            
            {/* Security Options */}
            <div className="space-y-3 mb-8">
              {/* Two Factor Auth */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-4 md:p-6 bg-gradient-to-br from-emerald-900/20 to-emerald-700/10 rounded-lg border border-emerald-600/30 hover:border-emerald-500/50 transition-all group">
                <div className="flex-1 flex items-start gap-3">
                  <Lock className="w-5 h-5 text-emerald-400 mt-1 flex-shrink-0" />
                  <div>
                    <p className="font-bold text-white group-hover:text-emerald-200 transition-colors">{t('settings.twoFactor')}</p>
                    <p className="text-sm text-slate-400 mt-1">{t('settings.twoFactorDesc')}</p>
                  </div>
                </div>
                <Switch checked={twoFactor} onCheckedChange={handle2FAToggle} className="h-6 w-11" />
              </div>

              {/* Backup Codes Management (visible when 2FA enabled) */}
              {twoFactor && (
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-4 md:p-6 bg-gradient-to-br from-amber-900/20 to-amber-700/10 rounded-lg border border-amber-600/30 hover:border-amber-500/50 transition-all group">
                  <div className="flex-1 flex items-start gap-3">
                    <KeyRound className="w-5 h-5 text-amber-400 mt-1 flex-shrink-0" />
                    <div>
                      <p className="font-bold text-white group-hover:text-amber-200 transition-colors">{t('settings.backupCodes') || 'Backup Codes'}</p>
                      <p className="text-sm text-slate-400 mt-1">{t('settings.backupCodesDesc') || 'Regenere seus códigos de backup para recuperação de conta'}</p>
                    </div>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setShowRegenDialog(true)}
                    className="border-amber-600/50 text-amber-400 hover:bg-amber-900/30 hover:text-amber-300"
                  >
                    <RefreshCw className="w-4 h-4 mr-2" />
                    {t('settings.regenerateBackupCodes') || 'Regenerar'}
                  </Button>
                </div>
              )}

              {/* Email Notifications */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-4 md:p-6 bg-brand-primary/5 rounded-lg border border-brand-primary/20 hover:border-brand-primary/40 transition-all group">
                <div className="flex-1 flex items-start gap-3">
                  <Mail className="w-5 h-5 text-brand-primary mt-1 flex-shrink-0" />
                  <div>
                    <p className="font-bold text-content-primary group-hover:text-brand-primary transition-colors">{t('settings.emailNotifications')}</p>
                    <p className="text-sm text-slate-400 mt-1">{t('settings.emailNotificationsDesc')}</p>
                  </div>
                </div>
                <Switch checked={emailNotifications} onCheckedChange={setEmailNotifications} className="h-6 w-11" />
              </div>

              {/* SMS Alerts */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-4 md:p-6 bg-gradient-to-br from-indigo-900/20 to-indigo-700/10 rounded-lg border border-indigo-600/30 hover:border-indigo-500/50 transition-all group">
                <div className="flex-1 flex items-start gap-3">
                  <Smartphone className="w-5 h-5 text-indigo-400 mt-1 flex-shrink-0" />
                  <div>
                    <p className="font-bold text-white group-hover:text-indigo-200 transition-colors">{t('settings.smsAlerts')}</p>
                    <p className="text-sm text-slate-400 mt-1">{t('settings.smsAlertsDesc')}</p>
                  </div>
                </div>
                <Switch checked={smsAlerts} onCheckedChange={setSmsAlerts} className="h-6 w-11" />
              </div>
            </div>

            {/* Change Password Section */}
            <div className="mt-8 pt-8 border-t border-slate-700">
              <h3 className="text-xl font-bold text-white mb-6 flex items-center gap-2">
                <Lock className="w-5 h-5 text-rose-400" />
                {t('settings.changePassword')}
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
                <div className="space-y-3">
                  <Label className="text-base font-semibold text-white">{t('settings.currentPassword')}</Label>
                  <Input type="password" className="bg-slate-800/50 border-slate-700 h-12 text-white placeholder:text-slate-500 focus:border-rose-500 focus:ring-rose-500/20" placeholder="••••••••" />
                </div>
                <div className="space-y-3">
                  <Label className="text-base font-semibold text-white">{t('settings.newPassword')}</Label>
                  <Input type="password" className="bg-slate-800/50 border-slate-700 h-12 text-white placeholder:text-slate-500 focus:border-rose-500 focus:ring-rose-500/20" placeholder="••••••••" />
                </div>
              </div>
              <Button className="bg-rose-600 hover:bg-rose-700 text-white font-semibold h-11">
                {t('settings.updatePassword')}
              </Button>
            </div>
          </div>
        </TabsContent>

        {/* Exchange Tab */}
        <TabsContent value="exchange" className="space-y-6">
          <div className="glass-card p-6 lg:p-8 rounded-xl border border-slate-700 bg-gradient-to-br from-slate-800/50 to-slate-900/50 hover:border-purple-500/30 transition-all duration-300 backdrop-blur-sm">
            {/* Section Header */}
            <div className="flex items-center gap-4 mb-8 pb-6 border-b border-slate-700">
              <div className="w-14 h-14 rounded-lg bg-gradient-to-br from-purple-600 to-purple-700 flex items-center justify-center shadow-lg shadow-purple-500/50">
                <Link2 className="w-7 h-7 text-white" />
              </div>
              <div>
                <h2 className="text-2xl font-bold text-white">{t('settings.exchangeConnection')}</h2>
                <p className="text-sm text-slate-400">{t('settings.exchangeConnectionDesc')}</p>
              </div>
            </div>

            {/* Connection Status */}
            {kucoinInfo && (
              <div className={`p-4 rounded-lg mb-6 flex items-center gap-3 border ${
                kucoinInfo.connected
                  ? 'bg-emerald-900/20 border-emerald-500/40 text-emerald-300'
                  : 'bg-rose-900/20 border-rose-500/40 text-rose-300'
              }`}>
                {kucoinInfo.connected
                  ? <CheckCircle2 className="w-5 h-5 flex-shrink-0" />
                  : <AlertTriangle className="w-5 h-5 flex-shrink-0" />}
                <div>
                  <p className="font-semibold">
                    {kucoinInfo.connected ? 'KuCoin conectada' : 'KuCoin desconectada'}
                  </p>
                  {kucoinInfo.connected && (
                    <p className="text-sm opacity-80">
                      API Key: {kucoinInfo.api_key_masked}{kucoinInfo.sandbox ? ' · Sandbox' : ''}
                      {kucoinInfo.balance_usd != null ? ` · USDT: $${kucoinInfo.balance_usd}` : ''}
                    </p>
                  )}
                </div>
              </div>
            )}

            {/* Warning Alert */}
            <div className="p-4 md:p-6 bg-gradient-to-br from-rose-900/30 to-rose-700/10 border-l-4 border-rose-500 rounded-lg mb-8 flex gap-4">
              <AlertTriangle className="w-6 h-6 text-rose-400 flex-shrink-0 mt-0.5" />
              <div>
                <p className="font-bold text-rose-300 mb-2">⚠️ {t('settings.securityImportant')}</p>
                <p className="text-sm text-rose-200/80">
                  {t('settings.securityWarning')}
                </p>
              </div>
            </div>

            {/* API Inputs */}
            <div className="space-y-6 mb-8">
              <div className="space-y-3">
                <Label htmlFor="apiKey" className="text-base font-semibold text-white">
                  API Key {kucoinInfo?.connected && <span className="text-xs text-slate-400 font-normal ml-2">(deixe em branco para manter a atual)</span>}
                </Label>
                <div className="relative">
                  <Input
                    id="apiKey"
                    type={showApiKey ? 'text' : 'password'}
                    value={apiKey}
                    onChange={(e) => setApiKey(e.target.value)}
                    placeholder={kucoinInfo?.connected ? kucoinInfo.api_key_masked : t('settings.apiKeyPlaceholder')}
                    className="bg-slate-800/50 border-slate-700 h-12 text-white placeholder:text-slate-500 focus:border-purple-500 focus:ring-purple-500/20 pr-12"
                  />
                  <button
                    type="button"
                    onClick={() => setShowApiKey(!showApiKey)}
                    className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-400 hover:text-white transition-colors"
                  >
                    {showApiKey ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                  </button>
                </div>
              </div>

              <div className="space-y-3">
                <Label htmlFor="apiSecret" className="text-base font-semibold text-white">API Secret</Label>
                <div className="relative">
                  <Input
                    id="apiSecret"
                    type={showApiSecret ? 'text' : 'password'}
                    value={apiSecret}
                    onChange={(e) => setApiSecret(e.target.value)}
                    placeholder={t('settings.apiSecretPlaceholder')}
                    className="bg-slate-800/50 border-slate-700 h-12 text-white placeholder:text-slate-500 focus:border-purple-500 focus:ring-purple-500/20 pr-12"
                  />
                  <button
                    type="button"
                    onClick={() => setShowApiSecret(!showApiSecret)}
                    className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-400 hover:text-white transition-colors"
                  >
                    {showApiSecret ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                  </button>
                </div>
              </div>

              <div className="space-y-3">
                <Label htmlFor="passphrase" className="text-base font-semibold text-white">
                  Passphrase <span className="text-rose-400">*</span>
                  <span className="text-xs text-slate-400 font-normal ml-2">(obrigatório para KuCoin)</span>
                </Label>
                <div className="relative">
                  <Input
                    id="passphrase"
                    type={showPassphrase ? 'text' : 'password'}
                    value={passphrase}
                    onChange={(e) => setPassphrase(e.target.value)}
                    placeholder="Passphrase da API KuCoin"
                    className="bg-slate-800/50 border-slate-700 h-12 text-white placeholder:text-slate-500 focus:border-purple-500 focus:ring-purple-500/20 pr-12"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassphrase(!showPassphrase)}
                    className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-400 hover:text-white transition-colors"
                  >
                    {showPassphrase ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                  </button>
                </div>
              </div>
            </div>

            {/* Test Mode Toggle */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-4 md:p-6 bg-gradient-to-br from-purple-900/20 to-purple-700/10 rounded-lg border border-purple-600/30 hover:border-purple-500/50 transition-all group mb-8">
              <div className="flex-1">
                <p className="font-bold text-white group-hover:text-purple-200 transition-colors">{t('settings.testMode')}</p>
                <p className="text-sm text-slate-400 mt-1">{t('settings.testModeDesc')}</p>
              </div>
              <Switch checked={testMode} onCheckedChange={setTestMode} className="h-6 w-11" />
            </div>

            {/* Action Buttons */}
            <div className="flex flex-col sm:flex-row gap-3">
              <Button
                className="bg-slate-700 hover:bg-slate-600 text-white font-semibold h-12 flex-1 sm:flex-none disabled:opacity-50"
                onClick={handleTestConnection}
                disabled={testingConnection || !kucoinInfo?.connected}
              >
                {testingConnection ? <Loader className="w-4 h-4 mr-2 animate-spin" /> : null}
                🔗 {t('settings.testConnection')}
              </Button>
              <Button 
                className="bg-gradient-to-r from-purple-600 to-purple-700 hover:from-purple-500 hover:to-purple-600 text-white font-semibold shadow-lg shadow-purple-500/30 h-12 flex-1 sm:flex-none disabled:opacity-50"
                onClick={handleSaveExchange}
                disabled={savingExchange}
              >
                {savingExchange ? <Loader className="w-4 h-4 mr-2 animate-spin" /> : <Save className="w-5 h-5 mr-2" />}
                {savingExchange ? 'Salvando...' : t('settings.saveConfig')}
              </Button>
            </div>
          </div>
        </TabsContent>

        {/* Notifications Tab */}
        <TabsContent value="notifications" className="space-y-6">
          {/* Novo sistema de notificações */}
          <NotificationSettings />
          
          {/* Gerenciador de alertas de preço */}
          <PriceAlertManager />
        </TabsContent>

        {/* Privacy & Data Tab (LGPD) */}
        <TabsContent value="privacy" className="space-y-6">
          <div className="glass-card p-6 lg:p-8 rounded-xl border border-slate-700 bg-gradient-to-br from-slate-800/50 to-slate-900/50 hover:border-amber-500/30 transition-all duration-300 backdrop-blur-sm">
            {/* Section Header */}
            <div className="flex items-center gap-4 mb-8 pb-6 border-b border-slate-700">
              <div className="w-14 h-14 rounded-lg bg-gradient-to-br from-amber-600 to-amber-700 flex items-center justify-center shadow-lg shadow-amber-500/50">
                <FileText className="w-7 h-7 text-white" />
              </div>
              <div>
                <h2 className="text-2xl font-bold text-white">Privacidade & Dados</h2>
                <p className="text-sm text-slate-400">Gerencie seus dados pessoais conforme a LGPD</p>
              </div>
            </div>

            {/* Legal Links */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
              <Link
                to="/privacy-policy"
                className="flex items-center gap-3 p-4 bg-gradient-to-br from-indigo-900/20 to-indigo-700/10 rounded-lg border border-indigo-600/30 hover:border-indigo-500/50 transition-all"
              >
                <Shield className="w-5 h-5 text-indigo-400" />
                <div>
                  <p className="font-bold text-white">Política de Privacidade</p>
                  <p className="text-sm text-slate-400">Como tratamos seus dados</p>
                </div>
              </Link>
              <Link
                to="/terms-of-service"
                className="flex items-center gap-3 p-4 bg-gradient-to-br from-emerald-900/20 to-emerald-700/10 rounded-lg border border-emerald-600/30 hover:border-emerald-500/50 transition-all"
              >
                <FileText className="w-5 h-5 text-emerald-400" />
                <div>
                  <p className="font-bold text-white">Termos de Serviço</p>
                  <p className="text-sm text-slate-400">Regras de uso da plataforma</p>
                </div>
              </Link>
            </div>

            {/* Data Export */}
            <div className="mb-8">
              <h3 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
                <Download className="w-5 h-5 text-amber-400" />
                Exportação de Dados
              </h3>
              <p className="text-sm text-slate-400 mb-4">
                Exporte todos os seus dados pessoais (Art. 18 LGPD — Portabilidade)
              </p>
              <div className="flex flex-col sm:flex-row gap-3">
                <Button
                  onClick={handleExportData}
                  disabled={exportingData}
                  className="bg-amber-600 hover:bg-amber-700 text-white font-semibold h-11"
                >
                  {exportingData ? <Loader className="w-4 h-4 mr-2 animate-spin" /> : <Download className="w-4 h-4 mr-2" />}
                  Exportar Dados (JSON)
                </Button>
                <Button
                  onClick={handleExportCSV}
                  variant="outline"
                  className="border-amber-600/50 text-amber-400 hover:bg-amber-600/10 font-semibold h-11"
                >
                  <Download className="w-4 h-4 mr-2" />
                  Exportar Trades (CSV)
                </Button>
                <Button
                  onClick={handleExportPDF}
                  variant="outline"
                  className="border-cyan-600/50 text-cyan-400 hover:bg-cyan-600/10 font-semibold h-11"
                >
                  <Download className="w-4 h-4 mr-2" />
                  Relatório Performance (PDF)
                </Button>
                <Button
                  onClick={handleExportFiscalPDF}
                  variant="outline"
                  className="border-emerald-600/50 text-emerald-400 hover:bg-emerald-600/10 font-semibold h-11"
                >
                  <Download className="w-4 h-4 mr-2" />
                  Relatório Fiscal (PDF)
                </Button>
              </div>
            </div>

            {/* Account Deletion */}
            <div className="pt-8 border-t border-slate-700">
              <h3 className="text-lg font-bold text-rose-400 mb-4 flex items-center gap-2">
                <Trash2 className="w-5 h-5" />
                Exclusão de Conta
              </h3>
              <div className="p-4 bg-gradient-to-br from-rose-900/30 to-rose-700/10 border border-rose-500/30 rounded-lg mb-6">
                <p className="text-sm text-rose-200/80">
                  <strong>⚠️ Atenção:</strong> Ao excluir sua conta, todos os bots serão desativados imediatamente.
                  Seus dados serão removidos permanentemente após 30 dias. Durante esse período,
                  você pode contatar o suporte para reverter a exclusão.
                </p>
              </div>

              {!confirmDelete ? (
                <Button
                  onClick={() => setConfirmDelete(true)}
                  variant="outline"
                  className="border-rose-500/50 text-rose-400 hover:bg-rose-600/10 font-semibold h-11"
                >
                  <Trash2 className="w-4 h-4 mr-2" />
                  Solicitar Exclusão de Conta
                </Button>
              ) : (
                <div className="space-y-4 p-4 border border-rose-500/30 rounded-lg bg-rose-950/20">
                  <p className="text-sm text-rose-300 font-semibold">
                    Confirme sua senha para prosseguir:
                  </p>
                  <Input
                    type="password"
                    value={deletePassword}
                    onChange={(e) => setDeletePassword(e.target.value)}
                    placeholder="Sua senha atual"
                    className="bg-slate-800/50 border-slate-700 h-12 text-white"
                  />
                  <Input
                    type="text"
                    value={deleteReason}
                    onChange={(e) => setDeleteReason(e.target.value)}
                    placeholder="Motivo (opcional)"
                    className="bg-slate-800/50 border-slate-700 h-12 text-white"
                  />
                  <div className="flex gap-3">
                    <Button
                      onClick={handleDeleteAccount}
                      disabled={deletingAccount || !deletePassword}
                      className="bg-rose-600 hover:bg-rose-700 text-white font-semibold h-11"
                    >
                      {deletingAccount ? <Loader className="w-4 h-4 mr-2 animate-spin" /> : <Trash2 className="w-4 h-4 mr-2" />}
                      Confirmar Exclusão
                    </Button>
                    <Button
                      onClick={() => { setConfirmDelete(false); setDeletePassword(''); }}
                      variant="outline"
                      className="border-slate-600 text-slate-400 h-11"
                    >
                      Cancelar
                    </Button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </TabsContent>
      </Tabs>
      </div>

      {/* Avatar Selector Modal */}
      <AvatarSelectorModal
        open={openAvatarModal}
        onOpenChange={setOpenAvatarModal}
        avatars={availableAvatars}
        selectedId={selectedAvatar}
        onSelect={setSelectedAvatar}
      />

      {/* 2FA Setup Dialog */}
      <TwoFactorSetup
        isOpen={show2FASetup}
        onClose={() => setShow2FASetup(false)}
        onComplete={handle2FASetupComplete}
      />

      {/* Disable 2FA Confirmation Dialog */}
      {showDisable2FADialog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="bg-slate-900 border border-slate-700 rounded-xl p-6 w-full max-w-md mx-4 space-y-4">
            <h3 className="text-lg font-bold text-white flex items-center gap-2">
              <Shield className="w-5 h-5 text-red-400" />
              {t('settings.disable2FATitle') || 'Desativar 2FA'}
            </h3>
            <p className="text-sm text-slate-400">
              {t('settings.disable2FADesc') || 'Digite o código do seu autenticador para desativar a autenticação de dois fatores.'}
            </p>
            <Input
              value={disable2FACode}
              onChange={(e) => setDisable2FACode(e.target.value.replace(/\D/g, '').slice(0, 6))}
              placeholder="000000"
              maxLength={6}
              className="bg-slate-800 border-slate-700 text-white text-center text-xl tracking-widest font-mono"
            />
            <div className="flex gap-3 justify-end">
              <Button
                variant="ghost"
                onClick={() => { setShowDisable2FADialog(false); setDisable2FACode(''); }}
                className="text-slate-400"
              >
                {t('common.cancel') || 'Cancelar'}
              </Button>
              <Button
                onClick={handleDisable2FA}
                disabled={disable2FACode.length !== 6 || disabling2FA}
                className="bg-red-600 hover:bg-red-700"
              >
                {disabling2FA ? <Loader className="w-4 h-4 animate-spin mr-2" /> : null}
                {t('settings.disable2FAConfirm') || 'Desativar'}
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Regenerate Backup Codes Dialog */}
      {showRegenDialog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="bg-slate-900 border border-slate-700 rounded-xl p-6 w-full max-w-md mx-4 space-y-4">
            <h3 className="text-lg font-bold text-white flex items-center gap-2">
              <KeyRound className="w-5 h-5 text-amber-400" />
              {t('settings.regenerateBackupCodes') || 'Regenerar Backup Codes'}
            </h3>
            <p className="text-sm text-slate-400">
              {t('settings.regenBackupDesc') || 'Digite o código do seu autenticador para gerar novos códigos de backup. Os códigos anteriores serão invalidados.'}
            </p>
            <Input
              value={regenCode}
              onChange={(e) => setRegenCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
              placeholder="000000"
              maxLength={6}
              className="bg-slate-800 border-slate-700 text-white text-center text-xl tracking-widest font-mono"
            />
            <div className="flex gap-3 justify-end">
              <Button
                variant="ghost"
                onClick={() => { setShowRegenDialog(false); setRegenCode(''); }}
                className="text-slate-400"
              >
                {t('common.cancel') || 'Cancelar'}
              </Button>
              <Button
                onClick={handleRegenerateBackupCodes}
                disabled={regenCode.length !== 6 || regeneratingCodes}
                className="bg-amber-600 hover:bg-amber-700"
              >
                {regeneratingCodes ? <Loader className="w-4 h-4 animate-spin mr-2" /> : <RefreshCw className="w-4 h-4 mr-2" />}
                {t('settings.regenerate') || 'Regenerar'}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
