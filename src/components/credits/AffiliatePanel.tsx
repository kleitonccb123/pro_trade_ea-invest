/**
 * AffiliatePanel Component
 * Displays referral link, tier badges, and commission statistics
 * Gamified visual with confetti on milestone achievements
 */

import React, { useState } from 'react';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import {
  Copy,
  CheckCircle2,
  Share2,
  TrendingUp,
  Users,
  DollarSign,
  Crown,
  Award,
  Zap,
} from 'lucide-react';
import ConfettiExplosion from 'react-confetti-explosion';

interface AffiliatePanelProps {
  referralCode: string;
  referralLink: string;
  referredUsersCount: number;
  commissionEarned: number;
  tier: 'bronze' | 'silver' | 'gold' | 'platinum';
  nextTierAt?: number;
  onShareClick?: () => void;
}

const TIER_CONFIG = {
  bronze: {
    label: 'Bronze',
    color: 'bg-amber-100 text-amber-900 border-amber-300',
    icon: Award,
    minReferrals: 0,
    commission: 0.1,
    badge: '🥉',
  },
  silver: {
    label: 'Silver',
    color: 'bg-slate-100 text-slate-900 border-slate-300',
    icon: TrendingUp,
    minReferrals: 5,
    commission: 0.15,
    badge: '🥈',
  },
  gold: {
    label: 'Gold',
    color: 'bg-yellow-100 text-yellow-900 border-yellow-300',
    icon: Crown,
    minReferrals: 15,
    commission: 0.2,
    badge: '🏆',
  },
  platinum: {
    label: 'Platinum',
    color: 'bg-purple-100 text-purple-900 border-purple-300',
    icon: Zap,
    minReferrals: 50,
    commission: 0.25,
    badge: '💎',
  },
};

