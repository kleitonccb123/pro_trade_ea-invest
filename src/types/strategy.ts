/**
 * TypeScript Interfaces - Strategy Management
 * 
 * Estas interfaces correspondem exatamente aos modelos Pydantic v2 do backend:
 * - backend/app/strategies/models.py
 * 
 * Mantém sincronização automática entre frontend e backend.
 */

/**
 * Estratégia como recebida do backend
 * Corresponde a: StrategyResponse (backend)
 * 
 * Nota: O backend retorna _id (ObjectId do MongoDB)
 * O Pydantic converte automaticamente para 'id' no JSON
 */
export interface StrategyResponse {
  id: string; // ObjectId convertido para string (alias _id)
  name: string;
  description?: string;
  parameters: Record<string, any>; // Qualquer objeto JSON
  user_id: string; // ID do usuário dono
  is_public: boolean; // Visível para outros usuários?
  created_at: string; // ISO 8601 datetime
  updated_at: string; // ISO 8601 datetime
  accuracy?: number; // Acurácia (0-100%)
  code?: string; // Código da estratégia
  trades?: number; // Número de trades no teste
  profit?: number; // Lucro/prejuízo no teste
  in_store?: boolean; // Está na loja de robôs?
}

/**
 * Estratégia para enviar ao backend (POST/PUT)
 * Corresponde a: StrategySubmitRequest (backend)
 * 
 * Nota: user_id é adicionado automaticamente pelo backend via token
 *       não enviamos aqui
 */
export interface StrategySubmitRequest {
  name: string;
  description?: string;
  parameters: Record<string, any>;
  is_public?: boolean; // default: false
}

/**
 * Estratégia para listagens (resumida)
 * Corresponde a: StrategyListItem (backend)
 * 
 * Menos campos para economizar bandwidth
 */
export interface StrategyListItem {
  id: string;
  name: string;
  description?: string;
  user_id: string;
  is_public: boolean;
  created_at: string;
}

/**
 * Resposta da API ao criar estratégia
 */
export interface StrategyCreateResponse {
  success: boolean;
  message?: string;
  data?: StrategyResponse;
}

/**
 * Resposta da API ao listar estratégias
 */
export interface StrategyListResponse {
  success: boolean;
  data: StrategyResponse[];
  total?: number;
}

/**
 * Erro da API
 */
export interface ApiError {
  detail?: string;
  message?: string;
  status?: number;
}

/**
 * Estado de carregamento para componentes
 */
export interface LoadingState {
  loading: boolean;
  error?: ApiError;
  data?: any;
}

/**
 * Validações de entrada
 */
export const strategyValidation = {
  minNameLength: 3,
  maxNameLength: 100,
  minDescriptionLength: 0,
  maxDescriptionLength: 500,
};
