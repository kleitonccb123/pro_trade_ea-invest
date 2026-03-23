import { apiGet, apiPost, apiDelete } from './apiClient';

export interface ExchangeCredentialsRequest {
  exchange: string;
  api_key: string;
  api_secret: string;
  passphrase?: string;
  sandbox?: boolean;
}

export interface ExchangeCredentialInfo {
  exchange: string;
  api_key_masked: string;
  connected: boolean;
  sandbox: boolean;
  last_validated: string | null;
  balance_usd: number | null;
}

export const exchangeService = {
  /**
   * Salva as credenciais da exchange no backend (criptografado).
   * Valida via CCXT antes de salvar.
   */
  async saveCredentials(data: ExchangeCredentialsRequest): Promise<ExchangeCredentialInfo> {
    return apiPost<ExchangeCredentialInfo>('/user/settings/exchanges', data);
  },

  /**
   * Lista todas as exchanges configuradas pelo usuário.
   */
  async listCredentials(): Promise<ExchangeCredentialInfo[]> {
    try {
      return await apiGet<ExchangeCredentialInfo[]>('/user/settings/exchanges');
    } catch {
      return [];
    }
  },

  /**
   * Retorna as credenciais de uma exchange específica (ou null se não configurada).
   */
  async getCredential(exchange: string): Promise<ExchangeCredentialInfo | null> {
    const list = await exchangeService.listCredentials();
    return list.find((c) => c.exchange === exchange) ?? null;
  },

  /**
   * Remove as credenciais de uma exchange.
   */
  async removeCredentials(exchange: string): Promise<void> {
    await apiDelete(`/user/settings/exchanges/${exchange}`);
  },
};