export const AffiliatePanel: React.FC<AffiliatePanelProps> = ({
  referralCode,
  referralLink,
  referredUsersCount,
  commissionEarned,
  tier,
  nextTierAt = 50,
  onShareClick,
}) => {
  const [copied, setCopied] = useState(false);
  const [showConfetti, setShowConfetti] = useState(false);
  const tierConfig = TIER_CONFIG[tier];
  const TierIcon = tierConfig.icon;

  const progressToNextTier =
    tier === 'platinum'
      ? 100
      : ((referredUsersCount - TIER_CONFIG[tier].minReferrals) /
          (nextTierAt - TIER_CONFIG[tier].minReferrals)) *
        100;

  const handleCopyLink = () => {
    navigator.clipboard.writeText(referralLink);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleShareClick = () => {
    if (onShareClick) {
      onShareClick();
    } else {
      // Default share behavior
      const text = `Junte-se a mim no Crypto Trade Hub! Use meu código de referência: ${referralCode}`;
      if (navigator.share) {
        navigator.share({
          title: 'Crypto Trade Hub',
          text: text,
          url: referralLink,
        });
      }
    }
  };

  const potentialEarnings = referredUsersCount * tierConfig.commission * 100; // Assuming $100 base

  return (
    <TooltipProvider>
      <Card className="border-l-4 border-purple-400">
        {showConfetti && <ConfettiExplosion particleCount={50} force={0.8} />}

        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Share2 className="w-5 h-5 text-purple-600" />
              <CardTitle className="text-lg">Programa de Afiliados</CardTitle>
            </div>
            <Badge className={tierConfig.color} variant="secondary">
              {tierConfig.badge} {tierConfig.label}
            </Badge>
          </div>
          <CardDescription>
            Ganhe com cada referência bem-sucedida
          </CardDescription>
        </CardHeader>

        <CardContent className="space-y-4">
          {/* Referral Code & Link */}
          <div className="space-y-2">
            <label className="text-xs font-semibold text-gray-700">
              Seu Código de Referência
            </label>
            <div className="flex gap-2">
              <div className="flex-1 px-3 py-2 bg-gray-100 rounded-lg border border-gray-300 font-mono text-sm">
                {referralCode}
              </div>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    onClick={handleCopyLink}
                    variant="outline"
                    size="sm"
                  >
                    {copied ? (
                      <CheckCircle2 className="w-4 h-4 text-green-600" />
                    ) : (
                      <Copy className="w-4 h-4" />
                    )}
                  </Button>
                </TooltipTrigger>
                <TooltipContent>
                  {copied ? 'Copiado!' : 'Copiar link de referência'}
                </TooltipContent>
              </Tooltip>
            </div>
          </div>

          {/* Share Button */}
          <Button
            onClick={handleShareClick}
            variant="default"
            className="w-full bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700"
          >
            <Share2 className="w-4 h-4 mr-2" />
            Compartilhar Link
          </Button>

          {/* Tier Progress */}
          <div className="space-y-3 p-3 bg-gradient-to-br from-purple-50 to-pink-50 rounded-lg border border-purple-200">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <TierIcon className="w-5 h-5 text-purple-600" />
                <span className="text-sm font-semibold text-gray-900">
                  Progresso do Nível
                </span>
              </div>
              {tier !== 'platinum' && (
                <span className="text-xs text-gray-600">
                  {referredUsersCount} / {nextTierAt} usuários
                </span>
              )}
            </div>

            {/* Progress Bar */}
            {tier !== 'platinum' && (
              <div className="w-full h-2 bg-gray-200 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-purple-500 to-pink-500 transition-all duration-500"
                  style={{ width: `${Math.min(progressToNextTier, 100)}%` }}
                />
              </div>
            )}

            {tier === 'platinum' && (
              <div className="text-center py-2">
                <p className="text-sm font-bold text-purple-900">
                  ✨ Nível Máximo Atingido!
                </p>
                <p className="text-xs text-purple-800">
                  Você está no topo do programa de afiliados
                </p>
              </div>
            )}
          </div>

          {/* Stats Grid */}
          <div className="grid grid-cols-2 gap-3">
            {/* Referred Users */}
            <div className="p-3 bg-blue-50 rounded-lg border border-blue-200">
              <div className="flex items-center gap-2 mb-1">
                <Users className="w-4 h-4 text-blue-600" />
                <span className="text-xs text-blue-900 font-semibold">
                  Referências
                </span>
              </div>
              <p className="text-2xl font-bold text-blue-900">
                {referredUsersCount}
              </p>
              <p className="text-xs text-blue-800 mt-1">usuários ativos</p>
            </div>

            {/* Commission Earned */}
            <div className="p-3 bg-green-50 rounded-lg border border-green-200">
              <div className="flex items-center gap-2 mb-1">
                <DollarSign className="w-4 h-4 text-green-600" />
                <span className="text-xs text-green-900 font-semibold">
                  Ganhos
                </span>
              </div>
              <p className="text-2xl font-bold text-green-900">
                ${commissionEarned.toFixed(2)}
              </p>
              <p className="text-xs text-green-800 mt-1">comissões acumuladas</p>
            </div>
          </div>

          {/* Commission Rate */}
          <div className="p-3 bg-gray-50 rounded-lg border border-gray-200">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-semibold text-gray-700">
                Taxa de Comissão Atual
              </span>
              <span className="text-sm font-bold text-gray-900">
                {(tierConfig.commission * 100).toFixed(1)}%
              </span>
            </div>
            <p className="text-xs text-gray-600">
              Ganhe <strong>${(tierConfig.commission * 100).toFixed(2)}</strong> para cada
              referência bem-sucedida de $100.
            </p>
          </div>

          {/* Potential Earnings */}
          <div className="p-3 bg-yellow-50 rounded-lg border border-yellow-200">
            <div className="flex items-start gap-2">
              <TrendingUp className="w-4 h-4 text-yellow-600 flex-shrink-0 mt-0.5" />
              <div className="flex-1">
                <p className="text-xs font-semibold text-yellow-900 mb-1">
                  Potencial de Ganho Mensal
                </p>
                <p className="text-sm text-yellow-900">
                  ~${potentialEarnings.toFixed(2)}/mês com suas referências atuais
                </p>
                <p className="text-xs text-yellow-800 mt-1">
                  (Baseado em $100 por conversão)
                </p>
              </div>
            </div>
          </div>

          {/* Tier Progression Info */}
          {tier !== 'platinum' && (
            <div className="p-3 bg-blue-50 rounded-lg border border-blue-200">
              <p className="text-xs font-semibold text-blue-900 mb-2">
                Próximo Nível: {TIER_CONFIG[Object.keys(TIER_CONFIG).find(k => k !== tier && TIER_CONFIG[k as keyof typeof TIER_CONFIG].minReferrals > TIER_CONFIG[tier].minReferrals) as keyof typeof TIER_CONFIG]?.label}
              </p>
              <p className="text-xs text-blue-800">
                Você precisa de{' '}
                <strong>
                  {nextTierAt - referredUsersCount} mais{' '}
                  {nextTierAt - referredUsersCount === 1
                    ? 'referência'
                    : 'referências'}
                </strong>{' '}
                para subir de nível e ganhar comissões maiores.
              </p>
            </div>
          )}

          {/* Pro Tip */}
          <div className="p-3 bg-purple-50 rounded-lg border border-purple-200">
            <p className="text-xs text-purple-900">
              💡 <strong>Dica:</strong> Compartilhe seu link em comunidades de
              traders! Quanto mais referências, maior sua comissão.
            </p>
          </div>
        </CardContent>
      </Card>
    </TooltipProvider>
  );
};

export default AffiliatePanel;
