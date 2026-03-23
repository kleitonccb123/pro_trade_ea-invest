import { useState, useEffect } from 'react';
import { Copy, Share2, TrendingUp, Users, DollarSign, Award, Zap, Gift, Target, Lock, RefreshCw, Smartphone, Mail, Heart, MessageCircle, Link as LinkIcon, Eye, EyeOff, Calendar, CheckCircle2, Flame, Wallet, CreditCard, ArrowDownCircle, AlertCircle, Clock } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Skeleton } from '@/components/ui/skeleton';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';
import { useToast } from '@/hooks/use-toast';
import { useApiErrorToast } from '@/hooks/use-api-error-handler';
import { affiliateApi, AffiliateStats as ApiAffiliateStats, AffiliateTier, AffiliateWallet } from '@/lib/api';
import { useLanguage } from '@/hooks/use-language';

interface AffiliateStats {
  total_referrals: number;
  active_referrals: number;
  total_earnings: number;
  pending_earnings: number;
  withdrawn_earnings: number;
  commission_rate: number;
  level: string;
  next_level?: string;
  referrals_to_next_level?: number;
}

interface LevelInfo {
  level: string;
  bonus_percentage: number;
  min_referrals: number;
  commission_rate: number;
  description: string;
  special_benefits?: string;
}

interface Referral {
  id: string;
  name?: string;
  email: string;
  status: 'active' | 'inactive' | 'pending';
  joined_at: string;
  total_spent: number;
  commissions_earned: number;
}

interface ReferralsData {
  referrals: Referral[];
  total_count: number;
}

const LEVEL_COLORS = {
  bronze: { bg: 'from-orange-500 to-yellow-500', text: 'text-orange-600', border: 'border-orange-500/40' },
  silver: { bg: 'from-gray-400 to-gray-500', text: 'text-gray-600', border: 'border-gray-500/40' },
  gold: { bg: 'from-yellow-400 to-yellow-500', text: 'text-yellow-600', border: 'border-yellow-500/40' },
  platinum: { bg: 'from-cyan-400 to-blue-500', text: 'text-blue-600', border: 'border-blue-500/40' },
  diamond: { bg: 'from-purple-500 to-pink-500', text: 'text-pink-600', border: 'border-pink-500/40' },
};

const LEVEL_EMOJIS = {
  bronze: '🥉',
  silver: '🥈',
  gold: '🥇',
  platinum: '💎',
  diamond: '👑',
};

