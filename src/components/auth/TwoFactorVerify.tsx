/**
 * TwoFactorVerify - Componente de Verificação 2FA
 * 
 * Features:
 * - Input OTP de 6 dígitos (Shadcn/UI)
 * - Verificação via POST /auth/2fa/verify
 * - Suporte a Backup Codes
 * - Redirect para Dashboard após sucesso
 * - Layout responsivo
 */

import { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Shield, KeyRound, Smartphone, AlertCircle, Loader2, ArrowLeft, RefreshCw } from 'lucide-react';
import { InputOTP, InputOTPGroup, InputOTPSlot, InputOTPSeparator } from '@/components/ui/input-otp';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useToast } from '@/hooks/use-toast';
import useApi from '@/hooks/useApi';
import { useAuthStore } from '@/context/AuthContext';

interface TwoFactorVerifyProps {
  onSuccess?: () => void;
  onCancel?: () => void;
}

interface VerifyResponse {
  access_token: string;
  token_type: string;
  message?: string;
}

interface LocationState {
  tempToken?: string;
  email?: string;
  requires2FA?: boolean;
}

export default function TwoFactorVerify({ onSuccess, onCancel }: TwoFactorVerifyProps) {
  const navigate = useNavigate();
  const location = useLocation();
  const { toast } = useToast();
  const api = useApi();
  const { setTokens, checkAuth } = useAuthStore();
  
  // Get temp token from location state (passed from login)
  const locationState = location.state as LocationState;
  const tempToken = locationState?.tempToken;
  const userEmail = locationState?.email;
  
  // State
  const [otpCode, setOtpCode] = useState('');
  const [backupCode, setBackupCode] = useState('');
  const [isVerifying, setIsVerifying] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [attemptsLeft, setAttemptsLeft] = useState(5);
  const [isLocked, setIsLocked] = useState(false);
  const [lockoutTime, setLockoutTime] = useState(0);
  const [activeTab, setActiveTab] = useState<'totp' | 'backup'>('totp');

  // Redirect if no temp token
  useEffect(() => {
    if (!tempToken) {
      toast({
        title: 'Acesso Negado',
        description: 'Faça login primeiro para verificar o 2FA.',
        variant: 'destructive',
      });
      navigate('/login');
    }
  }, [tempToken, navigate, toast]);

  // Lockout timer
  useEffect(() => {
    if (lockoutTime > 0) {
      const timer = setInterval(() => {
        setLockoutTime((prev) => {
          if (prev <= 1) {
            setIsLocked(false);
            setAttemptsLeft(5);
            return 0;
          }
          return prev - 1;
        });
      }, 1000);
      return () => clearInterval(timer);
    }
  }, [lockoutTime]);

  // Auto-submit when OTP is complete
  useEffect(() => {
    if (otpCode.length === 6 && !isVerifying && !isLocked) {
      handleVerifyTotp();
    }
  }, [otpCode]);

  const handleVerifyTotp = async () => {
    if (otpCode.length !== 6) {
      setError('Digite o código completo de 6 dígitos');
      return;
    }

    if (isLocked) {
      setError(`Conta bloqueada. Tente novamente em ${lockoutTime} segundos.`);
      return;
    }

    setIsVerifying(true);
    setError(null);

    try {
      const response = await api.post<VerifyResponse>('/auth/2fa/complete', {
        pending_token: tempToken,
        code: otpCode,
      });

      // Success - save the final access token via auth store
      setTokens(response.access_token, '');
      await checkAuth();
      
      toast({
        title: '✅ Verificação Concluída',
        description: 'Login realizado com sucesso!',
      });

      // Callback or redirect
      if (onSuccess) {
        onSuccess();
      } else {
        navigate('/dashboard');
      }
    } catch (err: any) {
      const remaining = err.attempts_remaining ?? attemptsLeft - 1;
      setAttemptsLeft(remaining);
      
      if (remaining <= 0 || err.locked) {
        setIsLocked(true);
        setLockoutTime(err.lockout_seconds || 900); // 15 min default
        setError('Muitas tentativas incorretas. Conta bloqueada temporariamente.');
      } else {
        setError(err.message || 'Código inválido. Verifique e tente novamente.');
      }
      
      setOtpCode('');
    } finally {
      setIsVerifying(false);
    }
  };

  const handleVerifyBackup = async () => {
    // Normalize backup code format (XXXX-XXXX)
    const normalizedCode = backupCode.toUpperCase().replace(/[^A-Z0-9]/g, '');
    
    if (normalizedCode.length !== 8) {
      setError('Código de backup deve ter 8 caracteres (formato: XXXX-XXXX)');
      return;
    }

    setIsVerifying(true);
    setError(null);

    try {
      const formattedCode = normalizedCode.slice(0, 4) + '-' + normalizedCode.slice(4);
      const response = await api.post<VerifyResponse>('/auth/2fa/complete', {
        pending_token: tempToken,
        code: formattedCode,
      });

      // Success
      setTokens(response.access_token, '');
      await checkAuth();
      
      toast({
        title: '✅ Backup Code Usado',
        description: 'Login realizado. Considere gerar novos códigos de backup.',
        duration: 5000,
      });

      if (onSuccess) {
        onSuccess();
      } else {
        navigate('/dashboard');
      }
    } catch (err: any) {
      setError(err.message || 'Código de backup inválido ou já utilizado.');
      setBackupCode('');
    } finally {
      setIsVerifying(false);
    }
  };

  const handleCancel = () => {
    if (onCancel) {
      onCancel();
    } else {
      // Clear temp token and go back to login
      navigate('/login');
    }
  };

  const formatLockoutTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 p-4">
      {/* Background effects */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-blue-600/10 rounded-full blur-3xl"></div>
        <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-purple-600/10 rounded-full blur-3xl"></div>
      </div>

      <Card className="w-full max-w-md relative z-10 bg-slate-900/80 border-slate-800 backdrop-blur-xl">
        <CardHeader className="text-center space-y-4">
          <div className="mx-auto w-16 h-16 rounded-full bg-gradient-to-br from-blue-600 to-purple-600 flex items-center justify-center">
            <Shield className="w-8 h-8 text-white" />
          </div>
          <div>
            <CardTitle className="text-2xl font-bold text-white">Verificação em Duas Etapas</CardTitle>
            <CardDescription className="text-slate-400 mt-2">
              {userEmail ? `Verificando: ${userEmail}` : 'Digite o código do seu aplicativo autenticador'}
            </CardDescription>
          </div>
        </CardHeader>

        <CardContent className="space-y-6">
          {/* Error Alert */}
          {error && (
            <Alert variant="destructive" className="bg-red-500/10 border-red-500/30">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {/* Lockout Warning */}
          {isLocked && (
            <Alert className="bg-yellow-500/10 border-yellow-500/30 text-yellow-500">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>
                Conta bloqueada por {formatLockoutTime(lockoutTime)}
              </AlertDescription>
            </Alert>
          )}

          <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as 'totp' | 'backup')}>
            <TabsList className="grid w-full grid-cols-2 bg-slate-800">
              <TabsTrigger value="totp" className="data-[state=active]:bg-blue-600">
                <Smartphone className="w-4 h-4 mr-2" />
                App
              </TabsTrigger>
              <TabsTrigger value="backup" className="data-[state=active]:bg-blue-600">
                <KeyRound className="w-4 h-4 mr-2" />
                Backup
              </TabsTrigger>
            </TabsList>

            {/* TOTP Tab */}
            <TabsContent value="totp" className="space-y-6 mt-6">
              <div className="flex flex-col items-center space-y-4">
                <p className="text-sm text-slate-400 text-center">
                  Abra o Google Authenticator e digite o código de 6 dígitos
                </p>
                
                <InputOTP
                  value={otpCode}
                  onChange={setOtpCode}
                  maxLength={6}
                  disabled={isVerifying || isLocked}
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

                {/* Attempts remaining */}
                {attemptsLeft < 5 && !isLocked && (
                  <p className="text-xs text-yellow-500">
                    {attemptsLeft} tentativa{attemptsLeft !== 1 ? 's' : ''} restante{attemptsLeft !== 1 ? 's' : ''}
                  </p>
                )}

                <Button
                  onClick={handleVerifyTotp}
                  disabled={otpCode.length !== 6 || isVerifying || isLocked}
                  className="w-full bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700"
                >
                  {isVerifying ? (
                    <>
                      <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      Verificando...
                    </>
                  ) : (
                    'Verificar Código'
                  )}
                </Button>
              </div>
            </TabsContent>

            {/* Backup Code Tab */}
            <TabsContent value="backup" className="space-y-6 mt-6">
              <div className="space-y-4">
                <p className="text-sm text-slate-400 text-center">
                  Perdeu acesso ao app? Use um código de backup (formato: XXXX-XXXX)
                </p>
                
                <Input
                  value={backupCode}
                  onChange={(e) => setBackupCode(e.target.value.toUpperCase())}
                  placeholder="XXXX-XXXX"
                  maxLength={9}
                  disabled={isVerifying || isLocked}
                  className="bg-slate-800 border-slate-700 text-white text-center text-xl tracking-widest font-mono"
                />

                <Alert className="bg-slate-800/50 border-slate-700">
                  <AlertCircle className="h-4 w-4 text-slate-400" />
                  <AlertDescription className="text-slate-400 text-xs">
                    Cada código de backup pode ser usado apenas uma vez. 
                    Após usar, recomendamos configurar novos códigos.
                  </AlertDescription>
                </Alert>

                <Button
                  onClick={handleVerifyBackup}
                  disabled={backupCode.replace(/[^A-Z0-9]/g, '').length !== 8 || isVerifying || isLocked}
                  className="w-full bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700"
                >
                  {isVerifying ? (
                    <>
                      <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      Verificando...
                    </>
                  ) : (
                    'Usar Código de Backup'
                  )}
                </Button>
              </div>
            </TabsContent>
          </Tabs>
        </CardContent>

        <CardFooter className="flex flex-col space-y-3">
          <Button
            variant="ghost"
            onClick={handleCancel}
            className="w-full text-slate-400 hover:text-white hover:bg-slate-800"
          >
            <ArrowLeft className="w-4 h-4 mr-2" />
            Voltar ao Login
          </Button>
          
          <p className="text-xs text-slate-500 text-center">
            Problemas com 2FA? Entre em contato com o suporte.
          </p>
        </CardFooter>
      </Card>
    </div>
  );
}
