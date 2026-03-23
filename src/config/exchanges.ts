// Configuração das exchanges de cripto para o sistema
// Para alterar a exchange de cripto, basta trocar o ID aqui

export const EXCHANGE_CONFIG = {
  // Exchange de Cripto - Configurável
  CRYPTO: {
    // Opções disponíveis: 'binance', 'okx', 'bybit', 'kucoin', 'coinbase', 'kraken'
    CURRENT: 'binance', // Altere aqui quando decidir qual exchange usar
    
    // Configurações para diferentes exchanges (para referência futura)
    OPTIONS: {
      binance: {
        name: 'Binance',
        description: 'Maior volume mundial, alta liquidez',
        fees: { maker: 0.1, taker: 0.1 }
      },
      okx: {
        name: 'OKX', 
        description: 'Boas ferramentas de derivativos',
        fees: { maker: 0.08, taker: 0.1 }
      },
      bybit: {
        name: 'Bybit',
        description: 'Focada em derivativos',
        fees: { maker: 0.1, taker: 0.1 }
      },
      kucoin: {
        name: 'KuCoin',
        description: 'Boa variedade de altcoins',
        fees: { maker: 0.1, taker: 0.1 }
      },
      coinbase: {
        name: 'Coinbase Pro',
        description: 'Exchange regulamentada nos EUA',
        fees: { maker: 0.5, taker: 0.5 }
      },
      kraken: {
        name: 'Kraken',
        description: 'Exchange com boa reputação',
        fees: { maker: 0.16, taker: 0.26 }
      }
    }
  }
};

// Helper para obter a exchange de cripto atual
export const getCurrentCryptoExchange = () => EXCHANGE_CONFIG.CRYPTO.CURRENT;

// Helper para obter informações da exchange de cripto atual
export const getCurrentCryptoExchangeInfo = () => {
  const currentId = EXCHANGE_CONFIG.CRYPTO.CURRENT;
  return EXCHANGE_CONFIG.CRYPTO.OPTIONS[currentId as keyof typeof EXCHANGE_CONFIG.CRYPTO.OPTIONS];
};