/**
 * PublicStrategies.tsx - Página de Estratégias Públicas
 * 
 * Exibe:
 * - Lista de estratégias públicas com design glassmorphism
 * - Ranking visual (Top 3) com medalhas
 * - Efeitos de hover e animações com Framer Motion
 * - Filtros e busca
 * 
 * Acesso: Público (não requer autenticação)
 * Dados obtidos de: GET /api/strategies/public/list
 */

import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { useStrategies } from '../hooks/useStrategies';
import { StrategyResponse } from '../types/strategy';
import { AlertCircle, Search, Share2, MessageSquare, Star, Award } from 'lucide-react';

const PublicStrategies: React.FC = () => {
  const { fetchPublicStrategies } = useStrategies();
  const [strategies, setStrategies] = useState<StrategyResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [filteredStrategies, setFilteredStrategies] = useState<StrategyResponse[]>([]);

  // Carregar estratégias públicas ao montar
  useEffect(() => {
    const loadPublic = async () => {
      try {
        setLoading(true);
        const data = await fetchPublicStrategies();
        setStrategies(data);
        setFilteredStrategies(data);
      } catch (err) {
        setError('Erro ao carregar estratégias públicas');
        console.error(err);
      } finally {
        setLoading(false);
      }
    };

    loadPublic();
  }, [fetchPublicStrategies]);

  // Filtrar por busca
  useEffect(() => {
    const filtered = strategies.filter(
      (strategy) =>
        strategy.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        (strategy.description &&
          strategy.description.toLowerCase().includes(searchTerm.toLowerCase()))
    );
    setFilteredStrategies(filtered);
  }, [searchTerm, strategies]);

  return (
    <div className="min-h-screen bg-surface-base">
      {/* Header */}
      <div className="bg-surface-raised border-b border-edge-subtle">
        <div className="max-w-[1600px] mx-auto px-6 py-6">
          <h1 className="font-display font-bold text-3xl text-content-primary tracking-tight mb-1">Estratégias Públicas</h1>
          <p className="text-sm text-content-secondary">
            Explore e aprenda com estratégias compartilhadas pela comunidade
          </p>
        </div>
      </div>

      {/* Content */}
      <div className="max-w-[1600px] mx-auto px-6 py-8">
        {/* Search Bar */}
        <div className="mb-6">
          <div className="relative max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-content-muted" />
            <input
              type="text"
              placeholder="Buscar por nome ou descrição..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-10 pr-4 py-2.5 bg-surface-hover border border-edge-default text-sm text-content-primary rounded-lg placeholder:text-content-muted focus:outline-none focus:border-brand-primary focus:ring-2 focus:ring-brand-primary/15 transition-all duration-150"
            />
          </div>
        </div>

        {/* Error State */}
        {error && (
          <div className="mb-6 flex items-start gap-3 p-4 rounded-lg bg-semantic-loss/8 border border-semantic-loss/25">
            <AlertCircle className="w-4 h-4 text-semantic-loss flex-shrink-0 mt-0.5" />
            <p className="text-sm text-semantic-loss">{error}</p>
          </div>
        )}

        {/* Loading State */}
        {loading && (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="bg-surface-raised border border-edge-subtle rounded-lg p-6 animate-pulse">
                <div className="h-3 bg-surface-active rounded w-1/2 mb-4" />
                <div className="h-5 bg-surface-active rounded w-3/4 mb-2" />
                <div className="h-3 bg-surface-active rounded w-full mb-1" />
                <div className="h-3 bg-surface-active rounded w-2/3 mb-4" />
                <div className="h-3 bg-surface-active rounded w-1/3" />
              </div>
            ))}
          </div>
        )}

        {/* Empty State */}
        {!loading && strategies.length === 0 && (
          <div className="flex flex-col items-center justify-center py-20 text-center">
            <div className="w-10 h-10 rounded-lg bg-surface-hover flex items-center justify-center mb-4">
              <Award size={18} className="text-content-muted" />
            </div>
            <h3 className="font-display font-semibold text-content-primary mb-2">Nenhuma estratégia pública</h3>
            <p className="text-sm text-content-secondary max-w-xs">
              Seja o primeiro a compartilhar uma estratégia com a comunidade!
            </p>
          </div>
        )}

        {/* No Results */}
        {!loading && strategies.length > 0 && filteredStrategies.length === 0 && (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <div className="w-10 h-10 rounded-lg bg-surface-hover flex items-center justify-center mb-4">
              <Search size={18} className="text-content-muted" />
            </div>
            <h3 className="font-display font-semibold text-content-primary mb-2">Nenhum resultado</h3>
            <p className="text-sm text-content-secondary">Tente outros termos de busca.</p>
          </div>
        )}

        {/* Strategies Grid */}
        {!loading && filteredStrategies.length > 0 && (
          <>
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <Award className="w-4 h-4 text-semantic-warning" />
                <span className="text-sm font-medium text-content-secondary uppercase tracking-widest">Ranking</span>
              </div>
              <span className="text-xs text-content-muted font-mono tabular-nums">
                {filteredStrategies.length} estratégia(s)
              </span>
            </div>

            <motion.div
              className="grid gap-4 md:grid-cols-2 lg:grid-cols-3"
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.25, ease: 'easeOut' }}
            >
              {filteredStrategies.map((strategy, index) => {
                const medals = ['🥇', '🥈', '🥉'];
                const medal = index < 3 ? medals[index] : null;

                return (
                  <motion.div
                    key={strategy.id}
                    className="group bg-surface-raised border border-edge-subtle rounded-lg p-6 relative overflow-hidden transition-all duration-200 hover:border-edge-default"
                    initial={{ opacity: 0, y: 12 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: index * 0.04, duration: 0.2, ease: 'easeOut' }}
                  >
                    {/* Ranking badge */}
                    {medal && (
                      <span className="absolute top-4 right-4 text-lg" title={`#${index + 1}`}>
                        {medal}
                      </span>
                    )}

                    {/* Rank number */}
                    <div className="text-xs font-medium text-content-muted uppercase tracking-widest mb-3">
                      #{index + 1}
                    </div>

                    {/* Name & Description */}
                    <h3 className="font-display font-semibold text-base text-content-primary mb-1 pr-8 group-hover:text-brand-primary transition-colors duration-150">
                      {strategy.name}
                    </h3>
                    <p className="text-sm text-content-secondary line-clamp-2 mb-3">
                      {strategy.description || 'Sem descrição'}
                    </p>

                    {/* Author */}
                    <p className="text-xs text-content-muted mb-4">
                      Por: <span className="text-content-body font-medium">@usuario_{strategy.user_id.substring(0, 6)}</span>
                    </p>

                    {/* Parameters */}
                    {Object.keys(strategy.parameters).length > 0 && (
                      <div className="mb-4 p-3 bg-surface-hover border border-edge-subtle rounded-md">
                        <p className="text-2xs font-medium text-content-muted uppercase tracking-widest mb-2">
                          Parâmetros
                        </p>
                        <div className="space-y-1">
                          {Object.entries(strategy.parameters).slice(0, 3).map(([key, value]) => (
                            <div key={key} className="flex justify-between items-center">
                              <span className="text-xs text-content-muted">{key}</span>
                              <span className="font-mono text-xs text-content-body tabular-nums">
                                {String(value).substring(0, 15)}{String(value).length > 15 ? '…' : ''}
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Date */}
                    <p className="text-xs text-content-muted mb-4 pb-4 border-b border-edge-subtle">
                      Criada em: <span className="text-content-secondary font-mono tabular-nums">
                        {new Date(strategy.created_at).toLocaleDateString('pt-BR')}
                      </span>
                    </p>

                    {/* Actions */}
                    <div className="flex gap-2">
                      <button className="flex-1 flex items-center justify-center gap-2 py-2 px-3 rounded-md bg-brand-primary/10 hover:bg-brand-primary/15 border border-brand-primary/20 text-brand-primary text-xs font-medium transition-all duration-150">
                        <Star className="w-3.5 h-3.5" />
                        Salvar
                      </button>
                      <button className="p-2 rounded-md bg-surface-hover hover:bg-surface-active border border-edge-subtle text-content-secondary hover:text-content-primary transition-all duration-150">
                        <Share2 className="w-3.5 h-3.5" />
                      </button>
                      <button className="p-2 rounded-md bg-surface-hover hover:bg-surface-active border border-edge-subtle text-content-secondary hover:text-content-primary transition-all duration-150">
                        <MessageSquare className="w-3.5 h-3.5" />
                      </button>
                    </div>

                    {/* Accent line on hover */}
                    <div className="absolute bottom-0 left-0 right-0 h-[2px] bg-brand-primary/0 group-hover:bg-brand-primary/40 transition-all duration-300" />
                  </motion.div>
                );
              })}
            </motion.div>
          </>
        )}
      </div>
    </div>
  );
};

export default PublicStrategies;