export default function Affiliate() {
  const [stats, setStats] = useState<AffiliateStats | null>(null);
  const [levels, setLevels] = useState<LevelInfo[]>([]);
  const [referrals, setReferrals] = useState<Referral[]>([]);
  const [referralCode, setReferralCode] = useState('');
  const [referralLink, setReferralLink] = useState('');
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [copied, setCopied] = useState<'code' | 'link' | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState('overview');
  const [showHideBalance, setShowHideBalance] = useState(false);
  const { toast } = useToast();
  const { t } = useLanguage();

  // Wallet state
  const [walletData, setWalletData] = useState<AffiliateWallet | null>(null);
  const [transactions, setTransactions] = useState<any[]>([]);
  const [showWithdrawModal, setShowWithdrawModal] = useState(false);
  const [showMethodModal, setShowMethodModal] = useState(false);
  const [withdrawAmount, setWithdrawAmount] = useState('');
  const [pixKeyType, setPixKeyType] = useState('cpf');
  const [pixKey, setPixKey] = useState('');
  const [holderName, setHolderName] = useState('');
  const [submitting, setSubmitting] = useState(false);

  // Enable global API error toasts
  useApiErrorToast();

  // Load affiliate code from localStorage on mount
  useEffect(() => {
    const savedCode = localStorage.getItem('affiliate_code');
    if (savedCode) {
      setReferralCode(savedCode);
      setReferralLink(`${window.location.origin}?ref=${savedCode}`);
    }
  }, []);

  useEffect(() => {
    fetchAffiliateData();
    fetchWalletData();
  }, []);

  const fetchAffiliateData = async (isRefresh = false) => {
    if (isRefresh) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }
    setError(null);

    try {
      console.log('[Affiliate] Iniciando fetchAffiliateData...');

      // Fetch data from real API endpoints
      const [affiliateInfo, statsData, tiersData] = await Promise.all([
        affiliateApi.getMe().catch((err) => {
          console.warn('[Affiliate] getMe erro:', err);
          return null;
        }),
        affiliateApi.getStats().catch((err) => {
          console.warn('[Affiliate] getStats erro:', err);
          return null;
        }),
        affiliateApi.getTiers().catch((err) => {
          console.warn('[Affiliate] getTiers erro:', err);
          return [];
        }),
      ]);

      console.log('[Affiliate] API responses:', { affiliateInfo, statsData, tiersData });

      // If user doesn't have affiliate code, try to generate one
      let code = affiliateInfo?.code;
      if (!code) {
        try {
          const generated = await affiliateApi.generateCode();
          code = generated.code;
          console.log('[Affiliate] Código gerado:', code);
        } catch (e) {
          console.log('[Affiliate] generateCode erro, usando fallback');
          // Fallback: use or generate local storage code
          code = localStorage.getItem('affiliate_code') || `AFF${Math.random().toString(36).substr(2, 8).toUpperCase()}`;
          localStorage.setItem('affiliate_code', code);
        }
      }

      if (statsData) {
        const newStats = {
          total_referrals: statsData.total_referrals,
          active_referrals: statsData.active_referrals,
          total_earnings: statsData.total_earnings,
          pending_earnings: statsData.pending_earnings,
          withdrawn_earnings: statsData.withdrawn_earnings,
          commission_rate: statsData.commission_rate,
          level: statsData.level,
          next_level: statsData.next_level,
          referrals_to_next_level: statsData.referrals_to_next_level,
        };
        setStats(newStats);
        console.log('[Affiliate] Stats definidas:', newStats);
      } else {
        // Fallback to default stats if API unavailable
        const fallbackStats = {
          total_referrals: 0,
          active_referrals: 0,
          total_earnings: 0,
          pending_earnings: 0,
          withdrawn_earnings: 0,
          commission_rate: 5.0,
          level: 'bronze',
          next_level: 'silver',
          referrals_to_next_level: 5,
        };
        setStats(fallbackStats);
        console.log('[Affiliate] Usando fallback stats');
      }

      // Map tiers to local format
      if (tiersData && tiersData.length > 0) {
        const mappedLevels = tiersData.map((tier: AffiliateTier) => ({
          level: tier.level,
          bonus_percentage: tier.bonus_percentage,
          min_referrals: tier.min_referrals,
          commission_rate: tier.commission_rate,
          description: tier.description,
          special_benefits: tier.special_benefits,
        }));
        setLevels(mappedLevels);
        console.log('[Affiliate] Níveis carregados:', mappedLevels);
      } else {
        // Fallback tiers
        const fallbackLevels = [
          { level: 'bronze', bonus_percentage: 0, min_referrals: 0, commission_rate: 5.0, description: 'Comece sua jornada como afiliado', special_benefits: 'Acesso ao painel básico e link de referência' },
          { level: 'silver', bonus_percentage: 3, min_referrals: 5, commission_rate: 8.0, description: 'Parabéns! Você está crescendo', special_benefits: 'Suporte prioritário + Bônus de 3% adicional' },
          { level: 'gold', bonus_percentage: 7, min_referrals: 20, commission_rate: 12.0, description: 'Elite de afiliados', special_benefits: 'Gerente dedicado + Bônus de 7% + Banners exclusivos' },
          { level: 'platinum', bonus_percentage: 10, min_referrals: 50, commission_rate: 15.0, description: 'Você é uma estrela!', special_benefits: 'Tudo do Gold + Programa VIP + Eventos exclusivos' },
          { level: 'diamond', bonus_percentage: 15, min_referrals: 100, commission_rate: 20.0, description: 'O topo da hierarquia', special_benefits: 'Tudo do Platinum + Comissão customizada + Carro brinde anual' },
        ];
        setLevels(fallbackLevels);
        console.log('[Affiliate] Usando fallback níveis');
      }

      // Simular dados de referências (em produção viriam da API)
      const referralsList: Referral[] = [
        { id: '1', email: 'user1@example.com', status: 'active', joined_at: '2024-01-15', total_spent: 1250, commissions_earned: 62.50 },
        { id: '2', email: 'user2@example.com', status: 'active', joined_at: '2024-02-03', total_spent: 850, commissions_earned: 42.50 },
        { id: '3', email: 'user3@example.com', status: 'inactive', joined_at: '2024-02-10', total_spent: 340, commissions_earned: 0 },
        { id: '4', email: 'user4@example.com', status: 'pending', joined_at: '2024-02-15', total_spent: 0, commissions_earned: 0 },
      ];
      setReferrals(referralsList);

      // Set referral code and link
      if (code) {
        setReferralCode(code);
        setReferralLink(`${window.location.origin}?ref=${code}`);
        console.log('[Affiliate] Código de referência definido:', code);
      }

      if (isRefresh) {
        toast({
          title: `✅ ${t('affiliates.updated')}`,
          description: t('affiliates.updatedDesc'),
        });
      }

      console.log('[Affiliate] Carregamento concluído com sucesso');
    } catch (err) {
      console.error('[Affiliate] Erro ao carregar dados:', err);
      setError(t('affiliates.loadError'));
      
      // Generate a fallback code if not already done
      const fallbackCode = localStorage.getItem('affiliate_code') || `AFF${Math.random().toString(36).substr(2, 8).toUpperCase()}`;
      if (!localStorage.getItem('affiliate_code')) {
        localStorage.setItem('affiliate_code', fallbackCode);
      }
      setReferralCode(fallbackCode);
      setReferralLink(`${window.location.origin}?ref=${fallbackCode}`);
      
      // Set default stats
      setStats({
        total_referrals: 0,
        active_referrals: 0,
        total_earnings: 0,
        pending_earnings: 0,
        withdrawn_earnings: 0,
        commission_rate: 5.0,
        level: 'bronze',
        next_level: 'silver',
        referrals_to_next_level: 5,
      });

      setLevels([
        { level: 'bronze', bonus_percentage: 0, min_referrals: 0, commission_rate: 5.0, description: 'Comece sua jornada como afiliado', special_benefits: 'Acesso ao painel básico e link de referência' },
        { level: 'silver', bonus_percentage: 3, min_referrals: 5, commission_rate: 8.0, description: 'Parabéns! Você está crescendo', special_benefits: 'Suporte prioritário + Bônus de 3% adicional' },
        { level: 'gold', bonus_percentage: 7, min_referrals: 20, commission_rate: 12.0, description: 'Elite de afiliados', special_benefits: 'Gerente dedicado + Bônus de 7% + Banners exclusivos' },
        { level: 'platinum', bonus_percentage: 10, min_referrals: 50, commission_rate: 15.0, description: 'Você é uma estrela!', special_benefits: 'Tudo do Gold + Programa VIP + Eventos exclusivos' },
        { level: 'diamond', bonus_percentage: 15, min_referrals: 100, commission_rate: 20.0, description: 'O topo da hierarquia', special_benefits: 'Tudo do Platinum + Comissão customizada + Carro brinde anual' },
      ]);
      
      toast({
        title: t('affiliates.warning'),
        description: t('affiliates.usingCache'),
        variant: 'destructive',
      });
    } finally {
      setLoading(false);
      setRefreshing(false);
      console.log('[Affiliate] Estado de loading finalizado');
    }
  };

  const fetchWalletData = async () => {
    try {
      const [wallet, txData] = await Promise.all([
        affiliateApi.getWallet().catch(() => null),
        affiliateApi.getTransactions({ page: 1, per_page: 20 }).catch(() => ({ transactions: [], total: 0, page: 1, per_page: 20 })),
      ]);
      if (wallet) setWalletData(wallet);
      if (txData?.transactions) setTransactions(txData.transactions);
    } catch (err) {
      console.warn('[Affiliate] fetchWalletData error:', err);
    }
  };

  const handleSetWithdrawalMethod = async () => {
    if (!pixKey.trim() || !holderName.trim()) return;
    setSubmitting(true);
    try {
      await affiliateApi.setWithdrawalMethod({ type: 'pix', key: pixKey.trim(), holder_name: holderName.trim() });
      toast({ title: `✅ ${t('affiliates.methodSaved')}` });
      setShowMethodModal(false);
      setPixKey('');
      setHolderName('');
      await fetchWalletData();
    } catch (err: any) {
      toast({ title: t('affiliates.withdrawError'), description: err?.message, variant: 'destructive' });
    } finally {
      setSubmitting(false);
    }
  };

  const handleRequestWithdrawal = async () => {
    const amount = parseFloat(withdrawAmount);
    if (isNaN(amount) || amount < 50) {
      toast({ title: t('affiliates.minWithdrawalAmount'), variant: 'destructive' });
      return;
    }
    setSubmitting(true);
    try {
      const result = await affiliateApi.requestWithdrawal(amount);
      if (result.success) {
        toast({ title: `✅ ${t('affiliates.withdrawSuccess')}` });
        setShowWithdrawModal(false);
        setWithdrawAmount('');
        await fetchWalletData();
      } else {
        toast({ title: t('affiliates.withdrawError'), description: result.message, variant: 'destructive' });
      }
    } catch (err: any) {
      toast({ title: t('affiliates.withdrawError'), description: err?.message, variant: 'destructive' });
    } finally {
      setSubmitting(false);
    }
  };

  const copyToClipboard = (text: string, type: 'code' | 'link') => {
    navigator.clipboard.writeText(text);
    setCopied(type);
    toast({
      title: `✅ ${t('affiliates.copied')}`,
      description: type === 'code' ? t('affiliates.codeCopied') : t('affiliates.linkCopied'),
    });
    setTimeout(() => setCopied(null), 2000);
  };

  const shareToSocial = (platform: string) => {
    const text = t('affiliates.shareText').replace('{code}', referralCode);
    const urls: Record<string, string> = {
      whatsapp: `https://wa.me/?text=${encodeURIComponent(text + ' ' + referralLink)}`,
      telegram: `https://t.me/share/url?url=${encodeURIComponent(referralLink)}&text=${encodeURIComponent(text)}`,
      twitter: `https://twitter.com/intent/tweet?text=${encodeURIComponent(text)}&url=${encodeURIComponent(referralLink)}`,
      email: `mailto:?subject=${encodeURIComponent(t('affiliates.shareEmailSubject'))}&body=${encodeURIComponent(text + '\n\n' + referralLink)}`,
    };

    if (urls[platform]) {
      window.open(urls[platform], '_blank', 'width=600,height=400');
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-background via-background to-primary/5 p-6 md:p-8">
        <div className="max-w-7xl mx-auto space-y-8">
          {/* Hero Skeleton */}
          <div className="text-center space-y-6 pt-8">
            <Skeleton className="h-8 w-48 mx-auto rounded-full" />
            <Skeleton className="h-20 w-96 mx-auto" />
            <Skeleton className="h-6 w-80 mx-auto" />
          </div>
          
          {/* Level Card Skeleton */}
          <div className="glass-card border p-8 rounded-2xl">
            <div className="flex flex-col md:flex-row justify-between gap-6">
              <div className="space-y-4">
                <Skeleton className="h-8 w-40" />
                <Skeleton className="h-6 w-60" />
                <Skeleton className="h-4 w-full max-w-md" />
              </div>
              <div className="space-y-3">
                <Skeleton className="h-10 w-64" />
                <Skeleton className="h-10 w-64" />
              </div>
            </div>
          </div>

          {/* Stats Grid Skeleton */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
            {[1, 2, 3, 4].map((i) => (
              <Card key={i} className="glass-card">
                <CardHeader className="pb-2">
                  <Skeleton className="h-4 w-24" />
                </CardHeader>
                <CardContent>
                  <Skeleton className="h-8 w-20" />
                  <Skeleton className="h-4 w-32 mt-2" />
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </div>
    );
  }


  const LEVEL_COLORS = {
    bronze: { bg: 'from-orange-500 to-yellow-500', text: 'text-orange-600', border: 'border-orange-500/40' },
    silver: { bg: 'from-gray-400 to-gray-500', text: 'text-gray-600', border: 'border-gray-500/40' },
    gold: { bg: 'from-yellow-400 to-yellow-500', text: 'text-yellow-600', border: 'border-yellow-500/40' },
    platinum: { bg: 'from-cyan-400 to-blue-500', text: 'text-blue-600', border: 'border-blue-500/40' },
    diamond: { bg: 'from-purple-500 to-pink-500', text: 'text-pink-600', border: 'border-pink-500/40' },
  };

  const LEVEL_EMOJIS = {
    bronze: '🥉',
    silver: '🥈',
    gold: '🥇',
    platinum: '💎',
    diamond: '👑',
  };

  const currentLevelColor = LEVEL_COLORS[stats?.level as keyof typeof LEVEL_COLORS] || LEVEL_COLORS.bronze;
  const levelEmoji = LEVEL_EMOJIS[stats?.level as keyof typeof LEVEL_EMOJIS] || '🥉';

  return (
    <div className="w-full space-y-8" style={{ background: '#0B0E11', minHeight: '100vh' }}>
      {/* Premium Animated Background */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-20 left-10 w-72 h-72 rounded-full blur-3xl animate-pulse" style={{ background: 'rgba(35,200,130,0.07)' }}></div>
        <div className="absolute bottom-20 right-10 w-96 h-96 rounded-full blur-3xl animate-pulse" style={{ animationDelay: '2s', background: 'rgba(20,160,100,0.05)' }}></div>
        <div className="absolute top-1/3 right-1/3 w-64 h-64 rounded-full blur-3xl" style={{ background: 'rgba(35,200,130,0.04)' }}></div>
      </div>

      <div className="relative z-10 p-6 md:p-8 space-y-8 max-w-7xl mx-auto">
        {/* Header with Refresh */}
        <div className="flex items-center justify-between pt-4">
          <div>
            <h1 className="text-3xl md:text-4xl font-black bg-gradient-to-r from-emerald-400 to-teal-400 bg-clip-text text-transparent">
              💰 {t('affiliates.programTitle')}
            </h1>
            <p className="text-muted-foreground mt-1">{t('affiliates.unlimitedCommissions')}</p>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => fetchAffiliateData(true)}
            disabled={refreshing}
            className="border-emerald-500/30 hover:border-emerald-500/60 text-emerald-400 hover:text-emerald-300 bg-transparent transition-all"
          >
            <RefreshCw className={`w-4 h-4 mr-2 ${refreshing ? 'animate-spin' : ''}`} />
            {refreshing ? t('affiliates.refreshing') : t('affiliates.refresh')}
          </Button>
        </div>

        {/* Error Banner */}
        {error && (
          <div className="bg-yellow-500/10 border border-yellow-500/30 text-yellow-500 px-4 py-3 rounded-lg flex items-center gap-2">
            <span>⚠️</span>
            <span>{error}</span>
          </div>
        )}

        {/* Tabs Navigation */}
        <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
          <TabsList className="grid w-full max-w-2xl grid-cols-4 p-1 rounded-xl" style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(35,200,130,0.2)' }}>
            <TabsTrigger value="overview" className="gap-2">
              <TrendingUp className="w-4 h-4" />
              <span className="hidden sm:inline">{t('affiliates.overview')}</span>
              <span className="sm:hidden">{t('affiliates.overview')}</span>
            </TabsTrigger>
            <TabsTrigger value="referrals" className="gap-2">
              <Users className="w-4 h-4" />
              <span className="hidden sm:inline">{t('affiliates.referrals')}</span>
              <span className="sm:hidden">{t('affiliates.referrals')}</span>
            </TabsTrigger>
            <TabsTrigger value="levels" className="gap-2">
              <Award className="w-4 h-4" />
              <span className="hidden sm:inline">{t('affiliates.levelsTab')}</span>
              <span className="sm:hidden">{t('affiliates.levelsTab')}</span>
            </TabsTrigger>
            <TabsTrigger value="wallet" className="gap-2">
              <Wallet className="w-4 h-4" />
              <span className="hidden sm:inline">{t('affiliates.walletTab')}</span>
              <span className="sm:hidden">{t('affiliates.walletTab')}</span>
            </TabsTrigger>
          </TabsList>

          {/* Overview Tab */}
          <TabsContent value="overview" className="space-y-8">
            {/* Current Level Card */}
            {stats && (
            <div className={`rounded-2xl p-8 md:p-12 transition-all duration-300 overflow-hidden relative group`}
              style={{ border: `2px solid ${currentLevelColor.border.replace('border-','').includes('orange') ? 'rgba(249,115,22,0.4)' : currentLevelColor.border.replace('border-','').includes('gray') ? 'rgba(107,114,128,0.4)' : currentLevelColor.border.replace('border-','').includes('yellow') ? 'rgba(234,179,8,0.4)' : 'rgba(35,200,130,0.25)'}`, background: 'rgba(255,255,255,0.02)' }}>
                <div className={`absolute top-0 right-0 w-96 h-96 bg-gradient-to-bl ${currentLevelColor.bg} opacity-10 rounded-full blur-3xl -mr-48 -mt-48 group-hover:scale-125 transition-transform duration-500`}></div>

                <div className="relative z-10 space-y-8">
                  <div className="flex items-center justify-between flex-wrap gap-4">
                    <div className="space-y-3">
                      <p className="text-sm text-muted-foreground font-bold uppercase tracking-widest">{t('affiliates.currentLevel')}</p>
                      <div className="flex items-center gap-4">
                        <span className="text-6xl font-black">{levelEmoji}</span>
                        <div>
                      <h2 className="text-4xl font-black bg-gradient-to-r from-emerald-400 to-teal-400 bg-clip-text text-transparent capitalize">
                            {stats.level}
                          </h2>
                          <p className="text-lg text-muted-foreground">{stats.commission_rate}% {t('affiliates.ofCommission')}</p>
                        </div>
                      </div>
                    </div>

                    {stats.next_level && (
                      <div className="text-center space-y-2 bg-muted/30 px-6 py-4 rounded-xl">
                        <p className="text-sm text-muted-foreground font-bold">⏫ {t('affiliates.nextLevel')}</p>
                        <p className="text-3xl font-bold text-teal-400 capitalize">{stats.next_level}</p>
                        <p className="text-sm bg-emerald-500/15 text-emerald-400 px-3 py-1 rounded-full font-bold inline-block">
                          {stats.referrals_to_next_level} {t('affiliates.references')}
                        </p>
                      </div>
                    )}
                  </div>

                  {stats.next_level && (
                    <div className="space-y-2">
                      <div className="flex justify-between text-sm">
                        <span>{t('affiliates.progress')}:</span>
                        <span className="font-bold text-emerald-400">{stats.active_referrals}/{(stats.active_referrals || 1) + (stats.referrals_to_next_level || 1)}</span>
                      </div>
                      <div className="w-full bg-muted/30 rounded-full h-3 border border-border/40 overflow-hidden">
                        <div
                          className="h-full rounded-full transition-all duration-500"
                          style={{ width: `${Math.min((stats.active_referrals / ((stats.active_referrals || 1) + (stats.referrals_to_next_level || 1))) * 100, 100)}%`, background: 'linear-gradient(90deg, #23C882, #1aaa6e)' }}
                        ></div>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Stats Grid */}
            {stats && (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                {/* Total Earnings */}
                <div className="rounded-2xl p-6 hover:shadow-lg transition-all duration-300 group overflow-hidden relative" style={{ background: 'rgba(35,200,130,0.06)', border: '1px solid rgba(35,200,130,0.25)' }}>
                  <div className="absolute top-0 right-0 w-32 h-32 rounded-full blur-2xl -mr-16 -mt-16 group-hover:scale-150 transition-transform" style={{ background: 'rgba(35,200,130,0.15)' }}></div>
                  <div className="relative z-10 space-y-3">
                    <div className="flex items-center justify-between">
                      <DollarSign className="w-6 h-6 text-emerald-400" />
                      <span className="text-xs font-bold text-emerald-400 px-2 py-1 rounded-full" style={{ background: 'rgba(35,200,130,0.15)' }}>{t('affiliates.total')}</span>
                    </div>
                    <div>
                      <p className="text-sm text-slate-400 font-bold mb-1">{t('affiliates.totalEarnings')}</p>
                      <p className="text-3xl font-black text-emerald-400 flex items-center gap-2">
                        ${stats.total_earnings.toFixed(2)}
                        <Flame className="w-5 h-5 text-orange-500" />
                      </p>
                    </div>
                  </div>
                </div>

                {/* Pending Earnings */}
                <div className="rounded-2xl p-6 hover:shadow-lg transition-all duration-300 group overflow-hidden relative" style={{ background: 'rgba(250,173,20,0.06)', border: '1px solid rgba(250,173,20,0.25)' }}>
                  <div className="absolute top-0 right-0 w-32 h-32 rounded-full blur-2xl -mr-16 -mt-16 group-hover:scale-150 transition-transform" style={{ background: 'rgba(250,173,20,0.15)' }}></div>
                  <div className="relative z-10 space-y-3">
                    <div className="flex items-center justify-between">
                      <Zap className="w-6 h-6 text-amber-400" />
                      <span className="text-xs font-bold text-amber-400 px-2 py-1 rounded-full" style={{ background: 'rgba(250,173,20,0.15)' }}>{t('affiliates.pending')}</span>
                    </div>
                    <div>
                      <p className="text-sm text-slate-400 font-bold mb-1">{t('affiliates.processing')}</p>
                      <p className="text-3xl font-black text-amber-400">${stats.pending_earnings.toFixed(2)}</p>
                    </div>
                  </div>
                </div>

                {/* Active Referrals */}
                <div className="rounded-2xl p-6 hover:shadow-lg transition-all duration-300 group overflow-hidden relative" style={{ background: 'rgba(35,200,130,0.04)', border: '1px solid rgba(35,200,130,0.18)' }}>
                  <div className="absolute top-0 right-0 w-32 h-32 rounded-full blur-2xl -mr-16 -mt-16 group-hover:scale-150 transition-transform" style={{ background: 'rgba(35,200,130,0.10)' }}></div>
                  <div className="relative z-10 space-y-3">
                    <div className="flex items-center justify-between">
                      <Users className="w-6 h-6 text-emerald-400" />
                      <span className="text-xs font-bold text-emerald-400 px-2 py-1 rounded-full" style={{ background: 'rgba(35,200,130,0.12)' }}>{t('affiliates.active')}</span>
                    </div>
                    <div>
                      <p className="text-sm text-slate-400 font-bold mb-1">{t('affiliates.activeReferrals')}</p>
                      <p className="text-3xl font-black text-emerald-400">{stats.active_referrals}</p>
                    </div>
                  </div>
                </div>

                {/* Total Referrals */}
                <div className="rounded-2xl p-6 hover:shadow-lg transition-all duration-300 group overflow-hidden relative" style={{ background: 'rgba(20,160,100,0.05)', border: '1px solid rgba(35,200,130,0.15)' }}>
                  <div className="absolute top-0 right-0 w-32 h-32 rounded-full blur-2xl -mr-16 -mt-16 group-hover:scale-150 transition-transform" style={{ background: 'rgba(35,200,130,0.08)' }}></div>
                  <div className="relative z-10 space-y-3">
                    <div className="flex items-center justify-between">
                      <TrendingUp className="w-6 h-6 text-teal-400" />
                      <span className="text-xs font-bold text-teal-400 px-2 py-1 rounded-full" style={{ background: 'rgba(20,160,100,0.15)' }}>{t('affiliates.total')}</span>
                    </div>
                    <div>
                      <p className="text-sm text-slate-400 font-bold mb-1">{t('affiliates.totalReferred')}</p>
                      <p className="text-3xl font-black text-teal-400">{stats.total_referrals}</p>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Share Section */}
            <div className="space-y-6">
              <div className="text-center space-y-2">
                <h3 className="text-2xl font-bold bg-gradient-to-r from-emerald-400 to-teal-400 bg-clip-text text-transparent">
                  📢 {t('affiliates.shareAndEarn')}
                </h3>
                <p className="text-muted-foreground">{t('affiliates.shareDesc')}</p>
              </div>

              <div className="grid md:grid-cols-2 gap-6">
                {/* Referral Code */}
                <div className="rounded-2xl p-8 hover:shadow-lg transition-all duration-300" style={{ background: 'rgba(35,200,130,0.05)', border: '1px solid rgba(35,200,130,0.25)' }}>
                  <div className="space-y-4">
                    <div className="flex items-center gap-2">
                      <Lock className="w-5 h-5 text-emerald-400" />
                      <h3 className="text-lg font-bold text-white">{t('affiliates.yourCode')}</h3>
                    </div>

                    <div className="rounded-xl p-6 font-mono text-center space-y-3" style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(35,200,130,0.2)' }}>
                      <p className="text-3xl font-black text-emerald-400 tracking-widest">{referralCode || t('affiliates.loadingText')}</p>
                      <Button
                        onClick={() => copyToClipboard(referralCode, 'code')}
                        className="w-full font-bold transition-all duration-300 text-emerald-400 border-emerald-500/30 hover:border-emerald-500/60 bg-transparent hover:bg-emerald-500/10"
                        variant="outline"
                      >
                        <Copy className="w-4 h-4 mr-2" />
                        {copied === 'code' ? `✅ ${t('affiliates.copied')}` : t('affiliates.copyCode')}
                      </Button>
                    </div>
                  </div>
                </div>

                {/* Referral Link */}
                <div className="rounded-2xl p-8 hover:shadow-lg transition-all duration-300" style={{ background: 'rgba(20,160,100,0.04)', border: '1px solid rgba(35,200,130,0.18)' }}>
                  <div className="space-y-4">
                    <div className="flex items-center gap-2">
                      <LinkIcon className="w-5 h-5 text-teal-400" />
                      <h3 className="text-lg font-bold text-white">{t('affiliates.referralLink')}</h3>
                    </div>

                    <div className="rounded-xl p-4 space-y-3 break-all" style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(35,200,130,0.15)' }}>
                      <p className="text-sm text-slate-400 font-mono">{referralLink || t('affiliates.loadingText')}</p>
                      <Button
                        onClick={() => copyToClipboard(referralLink, 'link')}
                        className="w-full font-bold transition-all duration-300 text-teal-400 border-teal-500/30 hover:border-teal-500/50 bg-transparent hover:bg-teal-500/10"
                        variant="outline"
                      >
                        <Copy className="w-4 h-4 mr-2" />
                        {copied === 'link' ? `✅ ${t('affiliates.copied')}` : t('affiliates.copyLink')}
                      </Button>
                    </div>
                  </div>
                </div>
              </div>

              {/* Social Share Buttons */}
              <div className="space-y-3">
                <p className="text-center text-muted-foreground font-bold text-sm">{t('affiliates.shareOnSocial')}</p>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  <Button
                    onClick={() => shareToSocial('whatsapp')}
                    className="bg-green-600 hover:bg-green-700 text-white font-bold"
                  >
                    <Smartphone className="w-4 h-4 mr-2" />
                    WhatsApp
                  </Button>
                  <Button
                    onClick={() => shareToSocial('telegram')}
                    className="bg-blue-500 hover:bg-blue-600 text-white font-bold"
                  >
                    <MessageCircle className="w-4 h-4 mr-2" />
                    Telegram
                  </Button>
                  <Button
                    onClick={() => shareToSocial('twitter')}
                    className="bg-sky-500 hover:bg-sky-600 text-white font-bold"
                  >
                    <Share2 className="w-4 h-4 mr-2" />
                    Twitter
                  </Button>
                  <Button
                    onClick={() => shareToSocial('email')}
                    className="bg-teal-700 hover:bg-teal-600 text-white font-bold"
                  >
                    <Mail className="w-4 h-4 mr-2" />
                    Email
                  </Button>
                </div>
              </div>
            </div>
          </TabsContent>

          {/* Referrals Tab */}
          <TabsContent value="referrals" className="space-y-6">
            <div className="space-y-3">
              <h3 className="text-2xl font-bold text-white">👥 {t('affiliates.yourReferrals')}</h3>
              <p className="text-slate-400">{t('affiliates.total')}: <span className="font-bold text-emerald-400">{referrals.length}</span> {t('affiliates.references')}</p>
            </div>

            {referrals.length > 0 ? (
              <div className="rounded-2xl overflow-hidden" style={{ border: '1px solid rgba(35,200,130,0.15)' }}>
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b border-emerald-500/15" style={{ background: 'rgba(255,255,255,0.03)' }}>
                        <th className="px-4 py-4 text-left text-sm font-bold text-slate-400">{t('affiliates.email')}</th>
                        <th className="px-4 py-4 text-left text-sm font-bold text-slate-400 hidden sm:table-cell">{t('affiliates.status')}</th>
                        <th className="px-4 py-4 text-left text-sm font-bold text-slate-400 hidden md:table-cell">{t('affiliates.date')}</th>
                        <th className="px-4 py-4 text-right text-sm font-bold text-slate-400">{t('affiliates.earned')}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {referrals.map((ref) => (
                        <tr key={ref.id} className="border-b border-border/40 hover:bg-muted/20 transition-colors">
                          <td className="px-4 py-4 text-sm">{ref.email}</td>
                          <td className="px-4 py-4 text-sm hidden sm:table-cell">
                            <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-bold ${
                              ref.status === 'active' ? 'bg-green-500/20 text-green-600' :
                              ref.status === 'pending' ? 'bg-yellow-500/20 text-yellow-600' :
                              'bg-gray-500/20 text-gray-600'
                            }`}>
                              {ref.status === 'active' && <CheckCircle2 className="w-3 h-3" />}
                              {ref.status === 'active' && t('affiliates.active')}
                              {ref.status === 'pending' && t('affiliates.pending')}
                              {ref.status === 'inactive' && t('affiliates.inactive')}
                            </span>
                          </td>
                          <td className="px-4 py-4 text-sm hidden md:table-cell text-muted-foreground">
                            {new Date(ref.joined_at).toLocaleDateString('pt-BR')}
                          </td>
                        <td className="px-4 py-3 text-right font-bold text-sm text-emerald-400">${ref.commissions_earned.toFixed(2)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ) : (
              <Card className="rounded-2xl" style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(35,200,130,0.12)' }}>
                <CardContent className="pt-12 pb-12 text-center">
                  <Users className="w-12 h-12 text-slate-600 mx-auto mb-4" />
                  <p className="text-slate-500">{t('affiliates.noReferrals')}</p>
                </CardContent>
              </Card>
            )}
          </TabsContent>

          {/* Levels Tab */}
          <TabsContent value="levels" className="space-y-8">
            <div className="text-center space-y-3 mb-8">
              <h3 className="text-3xl font-bold bg-gradient-to-r from-emerald-400 to-teal-400 bg-clip-text text-transparent">
                🎖️ {t('affiliates.levelStructure')}
              </h3>
              <p className="text-lg text-muted-foreground">{t('affiliates.levelStructureDesc')}</p>
            </div>

            <div className="grid md:grid-cols-2 lg:grid-cols-5 gap-4">
              {levels.map((level, idx) => {
                const levelColor = LEVEL_COLORS[level.level as keyof typeof LEVEL_COLORS];
                const emoji = LEVEL_EMOJIS[level.level as keyof typeof LEVEL_EMOJIS];
                const isActive = stats?.level === level.level;

                return (
                  <div
                    key={level.level}
                    className="rounded-2xl p-6 hover:shadow-lg transition-all duration-300 relative overflow-hidden"
                    style={{
                      border: isActive ? '2px solid rgba(35,200,130,0.6)' : '1px solid rgba(255,255,255,0.07)',
                      background: isActive ? 'rgba(35,200,130,0.07)' : 'rgba(255,255,255,0.02)',
                      boxShadow: isActive ? '0 0 30px rgba(35,200,130,0.2), inset 0 0 20px rgba(35,200,130,0.05)' : 'none',
                    }}
                  >
                    <div className={`absolute top-0 right-0 w-32 h-32 bg-gradient-to-bl ${levelColor.bg} opacity-15 rounded-full blur-2xl -mr-16 -mt-16 group-hover:scale-150 transition-transform`}></div>

                    <div className="relative z-10 space-y-4 text-center">
                      <p className="text-5xl font-black">{emoji}</p>
                      <h3 className={`text-xl font-bold capitalize ${levelColor.text}`}>{level.level}</h3>

                      <div className="space-y-2 text-sm rounded-lg p-3" style={{ background: 'rgba(255,255,255,0.04)' }}>
                        <div className="flex justify-between items-center">
                          <span className="text-slate-400">{t('affiliates.minReferrals')}</span>
                          <span className="text-lg font-black text-emerald-400">{level.min_referrals}</span>
                        </div>
                      </div>

                      <div className="space-y-2 text-sm rounded-lg p-3" style={{ background: 'rgba(255,255,255,0.04)' }}>
                        <div className="flex justify-between items-center">
                          <span className="text-slate-400">{t('affiliates.commission')}</span>
                          <span className="text-lg font-black text-teal-400">{level.commission_rate}%</span>
                        </div>
                      </div>

                      {level.bonus_percentage > 0 && (
                        <div className="rounded-lg py-3 px-3" style={{ background: 'rgba(35,200,130,0.12)', border: '1px solid rgba(35,200,130,0.3)' }}>
                          <p className="text-xs text-slate-400 font-bold">{t('affiliates.bonusReward')}</p>
                          <p className="text-2xl font-bold text-emerald-400">+{level.bonus_percentage}%</p>
                        </div>
                      )}

                      <p className="text-xs text-muted-foreground italic">{level.description}</p>

                      {isActive && (
                        <div className="text-xs px-3 py-2 rounded-full font-bold inline-block w-full text-emerald-400" style={{ background: 'rgba(35,200,130,0.15)' }}>
                          ✨ {t('affiliates.currentLevel')}
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </TabsContent>

          {/* Wallet Tab */}
          <TabsContent value="wallet" className="space-y-6">
            <div className="flex items-center justify-between">
              <h3 className="text-2xl font-bold text-white">💰 {t('affiliates.walletTitle')}</h3>
              <Button
                variant="outline"
                size="sm"
                onClick={fetchWalletData}
                className="border-emerald-500/30 hover:border-emerald-500/60 text-emerald-400 bg-transparent"
              >
                <RefreshCw className="w-4 h-4 mr-2" />
                {t('affiliates.refresh')}
              </Button>
            </div>

            {/* Balance Cards */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div className="rounded-2xl p-6" style={{ background: 'rgba(35,200,130,0.06)', border: '1px solid rgba(35,200,130,0.25)' }}>
                <div className="space-y-2">
                  <p className="text-sm text-slate-400 font-bold flex items-center gap-2">
                    <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                    {t('affiliates.availableBalance')}
                  </p>
                  <p className="text-3xl font-black text-emerald-400">
                    ${(walletData?.available_balance ?? 0).toFixed(2)}
                  </p>
                </div>
              </div>
              <div className="rounded-2xl p-6" style={{ background: 'rgba(250,173,20,0.05)', border: '1px solid rgba(250,173,20,0.2)' }}>
                <div className="space-y-2">
                  <p className="text-sm text-slate-400 font-bold flex items-center gap-2">
                    <Clock className="w-4 h-4 text-amber-400" />
                    {t('affiliates.pendingBalance')}
                  </p>
                  <p className="text-3xl font-black text-amber-400">
                    ${(walletData?.pending_balance ?? 0).toFixed(2)}
                  </p>
                  <p className="text-xs text-muted-foreground">{t('affiliates.holdPeriod')}</p>
                </div>
              </div>
              <div className="rounded-2xl p-6" style={{ background: 'rgba(35,200,130,0.03)', border: '1px solid rgba(35,200,130,0.15)' }}>
                <div className="space-y-2">
                  <p className="text-sm text-slate-400 font-bold flex items-center gap-2">
                    <ArrowDownCircle className="w-4 h-4 text-teal-400" />
                    {t('affiliates.totalWithdrawn')}
                  </p>
                  <p className="text-3xl font-black text-teal-400">
                    ${(walletData?.withdrawn_total ?? 0).toFixed(2)}
                  </p>
                </div>
              </div>
            </div>

            {/* Withdrawal Method + Withdraw Button */}
            <div className="grid md:grid-cols-2 gap-6">
              {/* Method Status */}
              <div className="rounded-2xl p-6 space-y-4" style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(35,200,130,0.15)' }}>
                <div className="flex items-center gap-2">
                  <CreditCard className="w-5 h-5 text-emerald-400" />
                  <h4 className="font-bold text-white">{t('affiliates.setWithdrawalMethod')}</h4>
                </div>
                {walletData?.withdrawal_method ? (
                  <div className="space-y-2 text-sm">
                    <div className="flex items-center gap-2 text-success">
                      <CheckCircle2 className="w-4 h-4" />
                      <span className="font-bold">{t('affiliates.methodConfigured')}</span>
                    </div>
                    <p className="text-muted-foreground">
                      <span className="font-bold">{t('affiliates.methodType')}:</span>{' '}
                      {walletData.withdrawal_method.type.toUpperCase()}
                    </p>
                    <p className="text-muted-foreground font-mono text-xs break-all">
                      {walletData.withdrawal_method.key}
                    </p>
                  </div>
                ) : (
                  <div className="flex items-center gap-2 text-muted-foreground text-sm">
                    <AlertCircle className="w-4 h-4 text-warning" />
                    <span>{t('affiliates.methodNotConfigured')}</span>
                  </div>
                )}
                <Button
                  variant="outline"
                  size="sm"
                  className="w-full border-emerald-500/30 hover:border-emerald-500/60 text-emerald-400 bg-transparent"
                  onClick={() => {
                    if (walletData?.withdrawal_method) {
                      setPixKey(walletData.withdrawal_method.key);
                      setHolderName(walletData.withdrawal_method.holder_name ?? '');
                    }
                    setShowMethodModal(true);
                  }}
                >
                  <CreditCard className="w-4 h-4 mr-2" />
                  {t('affiliates.setWithdrawalMethod')}
                </Button>
              </div>

              {/* Withdraw Action */}
              <div className="rounded-2xl p-6 space-y-4" style={{ background: 'rgba(35,200,130,0.04)', border: '1px solid rgba(35,200,130,0.18)' }}>
                <div className="flex items-center gap-2">
                  <ArrowDownCircle className="w-5 h-5 text-emerald-400" />
                  <h4 className="font-bold text-white">{t('affiliates.withdrawButton')}</h4>
                </div>
                <div className="text-sm text-muted-foreground">
                  <p>{t('affiliates.minWithdrawalAmount')}</p>
                </div>
                <Button
                  className="w-full text-white font-bold"
                  style={{ background: 'linear-gradient(135deg, #23C882 0%, #1aaa6e 100%)' }}
                  disabled={!walletData?.withdrawal_method || (walletData?.available_balance ?? 0) < 50}
                  onClick={() => setShowWithdrawModal(true)}
                >
                  <ArrowDownCircle className="w-4 h-4 mr-2" />
                  {t('affiliates.withdrawButton')}
                </Button>
                {!walletData?.withdrawal_method && (
                  <p className="text-xs text-muted-foreground text-center">{t('affiliates.configureMethodFirst')}</p>
                )}
              </div>
            </div>

            {/* Transaction History */}
            <div className="space-y-3">
              <h4 className="text-lg font-bold">📋 {t('affiliates.withdrawalHistory')}</h4>
              {transactions.length > 0 ? (
                <div className="rounded-2xl overflow-hidden" style={{ border: '1px solid rgba(35,200,130,0.15)' }}>
                  <div className="overflow-x-auto">
                    <table className="w-full">
                      <thead>
                        <tr className="border-b border-emerald-500/15" style={{ background: 'rgba(255,255,255,0.03)' }}>
                          <th className="px-4 py-3 text-left text-sm font-bold text-slate-400">{t('affiliates.date')}</th>
                          <th className="px-4 py-3 text-left text-sm font-bold text-slate-400 hidden sm:table-cell">Tipo</th>
                          <th className="px-4 py-3 text-left text-sm font-bold text-slate-400">{t('affiliates.status')}</th>
                          <th className="px-4 py-3 text-right text-sm font-bold text-slate-400">{t('affiliates.earned')}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {transactions.map((tx: any, idx: number) => (
                          <tr key={tx.id ?? idx} className="border-b border-border/40 hover:bg-muted/20 transition-colors">
                            <td className="px-4 py-3 text-sm text-muted-foreground">
                              {tx.created_at ? new Date(tx.created_at).toLocaleDateString('pt-BR') : '—'}
                            </td>
                            <td className="px-4 py-3 text-sm hidden sm:table-cell capitalize">{tx.type}</td>
                            <td className="px-4 py-3 text-sm">
                              <Badge variant={
                                tx.status === 'completed' || tx.status === 'available' ? 'default' :
                                tx.status === 'pending' || tx.status === 'processing' ? 'secondary' : 'destructive'
                              } className="capitalize">
                                {tx.status === 'pending' && t('affiliates.withdrawalStatusPending')}
                                {tx.status === 'processing' && t('affiliates.withdrawalStatusProcessing')}
                                {tx.status === 'completed' && t('affiliates.withdrawalStatusCompleted')}
                                {tx.status === 'available' && t('affiliates.withdrawalStatusCompleted')}
                                {tx.status === 'failed' && t('affiliates.withdrawalStatusFailed')}
                                {tx.status === 'cancelled' && t('affiliates.withdrawalStatusCancelled')}
                                {!['pending','processing','completed','available','failed','cancelled'].includes(tx.status) && tx.status}
                              </Badge>
                            </td>
                            <td className={`px-4 py-3 text-sm text-right font-bold ${tx.type === 'withdrawal' ? 'text-red-400' : 'text-emerald-400'}`}>
                              {tx.type === 'withdrawal' ? '-' : '+'}${parseFloat(tx.amount_usd ?? 0).toFixed(2)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              ) : (
                <Card className="rounded-2xl" style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(35,200,130,0.12)' }}>
                  <CardContent className="pt-10 pb-10 text-center">
                    <Wallet className="w-10 h-10 text-slate-600 mx-auto mb-3" />
                    <p className="text-slate-500">{t('affiliates.noWithdrawals')}</p>
                  </CardContent>
                </Card>
              )}
            </div>
          </TabsContent>
        </Tabs>

        {/* Set Withdrawal Method Dialog */}
        <Dialog open={showMethodModal} onOpenChange={setShowMethodModal}>
          <DialogContent className="sm:max-w-md">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <CreditCard className="w-5 h-5 text-emerald-400" />
                {t('affiliates.setWithdrawalMethod')}
              </DialogTitle>
            </DialogHeader>
            <div className="space-y-4 py-2">
              <div className="space-y-2">
                <Label>{t('affiliates.pixKeyType')}</Label>
                <Select value={pixKeyType} onValueChange={setPixKeyType}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="cpf">{t('affiliates.pixKeyTypeCPF')}</SelectItem>
                    <SelectItem value="cnpj">{t('affiliates.pixKeyTypeCNPJ')}</SelectItem>
                    <SelectItem value="email">{t('affiliates.pixKeyTypeEmail')}</SelectItem>
                    <SelectItem value="phone">{t('affiliates.pixKeyTypePhone')}</SelectItem>
                    <SelectItem value="random">{t('affiliates.pixKeyTypeRandom')}</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>{t('affiliates.pixKey')}</Label>
                <Input
                  value={pixKey}
                  onChange={(e) => setPixKey(e.target.value)}
                  placeholder={t('affiliates.pixKeyPlaceholder')}
                />
              </div>
              <div className="space-y-2">
                <Label>{t('affiliates.holderName')}</Label>
                <Input
                  value={holderName}
                  onChange={(e) => setHolderName(e.target.value)}
                  placeholder={t('affiliates.holderNamePlaceholder')}
                />
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setShowMethodModal(false)} disabled={submitting}>
                Cancelar
              </Button>
              <Button onClick={handleSetWithdrawalMethod} disabled={submitting || !pixKey.trim() || !holderName.trim()}>
                {submitting ? '...' : t('affiliates.saveMethod')}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Request Withdrawal Dialog */}
        <Dialog open={showWithdrawModal} onOpenChange={setShowWithdrawModal}>
          <DialogContent className="sm:max-w-md">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <ArrowDownCircle className="w-5 h-5 text-success" />
                {t('affiliates.withdrawTitle')}
              </DialogTitle>
            </DialogHeader>
            <div className="space-y-4 py-2">
              {walletData?.withdrawal_method && (
                <div className="bg-muted/30 rounded-lg p-3 text-sm text-muted-foreground">
                  <p className="font-bold mb-1">{t('affiliates.methodConfigured')}</p>
                  <p className="font-mono text-xs">{walletData.withdrawal_method.key}</p>
                </div>
              )}
              <div className="space-y-2">
                <Label>{t('affiliates.withdrawAmount')}</Label>
                <Input
                  type="number"
                  min="50"
                  step="0.01"
                  value={withdrawAmount}
                  onChange={(e) => setWithdrawAmount(e.target.value)}
                  placeholder="50.00"
                />
                <p className="text-xs text-muted-foreground">{t('affiliates.withdrawAmountHint')}</p>
                <p className="text-xs text-muted-foreground">
                  {t('affiliates.availableBalance')}: <span className="font-bold text-success">${(walletData?.available_balance ?? 0).toFixed(2)}</span>
                </p>
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setShowWithdrawModal(false)} disabled={submitting}>
                Cancelar
              </Button>
              <Button
                className="text-white font-bold"
                onClick={handleRequestWithdrawal}
                disabled={submitting || !withdrawAmount || parseFloat(withdrawAmount) < 50}
                style={{ background: 'linear-gradient(135deg, #23C882 0%, #1aaa6e 100%)' }}
              >
                {submitting ? '...' : t('affiliates.withdrawButton')}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* How It Works Section */}
        <div className="space-y-8 mt-16">
          <div className="text-center space-y-3">
            <h2 className="text-3xl font-black bg-gradient-to-r from-emerald-400 to-teal-400 bg-clip-text text-transparent">
              ⚡ {t('affiliates.howItWorks')}
            </h2>
            <p className="text-muted-foreground">{t('affiliates.howItWorksDesc')}</p>
          </div>

          <div className="grid md:grid-cols-3 gap-6">
            {[
              {
                step: '01',
                title: t('affiliates.step1Title'),
                desc: t('affiliates.step1Desc'),
                icon: Share2,
                color: 'text-emerald-400',
              },
              {
                step: '02',
                title: t('affiliates.step2Title'),
                desc: t('affiliates.step2Desc'),
                icon: Users,
                color: 'text-teal-400',
              },
              {
                step: '03',
                title: t('affiliates.step3Title'),
                desc: t('affiliates.step3Desc'),
                icon: DollarSign,
                color: 'text-emerald-300',
              },
            ].map((item, idx) => {
              const Icon = item.icon;
              return (
                <div key={idx} className="rounded-2xl p-8 hover:shadow-lg transition-all duration-300 relative overflow-hidden group" style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(35,200,130,0.15)' }}>
                  <div className="absolute top-0 right-0 w-32 h-32 rounded-full blur-2xl -mr-16 -mt-16 group-hover:scale-150 transition-transform" style={{ background: 'rgba(35,200,130,0.08)' }}></div>

                  <div className="relative z-10 space-y-4">
                    <p className="text-6xl font-black" style={{ color: 'rgba(35,200,130,0.2)' }}>{item.step}</p>
                    <div className="w-14 h-14 rounded-xl flex items-center justify-center" style={{ background: 'linear-gradient(135deg, #23C882 0%, #1aaa6e 100%)' }}>
                      <Icon className="w-7 h-7 text-white" />
                    </div>
                    <h3 className="text-2xl font-bold">{item.title}</h3>
                    <p className="text-muted-foreground leading-relaxed">{item.desc}</p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* FAQ Section */}
        <div className="space-y-6 mt-16">
          <div className="text-center space-y-3">
            <h2 className="text-3xl font-bold bg-gradient-to-r from-emerald-400 to-teal-400 bg-clip-text text-transparent">
              ❓ {t('affiliates.faq')}
            </h2>
          </div>

          <div className="grid md:grid-cols-2 gap-6">
            {[
              {
                question: t('affiliates.faq1Q'),
                answer: t('affiliates.faq1A'),
              },
              {
                question: t('affiliates.faq2Q'),
                answer: t('affiliates.faq2A'),
              },
              {
                question: t('affiliates.faq3Q'),
                answer: t('affiliates.faq3A'),
              },
              {
                question: t('affiliates.faq4Q'),
                answer: t('affiliates.faq4A'),
              },
            ].map((item, idx) => (
              <Card key={idx} className="rounded-2xl hover:shadow-lg transition-all duration-300" style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(35,200,130,0.12)', padding: '1.5rem' }}>
                <CardHeader className="pb-3">
                  <CardTitle className="text-lg font-bold flex items-center gap-2">
                    <Help className="w-5 h-5 text-emerald-400" />
                    {item.question}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-muted-foreground">{item.answer}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

// Helper component for missing icon
const Help = ({ className }: { className?: string }) => (
  <svg className={className} fill="none" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" viewBox="0 0 24 24" stroke="currentColor">
    <path d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
  </svg>
);
