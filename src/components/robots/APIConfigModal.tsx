import { useState, useEffect } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { AlertCircle, CheckCircle2, Copy, Eye, EyeOff, Shield, Zap, ArrowRight, ExternalLink } from 'lucide-react';
import { Robot } from '@/types/robot';

interface APIConfigModalProps {
  robot: Robot | null;
  isOpen: boolean;
  onClose: () => void;
  onConnect: (apiKey: string, apiSecret: string, apiPassword?: string) => void;
}

export function APIConfigModal({ robot, isOpen, onClose, onConnect }: APIConfigModalProps) {
  const [step, setStep] = useState<'guide' | 'input' | 'testing' | 'success'>('guide');
  const [apiKey, setApiKey] = useState('');
  const [apiSecret, setApiSecret] = useState('');
  const [apiPassword, setApiPassword] = useState('');
  const [showSecret, setShowSecret] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [error, setError] = useState('');
  const [copied, setCopied] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      setStep('guide');
      setApiKey('');
      setApiSecret('');
      setApiPassword('');
      setError('');
    }
  }, [isOpen]);

  const copyToClipboard = (text: string, label: string) => {
    navigator.clipboard.writeText(text);
    setCopied(label);
    setTimeout(() => setCopied(null), 2000);
  };

  const handleConnect = async () => {
    if (!apiKey.trim() || !apiSecret.trim()) {
      setError('Chave de API e Senha são obrigatórias');
      return;
    }

    setIsConnecting(true);
    setError('');
    setStep('testing');

    // Simulate API connection test
    setTimeout(() => {
      try {
        // Basic validation
        if (apiKey.length < 20) {
          throw new Error('Chave de API parece inválida (muito curta)');
        }
        if (apiSecret.length < 20) {
          throw new Error('Senha parece inválida (muito curta)');
        }

        // Simulate successful connection
        onConnect(apiKey, apiSecret, apiPassword);
        setStep('success');
        setIsConnecting(false);

        // Auto close after 2 seconds
        setTimeout(() => {
          onClose();
        }, 2000);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Erro ao conectar com a API');
        setStep('input');
        setIsConnecting(false);
      }
    }, 1500);
  };

  if (!robot) return null;

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Shield className="w-5 h-5 text-primary" />
            Conectar API - {robot.name}
          </DialogTitle>
        </DialogHeader>

        {/* Step: Guide */}
        {step === 'guide' && (
          <div className="space-y-6">
            <DialogDescription className="text-base">
              Siga os passos abaixo para conectar sua API da Binance ao robô
            </DialogDescription>

            <div className="space-y-4">
              {/* Step 1 */}
              <div className="bg-primary/10 border border-primary/30 rounded-lg p-4 space-y-3">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-full bg-primary text-white flex items-center justify-center font-bold text-sm">
                    1
                  </div>
                  <h4 className="font-bold text-primary">Acesse as configurações da Binance</h4>
                </div>
                <div className="ml-11 space-y-2 text-sm text-muted-foreground">
                  <p>📱 Vá para: <code className="bg-background/50 px-2 py-1 rounded text-xs">account.binance.com</code></p>
                  <p>🔐 Navegue até: <strong>Segurança → Gerenciamento de API</strong></p>
                </div>
              </div>

              {/* Step 2 */}
              <div className="bg-accent/10 border border-accent/30 rounded-lg p-4 space-y-3">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-full bg-accent text-white flex items-center justify-center font-bold text-sm">
                    2
                  </div>
                  <h4 className="font-bold text-accent">Crie uma nova chave de API</h4>
                </div>
                <div className="ml-11 space-y-2 text-sm text-muted-foreground">
                  <p>✅ Clique em <strong>"Criar API"</strong></p>
                  <p>📝 Escolha um nome (ex: "Pro Trader-EA")</p>
                  <p>🛡️ Restrições recomendadas:</p>
                  <ul className="list-disc list-inside ml-2 text-xs space-y-1 mt-2">
                    <li>Trading spot habilitado</li>
                    <li>IP whitelist: 3.128.0.0/9, 18.130.0.0/16</li>
                    <li>Restringir para o seu IP</li>
                  </ul>
                </div>
              </div>

              {/* Step 3 */}
              <div className="bg-success/10 border border-success/30 rounded-lg p-4 space-y-3">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-full bg-success text-white flex items-center justify-center font-bold text-sm">
                    3
                  </div>
                  <h4 className="font-bold text-success">Cole as credenciais aqui</h4>
                </div>
                <div className="ml-11 space-y-2 text-sm text-muted-foreground">
                  <p>🔑 Copie a <strong>Chave de API</strong> e <strong>Chave Secreta</strong></p>
                  <p>⚠️ Guarde com segurança - nunca compartilhe!</p>
                </div>
              </div>
            </div>

            {/* Warning */}
            <div className="bg-warning/10 border border-warning/30 rounded-lg p-4 flex gap-3">
              <AlertCircle className="w-5 h-5 text-warning flex-shrink-0 mt-0.5" />
              <div className="text-sm space-y-1">
                <p className="font-semibold text-warning">🔒 Segurança em primeiro lugar</p>
                <p className="text-muted-foreground">Suas credenciais são criptografadas e nunca sairão do seu dispositivo. Não compartilhe com ninguém!</p>
              </div>
            </div>

            <DialogFooter>
              <Button variant="outline" onClick={onClose}>
                Cancelar
              </Button>
              <Button onClick={() => setStep('input')} className="gap-2">
                Próximo <ArrowRight className="w-4 h-4" />
              </Button>
            </DialogFooter>
          </div>
        )}

        {/* Step: Input */}
        {step === 'input' && (
          <div className="space-y-6">
            <div className="space-y-4">
              {/* API Key Input */}
              <div className="space-y-2">
                <label className="text-sm font-semibold flex items-center gap-2">
                  <Shield className="w-4 h-4 text-primary" />
                  Chave de API (API Key)
                </label>
                <div className="flex gap-2">
                  <Input
                    type="password"
                    placeholder="Cole sua chave de API aqui..."
                    value={apiKey}
                    onChange={(e) => {
                      setApiKey(e.target.value);
                      setError('');
                    }}
                    className="font-mono text-xs"
                  />
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => copyToClipboard(apiKey, 'apiKey')}
                    disabled={!apiKey}
                  >
                    <Copy className="w-4 h-4" />
                  </Button>
                </div>
                <p className="text-xs text-muted-foreground">Cole a chave pública da sua API</p>
              </div>

              {/* API Secret Input */}
              <div className="space-y-2">
                <label className="text-sm font-semibold flex items-center gap-2">
                  <Shield className="w-4 h-4 text-accent" />
                  Chave Secreta (API Secret)
                </label>
                <div className="flex gap-2">
                  <Input
                    type={showSecret ? 'text' : 'password'}
                    placeholder="Cole sua chave secreta aqui..."
                    value={apiSecret}
                    onChange={(e) => {
                      setApiSecret(e.target.value);
                      setError('');
                    }}
                    className="font-mono text-xs"
                  />
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setShowSecret(!showSecret)}
                  >
                    {showSecret ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </Button>
                </div>
                <p className="text-xs text-muted-foreground">Cole a chave secreta (nunca será compartilhada)</p>
              </div>

              {/* API Password (Optional) */}
              <div className="space-y-2">
                <label className="text-sm font-semibold flex items-center gap-2">
                  <Shield className="w-4 h-4 text-muted-foreground" />
                  Senha de API (Opcional)
                </label>
                <Input
                  type="password"
                  placeholder="Sua senha de API (se tiver)"
                  value={apiPassword}
                  onChange={(e) => setApiPassword(e.target.value)}
                  className="font-mono text-xs"
                />
                <p className="text-xs text-muted-foreground">Deixe em branco se não tiver configurado</p>
              </div>

              {/* Error Message */}
              {error && (
                <div className="bg-destructive/10 border border-destructive/30 rounded-lg p-3 flex gap-2">
                  <AlertCircle className="w-5 h-5 text-destructive flex-shrink-0" />
                  <p className="text-sm text-destructive">{error}</p>
                </div>
              )}
            </div>

            <DialogFooter>
              <Button variant="outline" onClick={() => setStep('guide')}>
                Voltar
              </Button>
              <Button
                onClick={handleConnect}
                disabled={!apiKey.trim() || !apiSecret.trim() || isConnecting}
                className="gap-2 bg-gradient-to-r from-primary to-accent"
              >
                <Zap className="w-4 h-4" />
                {isConnecting ? 'Testando conexão...' : 'Conectar'}
              </Button>
            </DialogFooter>
          </div>
        )}

        {/* Step: Testing */}
        {step === 'testing' && (
          <div className="space-y-6 py-8">
            <div className="flex flex-col items-center gap-4">
              <div className="w-16 h-16 rounded-full bg-primary/20 flex items-center justify-center animate-spin">
                <div className="w-14 h-14 rounded-full bg-primary/30 flex items-center justify-center">
                  <Zap className="w-6 h-6 text-primary animate-pulse" />
                </div>
              </div>
              <h3 className="text-lg font-bold">Testando Conexão...</h3>
              <p className="text-sm text-muted-foreground text-center">
                Validando suas credenciais e conectando ao servidor da Binance
              </p>
            </div>
          </div>
        )}

        {/* Step: Success */}
        {step === 'success' && (
          <div className="space-y-6 py-8">
            <div className="flex flex-col items-center gap-4">
              <div className="w-16 h-16 rounded-full bg-success/20 flex items-center justify-center">
                <CheckCircle2 className="w-8 h-8 text-success" />
              </div>
              <h3 className="text-lg font-bold">Conectado com Sucesso! ✅</h3>
              <p className="text-sm text-muted-foreground text-center">
                Seu robô {robot.name} foi conectado à Binance e está pronto para operar
              </p>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
