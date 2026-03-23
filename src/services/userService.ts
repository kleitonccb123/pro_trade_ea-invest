import { apiGet, apiPut } from './apiClient';

export interface UserProfile {
  id: string;
  email: string;
  name?: string;
  phone?: string;
  timezone: string;
  language: string;
  avatar?: string;
  created_at: string;
  two_factor_enabled: boolean;
}

export interface ProfileUpdateRequest {
  name?: string;
  email?: string;
  phone?: string;
  timezone?: string;
  language?: string;
  avatar?: string;
}

const AVAILABLE_AVATARS = [
  { id: 'avatar-1', emoji: '💹', name: 'Gráfico em Alta' },
  { id: 'avatar-2', emoji: '💰', name: 'Fortuna' },
  { id: 'avatar-3', emoji: '🚀', name: 'Foguete' },
  { id: 'avatar-4', emoji: '💎', name: 'Diamante' },
  { id: 'avatar-5', emoji: '⚡', name: 'Relâmpago' },
  { id: 'avatar-6', emoji: '📊', name: 'Gráficos' },
  { id: 'avatar-7', emoji: '🎯', name: 'Target' },
  { id: 'avatar-8', emoji: '👑', name: 'Rei do Trade' },
];

export const userService = {
  /**
   * Busca o perfil do usuário atual
   */
  async getProfile(): Promise<UserProfile> {
    try {
      const response = await apiGet<UserProfile>('/user/settings/profile');
      return response || {
        id: '',
        email: '',
        timezone: 'America/Sao_Paulo',
        language: 'pt-BR',
        created_at: new Date().toISOString(),
        two_factor_enabled: false,
      };
    } catch (error) {
      console.error('Erro ao buscar perfil:', error);
      throw error;
    }
  },

  /**
   * Atualiza o perfil do usuário
   */
  async updateProfile(data: ProfileUpdateRequest): Promise<UserProfile> {
    try {
      const response = await apiPut<UserProfile>('/user/settings/profile', data);
      return response || {
        id: '',
        email: '',
        timezone: 'America/Sao_Paulo',
        language: 'pt-BR',
        created_at: new Date().toISOString(),
        two_factor_enabled: false,
      };
    } catch (error) {
      console.error('Erro ao atualizar perfil:', error);
      throw error;
    }
  },

  /**
   * Retorna lista de avatares pré-setados
   */
  getAvailableAvatars() {
    return AVAILABLE_AVATARS;
  },

  /**
   * Retorna um avatar específico
   */
  getAvatarById(id: string) {
    return AVAILABLE_AVATARS.find(avatar => avatar.id === id);
  },

  /**
   * Retorna avatar padrão
   */
  getDefaultAvatar() {
    return AVAILABLE_AVATARS[0];
  },
};
