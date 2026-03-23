import React, { useState } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { 
  Plus, 
  Settings, 
  CheckCircle, 
  AlertCircle, 
  Wifi, 
  WifiOff,
  Eye,
  EyeOff,
  Key,
  Globe,
  Coins
} from 'lucide-react';
import { SUPPORTED_EXCHANGES, getExchangeById, getExchangesByType } from '@/lib/exchanges';
import { Exchange, ExchangeCredentials, ExchangeConnection } from '@/types/exchange';

interface ExchangeManagerProps {
  connections?: ExchangeConnection[];
  onAddConnection?: (credentials: ExchangeCredentials) => void;
  onRemoveConnection?: (exchangeId: string) => void;
  onTestConnection?: (exchangeId: string) => Promise<boolean>;
  marketType?: 'crypto';
}

export function ExchangeManager({ 
  connections = [],
  onAddConnection,
  onRemoveConnection,
  onTestConnection,
  marketType = 'crypto'
}: ExchangeManagerProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [selectedExchange, setSelectedExchange] = useState<Exchange | null>(null);
  const [showPassword, setShowPassword] = useState(false);
  const [credentials, setCredentials] = useState<Partial<ExchangeCredentials>>({
    exchangeId: '',
    apiKey: '',
    apiSecret: '',
    passphrase: '',
    sandbox: false
  });

  // Filtrar exchanges por tipo - apenas crypto
  const availableExchanges = getExchangesByType('crypto');

  const handleSubmit = () => {
    if (!credentials.exchangeId || !credentials.apiKey || !credentials.apiSecret) {
      return;
    }

    onAddConnection?.(credentials as ExchangeCredentials);
    
    // Reset form
    setCredentials({
      exchangeId: '',
      apiKey: '',
      apiSecret: '',
      passphrase: '',
      sandbox: false
    });
    setSelectedExchange(null);
    setIsOpen(false);
  };

  // Usar apenas exchanges de crypto
  const filteredExchanges = availableExchanges;

  const selectExchange = (exchange: Exchange) => {
    setSelectedExchange(exchange);
    setCredentials(prev => ({ ...prev, exchangeId: exchange.id }));
  };

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold">Conexões de Exchange</h2>
          <p className="text-sm text-muted-foreground">
            Gerencie suas conexões com exchanges de criptomoedas
          </p>
        </div>
        <Dialog open={isOpen} onOpenChange={setIsOpen}>
          <DialogTrigger asChild>
            <Button variant="premium">
              <Plus className="w-4 h-4 mr-2" />
              Adicionar Exchange
            </Button>
          </DialogTrigger>
          
          <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>Conectar Nova Exchange</DialogTitle>
            </DialogHeader>

            {/* Lista de Exchanges */}
            {!selectedExchange && (
              <div className="space-y-4">
                <h3 className="font-medium">Selecione uma Exchange</h3>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  {filteredExchanges.map((exchange) => (
                    <Card 
                      key={exchange.id} 
                      className={`cursor-pointer transition-all hover:border-primary/50 ${
                        connections.some(c => c.exchange.id === exchange.id) 
                          ? 'opacity-50 pointer-events-none' 
                          : ''
                      }`}
                      onClick={() => selectExchange(exchange)}
                    >
                      <CardContent className="p-4 text-center">
                        <div className="w-12 h-12 mx-auto mb-2 bg-muted rounded-lg flex items-center justify-center">
                          {/* Ícone de cripto */}
                          <Coins className="w-6 h-6 text-orange-600" />
                        </div>
                        <p className="font-medium text-sm">{exchange.displayName}</p>
                        <p className="text-xs text-muted-foreground mb-2">
                          Exchange Cripto
                        </p>
                        <div className="flex justify-center">
                          <Badge variant="outline" className="text-xs">
                            {(exchange.fees.taker * 100).toFixed(3)}% fee
                          </Badge>
                        </div>
                        {connections.some(c => c.exchange.id === exchange.id) && (
                          <div className="flex items-center justify-center mt-2">
                            <CheckCircle className="w-4 h-4 text-green-600 mr-1" />
                            <span className="text-xs text-green-600">Conectado</span>
                          </div>
                        )}
                      </CardContent>
                    </Card>
                  ))}
                </div>
              </div>
            )}

            {/* Formulário de Credenciais */}
            {selectedExchange && (
              <div className="space-y-4">
                <div className="flex items-center gap-3 pb-3 border-b">
                  <div className="w-12 h-12 bg-muted rounded-lg flex items-center justify-center">
                    <div className="w-8 h-8 bg-primary/20 rounded" />
                  </div>
                  <div>
                    <h3 className="font-medium">{selectedExchange.displayName}</h3>
                    <p className="text-sm text-muted-foreground">
                      Configure suas credenciais de API
                    </p>
                  </div>
                  <Button 
                    variant="ghost" 
                    size="sm" 
                    onClick={() => setSelectedExchange(null)}
                  >
                    ← Voltar
                  </Button>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="apiKey">
                      <Key className="w-4 h-4 mr-1 inline" />
                      API Key
                    </Label>
                    <Input
                      id="apiKey"
                      type={showPassword ? 'text' : 'password'}
                      value={credentials.apiKey || ''}
                      onChange={(e) => setCredentials(prev => ({ ...prev, apiKey: e.target.value }))}
                      placeholder="Sua API Key"
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="apiSecret">
                      <Key className="w-4 h-4 mr-1 inline" />
                      API Secret
                    </Label>
                    <div className="relative">
                      <Input
                        id="apiSecret"
                        type={showPassword ? 'text' : 'password'}
                        value={credentials.apiSecret || ''}
                        onChange={(e) => setCredentials(prev => ({ ...prev, apiSecret: e.target.value }))}
                        placeholder="Sua API Secret"
                      />
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="absolute right-0 top-0 h-full px-3"
                        onClick={() => setShowPassword(!showPassword)}
                      >
                        {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                      </Button>
                    </div>
                  </div>

                  {/* Passphrase para OKX, KuCoin */}
                  {(['okx', 'kucoin'].includes(selectedExchange.id)) && (
                    <div className="space-y-2">
                      <Label htmlFor="passphrase">Passphrase</Label>
                      <Input
                        id="passphrase"
                        type={showPassword ? 'text' : 'password'}
                        value={credentials.passphrase || ''}
                        onChange={(e) => setCredentials(prev => ({ ...prev, passphrase: e.target.value }))}
                        placeholder="Passphrase (se aplicável)"
                      />
                    </div>
                  )}

                  <div className="flex items-center space-x-2">
                    <Switch
                      id="sandbox"
                      checked={credentials.sandbox || false}
                      onCheckedChange={(checked) => setCredentials(prev => ({ ...prev, sandbox: checked }))}
                    />
                    <Label htmlFor="sandbox">Modo Sandbox/Testnet</Label>
                  </div>
                </div>

                <div className="flex justify-end gap-2 pt-4 border-t">
                  <Button variant="outline" onClick={() => setIsOpen(false)}>
                    Cancelar
                  </Button>
                  <Button onClick={handleSubmit} variant="premium">
                    <CheckCircle className="w-4 h-4 mr-1" />
                    Conectar Exchange
                  </Button>
                </div>
              </div>
            )}
          </DialogContent>
        </Dialog>
      </div>

      {/* Lista de Conexões Ativas */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {connections.length === 0 ? (
          <Card className="glass-card col-span-full">
            <CardContent className="p-8 text-center">
              <div className="w-16 h-16 mx-auto mb-4 bg-muted/50 rounded-full flex items-center justify-center">
                <Wifi className="w-8 h-8 text-muted-foreground" />
              </div>
              <h3 className="font-medium mb-2">Nenhuma Exchange Conectada</h3>
              <p className="text-sm text-muted-foreground mb-4">
                Conecte suas exchanges favoritas para começar a operar
              </p>
              <Button variant="outline" onClick={() => setIsOpen(true)}>
                <Plus className="w-4 h-4 mr-2" />
                Conectar Primeira Exchange
              </Button>
            </CardContent>
          </Card>
        ) : (
          connections.map((connection) => (
            <Card key={connection.exchange.id} className="glass-card">
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 bg-muted rounded-lg flex items-center justify-center">
                      <div className="w-6 h-6 bg-primary/20 rounded" />
                    </div>
                    <div>
                      <CardTitle className="text-base">{connection.exchange.displayName}</CardTitle>
                      <p className="text-xs text-muted-foreground">
                        {connection.exchange.pairs.length} pares
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-1">
                    {connection.isConnected ? (
                      <Badge variant="success" className="text-xs">
                        <Wifi className="w-3 h-3 mr-1" />
                        Online
                      </Badge>
                    ) : (
                      <Badge variant="destructive" className="text-xs">
                        <WifiOff className="w-3 h-3 mr-1" />
                        Offline
                      </Badge>
                    )}
                  </div>
                </div>
              </CardHeader>

              <CardContent className="space-y-3">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">Taxa Maker/Taker:</span>
                  <span className="font-medium">
                    {(connection.exchange.fees.maker * 100).toFixed(3)}% / {(connection.exchange.fees.taker * 100).toFixed(3)}%
                  </span>
                </div>

                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">Features:</span>
                  <span className="font-medium">
                    {connection.exchange.supportedFeatures.length} recursos
                  </span>
                </div>

                {connection.lastPing && (
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">Último ping:</span>
                    <span className="font-medium">
                      {new Date(connection.lastPing).toLocaleTimeString()}
                    </span>
                  </div>
                )}

                {connection.error && (
                  <div className="p-2 bg-destructive/10 border border-destructive/20 rounded text-sm text-destructive">
                    <AlertCircle className="w-4 h-4 mr-1 inline" />
                    {connection.error}
                  </div>
                )}

                <div className="flex gap-2 pt-2 border-t">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => onTestConnection(connection.exchange.id)}
                    className="flex-1"
                  >
                    <Settings className="w-4 h-4 mr-1" />
                    Testar
                  </Button>
                  <Button
                    variant="destructive"
                    size="sm"
                    onClick={() => onRemoveConnection(connection.exchange.id)}
                  >
                    Remover
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))
        )}
      </div>
    </div>
  );
}