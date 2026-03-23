import { useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { TrendingUp, DollarSign, Globe, Coins } from 'lucide-react';
import { SUPPORTED_EXCHANGES, getExchangesByType } from '@/lib/exchanges';
import { Exchange } from '@/types/exchange';

interface ExchangeSelectorProps {
  selectedExchange?: Exchange;
  onExchangeSelect: (exchange: Exchange) => void;
}

export default function ExchangeSelector({ selectedExchange, onExchangeSelect }: ExchangeSelectorProps) {
  const [selectedType, setSelectedType] = useState<'crypto'>('crypto');
  
  const cryptoExchange = getExchangesByType('crypto')[0];

  const exchangeTypes = [
    {
      type: 'crypto' as const,
      title: 'Criptomoedas',
      description: 'Trade criptomoedas',
      icon: Coins,
      exchange: cryptoExchange,
      color: 'text-orange-600'
    }
  ];

  const currentExchange = cryptoExchange;

  return (
    <div className="space-y-6">
      {/* Seletor de Tipo */}
      <div className="grid grid-cols-1 md:grid-cols-1 gap-4">
        {exchangeTypes.map(({ type, title, description, icon: Icon, color }) => (
          <Card
            key={type}
            className={`cursor-pointer transition-all hover:shadow-md ${
              selectedType === type ? 'ring-2 ring-primary' : ''
            }`}
            onClick={() => setSelectedType(type)}
          >
            <CardHeader className="pb-3">
              <div className="flex items-center space-x-3">
                <Icon className={`h-6 w-6 ${color}`} />
                <div>
                  <CardTitle className="text-lg">{title}</CardTitle>
                  <CardDescription>{description}</CardDescription>
                </div>
              </div>
            </CardHeader>
          </Card>
        ))}
      </div>

      {/* Detalhes da Exchange Selecionada */}
      {currentExchange && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-3">
                <div className="w-12 h-12 bg-gray-100 rounded-full flex items-center justify-center overflow-hidden">
                  {currentExchange.logo && currentExchange.logo.endsWith('.svg') ? (
                    <img src={currentExchange.logo} alt={currentExchange.displayName} className="w-8 h-8 object-contain" />
                  ) : (
                    <Coins className="h-6 w-6 text-orange-600" />
                  )}
                </div>
                <div>
                  <CardTitle>{currentExchange.displayName}</CardTitle>
                  <CardDescription>
                    Exchange de Criptomoedas
                  </CardDescription>
                </div>
              </div>
              <Button 
                onClick={() => onExchangeSelect(currentExchange)}
                className={selectedExchange?.id === currentExchange.id ? 'opacity-50' : ''}
                disabled={selectedExchange?.id === currentExchange.id}
              >
                {selectedExchange?.id === currentExchange.id ? 'Selecionada' : 'Selecionar'}
              </Button>
            </div>
          </CardHeader>
          
          <CardContent className="space-y-4">
            {/* Taxas */}
            <div className="flex space-x-4">
              <div className="text-sm">
                <span className="font-medium">Maker:</span> {(currentExchange.fees.maker * 100).toFixed(3)}%
              </div>
              <div className="text-sm">
                <span className="font-medium">Taker:</span> {(currentExchange.fees.taker * 100).toFixed(3)}%
              </div>
            </div>

            {/* Features */}
            <div>
              <p className="text-sm font-medium mb-2">Recursos Disponíveis:</p>
              <div className="flex flex-wrap gap-2">
                {currentExchange.supportedFeatures.map((feature) => (
                  <Badge key={feature} variant="secondary" className="text-xs">
                    {feature.replace('_', ' ').toLowerCase()}
                  </Badge>
                ))}
              </div>
            </div>

            {/* Pares Principais */}
            <div>
              <p className="text-sm font-medium mb-2">
                Principais Moedas:
              </p>
              <div className="flex flex-wrap gap-2">
                {currentExchange.pairs.slice(0, 8).map((pair) => (
                  <Badge key={pair} variant="outline" className="text-xs">
                    {pair}
                  </Badge>
                ))}
                {currentExchange.pairs.length > 8 && (
                  <Badge variant="outline" className="text-xs">
                    +{currentExchange.pairs.length - 8} mais
                  </Badge>
                )}
              </div>
            </div>

            {/* URL da API */}
            <div className="text-sm text-muted-foreground">
              <span className="font-medium">API:</span> {currentExchange.apiEndpoints.rest}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}