import React, { useState } from 'react';
import { Dialog, DialogContent } from '@/components/ui/dialog';
import { ArrowRight } from 'lucide-react';

interface RegistrationModalProps {
  isOpen: boolean;
  onClose: () => void;
  onAnswer: (hasAccount: boolean) => void;
}

export default function RegistrationModal({ isOpen, onClose, onAnswer }: RegistrationModalProps) {
  const [isAnimating, setIsAnimating] = useState(false);

  const handleCreateAccount = () => {
    setIsAnimating(true);
    setTimeout(() => {
      onAnswer(false);
      onClose();
      setIsAnimating(false);
    }, 300);
  };

  const handleHasAccount = () => {
    setIsAnimating(true);
    setTimeout(() => {
      onAnswer(true);
      onClose();
      setIsAnimating(false);
    }, 300);
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-sm bg-gradient-to-br from-slate-950 via-slate-900 to-black border border-emerald-500/50 shadow-2xl overflow-hidden p-8">
        {/* Decorative Background Elements */}
        <div className="absolute top-0 right-0 w-32 h-32 bg-emerald-500/10 rounded-full blur-3xl"></div>
        <div className="absolute bottom-0 left-0 w-32 h-32 bg-emerald-500/5 rounded-full blur-3xl"></div>

        <div className="relative z-10 text-center space-y-8">
          {/* Header */}
          <div className="space-y-2">
            <div className="text-5xl">🇺🇸</div>
            <h2 className="text-2xl font-bold bg-gradient-to-r from-emerald-400 to-teal-300 bg-clip-text text-transparent">
              Conectar KuCoin
            </h2>
            <p className="text-slate-300 text-sm">
              Comece a usar os robôs de trading agora
            </p>
          </div>

          {/* Main CTA Button */}
          <a
            href="https://www.kucoin.com/ucenter/signup"
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => {
              e.preventDefault();
              window.open('https://www.kucoin.com/ucenter/signup', '_blank');
              handleCreateAccount();
            }}
            className="group relative block w-full"
          >
            <button
              className={`w-full bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-400 hover:to-teal-500 text-white font-bold py-4 px-6 rounded-xl transition-all duration-300 transform hover:scale-105 hover:shadow-2xl hover:shadow-emerald-500/50 active:scale-95 flex items-center justify-center gap-3 ${
                isAnimating ? 'scale-105 shadow-2xl shadow-emerald-500/50' : ''
              }`}
            >
              <span className="text-lg">➕</span>
              <span>Criar Conta KuCoin</span>
              <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
            </button>
          </a>

          {/* Secondary Link */}
          <button
            onClick={handleHasAccount}
            className="text-sm text-emerald-500/70 hover:text-emerald-400 transition-colors font-medium underline decoration-dashed"
          >
            Já tenho minha conta
          </button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
