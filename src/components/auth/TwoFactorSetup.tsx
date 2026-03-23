/**
 * TwoFactorSetup - Configuração inicial do 2FA
 * 
 * Features:
 * - QR Code para Google Authenticator
 * - Confirmação com código TOTP
 * - Exibição de Backup Codes
 */

import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Shield, Copy, Check, Loader2, AlertCircle, Download, QrCode } from 'lucide-react';
import { InputOTP, InputOTPGroup, InputOTPSlot, InputOTPSeparator } from '@/components/ui/input-otp';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import { useToast } from '@/hooks/use-toast';
import useApi from '@/hooks/useApi';

interface SetupResponse {
  secret: string;
  qr_code_url: string;
  backup_codes: string[];
}

interface TwoFactorSetupProps {
  isOpen: boolean;
  onClose: () => void;
  onComplete?: () => void;
}

export default function TwoFactorSetup({ isOpen, onClose, onComplete }: TwoFactorSetupProps) {
  const navigate = useNavigate();
  const { toast } = useToast();
  const api = useApi();

  // State
  const [step, setStep] = useState<'setup' | 'verify' | 'backup'>('setup');
  const [setupData, setSetupData] = useState<SetupResponse | null>(null);
  const [verifyCode, setVerifyCode] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copiedSecret, setCopiedSecret] = useState(false);
  const [copiedBackup, setCopiedBackup] = useState(false);

  // Fetch setup data when modal opens
  useEffect(() => {
    if (isOpen && !setupData) {
      initSetup();
    }
  }, [isOpen]);

  const initSetup = async () => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await api.post<SetupResponse>('/auth/2fa/setup');
      setSetupData(response);
      setStep('setup');
    } catch (err: any) {
      setError(err.message || 'Falha ao iniciar configuração 2FA');
    } finally {
      setIsLoading(false);
    }
  };

  const handleVerify = async () => {
    if (verifyCode.length !== 6) {
      setError('Digite o código completo de 6 dígitos');
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      await api.post('/auth/2fa/confirm', {
        code: verifyCode,
      });

      toast({
        title: '✅ 2FA Ativado',
        description: 'Autenticação em duas etapas configurada com sucesso!',
      });

      setStep('backup');
    } catch (err: any) {
      setError(err.message || 'Código inválido. Verifique e tente novamente.');
      setVerifyCode('');
    } finally {
      setIsLoading(false);
    }
  };

  const copyToClipboard = async (text: string, type: 'secret' | 'backup') => {
    try {
      await navigator.clipboard.writeText(text);
      if (type === 'secret') {
        setCopiedSecret(true);
        setTimeout(() => setCopiedSecret(false), 2000);
      } else {
        setCopiedBackup(true);
        setTimeout(() => setCopiedBackup(false), 2000);
      }
      toast({
        title: 'Copiado!',
        description: type === 'secret' ? 'Chave copiada para a área de transferência' : 'Códigos copiados!',
      });
    } catch (err) {
      toast({
        title: 'Erro',
        description: 'Não foi possível copiar',
        variant: 'destructive',
      });
    }
  };

  const downloadBackupCodes = () => {
    if (!setupData?.backup_codes) return;
    
    const content = `CRYPTO TRADE HUB - BACKUP CODES
==============================
Guarde estes códigos em um local seguro.
Cada código pode ser usado apenas UMA vez.

${setupData.backup_codes.map((code, i) => `${i + 1}. ${code}`).join('\n')}

Gerado em: ${new Date().toLocaleString()}
==============================
AVISO: Não compartilhe estes códigos!`;

    const blob = new Blob([content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'pro-trader-ea-backup-codes.txt';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    toast({
      title: '📥 Download Iniciado',
      description: 'Guarde o arquivo em um local seguro!',
    });
  };

  const handleComplete = () => {
    onClose();
    if (onComplete) {
      onComplete();
    }
  };

  // Auto-verify when OTP complete
  useEffect(() => {
    if (verifyCode.length === 6 && step === 'verify' && !isLoading) {
      handleVerify();
    }
  }, [verifyCode, step]);

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-lg bg-slate-900 border-slate-800 text-white">
        <DialogHeader>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-gradient-to-br from-blue-600 to-purple-600 flex items-center justify-center">
              <Shield className="w-5 h-5" />
            </div>
            <div>
              <DialogTitle className="text-xl">Configurar 2FA</DialogTitle>
              <DialogDescription className="text-slate-400">
                Adicione uma camada extra de segurança
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>

        {/* Error Alert */}
        {error && (
          <Alert variant="destructive" className="bg-red-500/10 border-red-500/30">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {/* Loading State */}
        {isLoading && step === 'setup' && !setupData && (
          <div className="flex flex-col items-center py-12">
            <Loader2 className="w-12 h-12 animate-spin text-blue-500 mb-4" />
            <p className="text-slate-400">Gerando configuração...</p>
          </div>
        )}

        {/* Step 1: Setup - Show QR Code */}
        {step === 'setup' && setupData && (
          <div className="space-y-6">
            <div className="text-center space-y-4">
              <p className="text-sm text-slate-400">
                Escaneie o QR Code com o Google Authenticator
              </p>
              
              {/* QR Code */}
              <div className="flex justify-center">
                <div className="bg-white p-4 rounded-lg">
                  <img 
                    src={setupData.qr_code_url} 
                    alt="QR Code 2FA" 
                    className="w-48 h-48"
                  />
                </div>
              </div>

              {/* Manual Entry */}
              <div className="bg-slate-800 rounded-lg p-4 space-y-2">
                <p className="text-xs text-slate-400">Ou digite manualmente:</p>
                <div className="flex items-center gap-2">
                  <code className="flex-1 bg-slate-700 px-3 py-2 rounded text-sm font-mono text-blue-400 break-all">
                    {setupData.secret}
                  </code>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => copyToClipboard(setupData.secret, 'secret')}
                    className="hover:bg-slate-700"
                  >
                    {copiedSecret ? <Check className="w-4 h-4 text-green-500" /> : <Copy className="w-4 h-4" />}
                  </Button>
                </div>
              </div>
            </div>

            <Button
              onClick={() => setStep('verify')}
              className="w-full bg-gradient-to-r from-blue-600 to-purple-600"
            >
              Próximo: Verificar Código
            </Button>
          </div>
        )}

        {/* Step 2: Verify */}
        {step === 'verify' && (
          <div className="space-y-6">
            <div className="text-center space-y-4">
              <p className="text-sm text-slate-400">
                Digite o código de 6 dígitos do seu app autenticador
              </p>

              <div className="flex justify-center">
                <InputOTP
                  value={verifyCode}
                  onChange={setVerifyCode}
                  maxLength={6}
                  disabled={isLoading}
                >
                  <InputOTPGroup>
                    <InputOTPSlot index={0} className="bg-slate-800 border-slate-700 text-white text-xl w-12 h-14" />
                    <InputOTPSlot index={1} className="bg-slate-800 border-slate-700 text-white text-xl w-12 h-14" />
                    <InputOTPSlot index={2} className="bg-slate-800 border-slate-700 text-white text-xl w-12 h-14" />
                  </InputOTPGroup>
                  <InputOTPSeparator className="text-slate-600" />
                  <InputOTPGroup>
                    <InputOTPSlot index={3} className="bg-slate-800 border-slate-700 text-white text-xl w-12 h-14" />
                    <InputOTPSlot index={4} className="bg-slate-800 border-slate-700 text-white text-xl w-12 h-14" />
                    <InputOTPSlot index={5} className="bg-slate-800 border-slate-700 text-white text-xl w-12 h-14" />
                  </InputOTPGroup>
                </InputOTP>
              </div>
            </div>

            <div className="flex gap-3">
              <Button
                variant="outline"
                onClick={() => setStep('setup')}
                className="flex-1 border-slate-700 hover:bg-slate-800"
              >
                Voltar
              </Button>
              <Button
                onClick={handleVerify}
                disabled={verifyCode.length !== 6 || isLoading}
                className="flex-1 bg-gradient-to-r from-blue-600 to-purple-600"
              >
                {isLoading ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    Verificando...
                  </>
                ) : (
                  'Verificar'
                )}
              </Button>
            </div>
          </div>
        )}

        {/* Step 3: Backup Codes */}
        {step === 'backup' && setupData && (
          <div className="space-y-6">
            <Alert className="bg-yellow-500/10 border-yellow-500/30">
              <AlertCircle className="h-4 w-4 text-yellow-500" />
              <AlertDescription className="text-yellow-400">
                <strong>IMPORTANTE:</strong> Salve estes códigos de backup em um local seguro. 
                Você precisará deles se perder acesso ao app autenticador.
              </AlertDescription>
            </Alert>

            <div className="bg-slate-800 rounded-lg p-4">
              <div className="grid grid-cols-2 gap-2">
                {setupData.backup_codes.map((code, index) => (
                  <div key={index} className="bg-slate-700 px-3 py-2 rounded font-mono text-sm text-center">
                    {code}
                  </div>
                ))}
              </div>
            </div>

            <div className="flex gap-3">
              <Button
                variant="outline"
                onClick={() => copyToClipboard(setupData.backup_codes.join('\n'), 'backup')}
                className="flex-1 border-slate-700 hover:bg-slate-800"
              >
                {copiedBackup ? <Check className="w-4 h-4 mr-2" /> : <Copy className="w-4 h-4 mr-2" />}
                Copiar
              </Button>
              <Button
                variant="outline"
                onClick={downloadBackupCodes}
                className="flex-1 border-slate-700 hover:bg-slate-800"
              >
                <Download className="w-4 h-4 mr-2" />
                Download
              </Button>
            </div>

            <Button
              onClick={handleComplete}
              className="w-full bg-gradient-to-r from-green-600 to-emerald-600"
            >
              Concluir Configuração
            </Button>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

export { TwoFactorSetup };
