import React, { useEffect, useState } from 'react';
import { useStrategies } from '../hooks/useStrategies';
import { StrategyResponse, StrategySubmitRequest } from '../types/strategy';
import { AlertCircle, Check, Trash2, Eye, EyeOff, Plus, Edit2, Code2, Star } from 'lucide-react';
import { StrategyBuilder } from '../components/StrategyBuilder';
import { useLanguage } from '@/hooks/use-language';

const MyStrategies: React.FC = () => {
  const { t } = useLanguage();
  const {
    strategies,
    loading,
    error,
    success,
    fetchStrategies,
    createStrategy,
    deleteStrategy,
    toggleVisibility,
    clearError,
    clearSuccess,
  } = useStrategies();

  const [showModal, setShowModal] = useState(false);
  const [showBuilder, setShowBuilder] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [formData, setFormData] = useState<StrategySubmitRequest>({
    name: '',
    description: '',
    parameters: {},
    is_public: false,
  });

  useEffect(() => {
    fetchStrategies();
  }, [fetchStrategies]);

  const handleCreateStrategy = async () => {
    if (!formData.name.trim()) return;
    await createStrategy(formData);
    setFormData({
      name: '',
      description: '',
      parameters: {},
      is_public: false,
    });
    setShowModal(false);
  };

  const handleDelete = async (id: string) => {
    if (window.confirm(t('strategies.confirmDelete'))) {
      await deleteStrategy(id);
    }
  };

  const handleToggleVisibility = async (id: string) => {
    await toggleVisibility(id);
  };

  const handleBuilderSave = async (strategy: StrategySubmitRequest) => {
    await createStrategy(strategy);
    setShowBuilder(false);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 to-slate-800">
      <div className="bg-slate-900 border-b border-slate-700 shadow-lg">
        <div className="max-w-7xl mx-auto px-4 py-6">
          <h1 className="text-3xl font-bold text-white mb-2">{t('strategies.myStrategies')}</h1>
          <p className="text-slate-400">
            {t('strategies.subtitle')}
          </p>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 py-8">
        {error && (
          <div className="mb-4 p-4 bg-red-900/20 border border-red-700 rounded-lg flex items-center gap-3">
            <AlertCircle className="w-5 h-5 text-red-500" />
            <div>
              <p className="text-red-300 font-semibold">{error.detail}</p>
              {error.status && (
                <p className="text-red-400 text-sm">{t('strategies.errorCode')}: {error.status}</p>
              )}
            </div>
            <button
              onClick={clearError}
              className="ml-auto text-red-400 hover:text-red-300 text-sm"
            >
              ✕
            </button>
          </div>
        )}

        {success && (
          <div className="mb-4 p-4 bg-green-900/20 border border-green-700 rounded-lg flex items-center gap-3">
            <Check className="w-5 h-5 text-green-500" />
            <p className="text-green-300 font-semibold">{t('strategies.successMessage')}</p>
          </div>
        )}

        <div className="mb-6 flex gap-3 flex-wrap">
          <button
            onClick={() => setShowModal(true)}
            className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-semibold transition"
          >
            <Plus className="w-5 h-5" />
            {t('strategies.newStrategy')}
          </button>

          <button
            onClick={() => setShowBuilder(true)}
            className="inline-flex items-center gap-2 px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg font-semibold transition"
          >
            <Code2 className="w-5 h-5" />
            {t('strategies.strategyBuilder')}
          </button>
        </div>

        {loading && (
          <div className="text-center py-12">
            <p className="text-slate-400">{t('strategies.loading')}</p>
          </div>
        )}

        {!loading && strategies.length === 0 && (
          <div className="text-center py-12">
            <p className="text-slate-400">{t('strategies.noStrategies')}</p>
          </div>
        )}

        {!loading && strategies.length > 0 && (
          <div className="grid gap-4">
            {strategies.map((strategy) => (
              <div
                key={strategy.id}
                className="bg-slate-700/50 border border-slate-600 rounded-lg p-4 hover:border-slate-500 transition"
              >
                <div className="flex items-start justify-between mb-3">
                  <div className="flex-1 ">
                    <h3 className="font-bold text-white text-lg mb-1 flex items-center gap-2">
                      {strategy.name}
                      {strategy.is_public && strategy.accuracy && strategy.accuracy >= 40 && (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-bold bg-green-600 text-white">
                          <Star className="w-3 h-3" />
                          {t('strategies.published')}
                        </span>
                      )}
                    </h3>
                    <p className="text-slate-400 text-sm line-clamp-2">
                      {strategy.description || t('strategies.noDescription')}
                    </p>
                  </div>
                  <span
                    className={`inline-block px-2 py-1 rounded text-xs font-semibold ${
                      strategy.is_public
                        ? 'bg-green-900/40 text-green-300 border border-green-700'
                        : 'bg-yellow-900/40 text-yellow-300 border border-yellow-700'
                    }`}
                  >
                    {strategy.is_public ? t('strategies.public') : t('strategies.private')}
                  </span>
                </div>

                {strategy.accuracy && (
                  <div className="mb-3 p-3 bg-slate-700/40 rounded">
                    <div className="flex items-center justify-between">
                      <p className="text-xs text-slate-400 font-semibold">{t('strategies.accuracy')}</p>
                      <p
                        className={`text-sm font-bold ${
                          strategy.accuracy >= 40
                            ? 'text-green-400'
                            : strategy.accuracy >= 30
                            ? 'text-yellow-400'
                            : 'text-red-400'
                        }`}
                      >
                        {strategy.accuracy.toFixed(1)}%
                      </p>
                    </div>
                  </div>
                )}

                {Object.keys(strategy.parameters).length > 0 && (
                  <div className="mb-3 p-3 bg-slate-700/40 rounded">
                    <p className="text-xs text-slate-400 font-semibold mb-2">
                      {t('strategies.parameters')}:
                    </p>
                    <div className="text-xs text-slate-300">
                      {Object.entries(strategy.parameters).map(([key, value]) => (
                        <div key={key} className="flex justify-between">
                          <span>{key}:</span>
                          <span className="font-mono text-slate-400">
                            {String(value)}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                <div className="flex gap-2 pt-3 border-t border-slate-600">
                  <button
                    onClick={() => handleToggleVisibility(strategy.id)}
                    title={
                      strategy.is_public
                        ? t('strategies.makePrivate')
                        : t('strategies.makePublic')
                    }
                    className="py-2 px-3 bg-blue-900/40 hover:bg-blue-900/60 text-blue-300 rounded text-sm font-semibold transition"
                  >
                    {strategy.is_public ? (
                      <Eye className="w-4 h-4" />
                    ) : (
                      <EyeOff className="w-4 h-4" />
                    )}
                    {strategy.is_public ? t('strategies.private') : t('strategies.public')}
                  </button>

                  <button
                    onClick={() => handleDelete(strategy.id)}
                    title={t('strategies.deleteStrategy')}
                    className="py-2 px-3 bg-red-900/40 hover:bg-red-900/60 text-red-300 rounded text-sm font-semibold transition"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {showModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
          <div className="bg-slate-800 border border-slate-700 rounded-lg max-w-md w-full p-6">
            <h2 className="text-2xl font-bold text-white mb-4">{t('strategies.newStrategy')}</h2>

            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleCreateStrategy();
              }}
              className="space-y-4"
            >
              <div>
                <label className="block text-sm font-semibold text-slate-300 mb-2">
                  {t('strategies.strategyName')} *
                </label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) =>
                    setFormData({ ...formData, name: e.target.value })
                  }
                  placeholder={t('strategies.namePlaceholder')}
                  className="w-full px-3 py-2 bg-slate-700 border border-slate-600 text-white rounded placeholder-slate-500 focus:outline-none focus:border-blue-500 transition"
                />
              </div>

              <div>
                <label className="block text-sm font-semibold text-slate-300 mb-2">
                  {t('strategies.description')}
                </label>
                <textarea
                  value={formData.description}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      description: e.target.value,
                    })
                  }
                  placeholder={t('strategies.descPlaceholder')}
                  className="w-full px-3 py-2 bg-slate-700 border border-slate-600 text-white rounded placeholder-slate-500 focus:outline-none focus:border-blue-500 transition resize-none"
                  rows={3}
                />
              </div>

              <div className="flex items-center gap-2 pt-2">
                <input
                  type="checkbox"
                  id="is_public"
                  checked={formData.is_public}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      is_public: e.target.checked,
                    })
                  }
                  className="w-4 h-4 bg-slate-700 border border-slate-600 rounded"
                />
                <label
                  htmlFor="is_public"
                  className="text-sm font-semibold text-slate-300"
                >
                  {t('strategies.publicVisible')}
                </label>
              </div>

              <div className="flex gap-3 pt-4">
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="flex-1 px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg font-semibold transition"
                >
                  {t('strategies.cancel')}
                </button>
                <button
                  type="submit"
                  className="flex-1 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-semibold transition"
                >
                  {t('strategies.create')}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {showBuilder && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50 overflow-auto">
          <button
            onClick={() => setShowBuilder(false)}
            className="fixed top-4 right-4 z-50 px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg font-semibold"
          >
            ✕ {t('strategies.close')}
          </button>
          <div className="p-4">
            <StrategyBuilder onSave={handleBuilderSave} />
          </div>
        </div>
      )}
    </div>
  );
};

export default MyStrategies;
