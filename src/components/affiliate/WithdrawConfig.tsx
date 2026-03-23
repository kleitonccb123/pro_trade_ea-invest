import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { Copy, Check, AlertCircle, Info } from 'lucide-react';
import api from '../../services/api';

/**
 * WithdrawConfig - Configuração de método de saque (PIX, Crypto, KuCoin UID, Banco)
 * 
 * Features:
 * - Validação de formato por tipo
 * - Máscara de entrada (UID numérico)
 * - Explicações visuais
 * - Cópia de exemplos
 */
const WithdrawConfig = ({ onMethodSaved, method: initialMethod = null }) => {
  const [method, setMethod] = useState(initialMethod?.type || 'pix');
  const [key, setKey] = useState(initialMethod?.key || '');
  const [holderName, setHolderName] = useState(initialMethod?.holder_name || '');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(false);

  // Validações por tipo
  const getValidation = () => {
    switch (method) {
      case 'pix':
        return {
          placeholder: 'emailoupix@gmail.com ou CPF: 123.456.789-00',
          pattern: '.+',
          hint: '✓ Email, CPF, Telefone ou Chave Aleatória',
          example: 'seu.email@example.com',
        };
      case 'kucoin_uid':
        return {
          placeholder: 'ex: 12345678',
          pattern: '^\\d{8,10}$',
          hint: '✓ 8-10 dígitos numéricos (encontre em Perfil > UID)',
          example: '12345678',
          warning: 'Certifique-se de que sua conta KuCoin está ativa e habilitada para receber transfers internos.',
        };
      case 'crypto':
        return {
          placeholder: 'ex: TU6jjxTH2rLFP7ktwhojjQ14k...',
          pattern: '.{26,}',
          hint: '✓ Endereço USDT TRC20 (mínimo 26 caracteres)',
          example: 'TU6jjxTH2rLFP7ktwhojjQ14kYjUZDJV...',
        };
      case 'bank_transfer':
        return {
          placeholder: 'ex: 12345-6 / 123456789-0',
          pattern: '.+',
          hint: '✓ Agência-Conta ou apenas Conta',
          example: '1234-5 / 9876543-2',
        };
      default:
        return {
          placeholder: '',
          pattern: '.+',
          hint: '',
          example: '',
        };
    }
  };

  const validation = getValidation();

  // Máscara para UID (apenas números)
  const handleUIDChange = (e) => {
    if (method === 'kucoin_uid') {
      const value = e.target.value.replace(/[^\d]/g, '').slice(0, 10);
      setKey(value);
    } else {
      setKey(e.target.value);
    }
  };

  // Validar antes de enviar
  const validateInput = () => {
    if (!key || key.trim().length === 0) {
      setError('Preencha o campo de chave/UID');
      return false;
    }

    if (!holderName || holderName.trim().length === 0) {
      setError('Preencha o nome do titular');
      return false;
    }

    if (method === 'kucoin_uid') {
      if (!/^\d{8,10}$/.test(key)) {
        setError('UID deve ter 8-10 dígitos numéricos');
        return false;
      }
    }

    if (method === 'crypto') {
      if (key.length < 26) {
        setError('Endereço crypto deve ter no mínimo 26 caracteres');
        return false;
      }
    }

    setError(null);
    return true;
  };

  // Enviar configuração
  const handleSave = async () => {
    if (!validateInput()) return;

    try {
      setLoading(true);
      const response = await api.post('/affiliates/withdrawal-method', {
        type: method,
        key: key.trim(),
        holder_name: holderName.trim(),
      });

      if (response.data.success) {
        setSuccess(true);
        setError(null);

        // Notifica componente pai
        if (onMethodSaved) {
          onMethodSaved(response.data.method);
        }

        // Reset
        setTimeout(() => {
          setSuccess(false);
        }, 3000);
      } else {
        setError(response.data.message || 'Erro ao salvar');
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Erro ao conectar');
    } finally {
      setLoading(false);
    }
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    // TODO: Mostrar toast
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-gradient-to-br from-slate-800 to-slate-900 border border-slate-700 rounded-xl p-6 backdrop-blur"
    >
      <h3 className="text-lg font-bold text-white mb-6">🔧 Configurar Método de Saque</h3>

      {/* Seletor de Tipo */}
      <div className="mb-6">
        <label className="block text-sm font-semibold text-gray-300 mb-3">
          Escolha seu método de recebimento
        </label>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {[
            { id: 'pix', label: '🔐 PIX', desc: 'Instantâneo' },
            { id: 'kucoin_uid', label: '🟡 KuCoin', desc: 'UID KuCoin' },
            { id: 'crypto', label: '₿ Crypto', desc: 'USDT TRC20' },
            { id: 'bank_transfer', label: '🏦 Banco', desc: '1-3 dias' },
          ].map((opt) => (
            <motion.button
              key={opt.id}
              onClick={() => {
                setMethod(opt.id);
                setError(null);
              }}
              whileHover={{ scale: 1.05 }}
              className={`p-3 rounded-lg transition font-semibold text-sm ${
                method === opt.id
                  ? 'bg-blue-600 text-white border-2 border-blue-400'
                  : 'bg-slate-700 text-gray-300 border-2 border-transparent hover:border-slate-600'
              }`}
            >
              <div>{opt.label}</div>
              <div className="text-xs opacity-75">{opt.desc}</div>
            </motion.button>
          ))}
        </div>
      </div>

      {/* Info Box */}
      {validation.warning && (
        <div className="mb-4 bg-orange-500/10 border border-orange-500/50 rounded-lg p-4 flex gap-3">
          <AlertCircle size={20} className="text-orange-400 flex-shrink-0 mt-0.5" />
          <p className="text-orange-400 text-sm">{validation.warning}</p>
        </div>
      )}

      {/* Campo de Chave/UID */}
      <div className="mb-4">
        <label className="block text-sm font-semibold text-gray-300 mb-2">
          {method === 'pix' && 'Chave PIX'}
          {method === 'kucoin_uid' && 'UID da KuCoin'}
          {method === 'crypto' && 'Endereço USDT (TRC20)'}
          {method === 'bank_transfer' && 'Agência e Conta'}
        </label>
        <input
          type="text"
          value={key}
          onChange={handleUIDChange}
          placeholder={validation.placeholder}
          maxLength={method === 'kucoin_uid' ? 10 : 255}
          className="w-full bg-slate-700 text-white rounded-lg px-4 py-3 border border-slate-600 focus:border-blue-500 focus:outline-none font-mono"
        />
        <p className="text-xs text-gray-400 mt-2">💡 {validation.hint}</p>
      </div>

      {/* Exemplo */}
      <div className="mb-6 bg-slate-700/50 rounded-lg p-3">
        <div className="flex justify-between items-center">
          <div>
            <p className="text-xs text-gray-400">
              {method === 'pix' && 'Exemplo de chave PIX:'}
              {method === 'kucoin_uid' && 'Exemplo de UID:'}
              {method === 'crypto' && 'Exemplo de endereço:'}
              {method === 'bank_transfer' && 'Exemplo de conta:'}
            </p>
            <p className="text-sm text-gray-300 font-mono mt-1 break-all">{validation.example}</p>
          </div>
          <button
            onClick={() => copyToClipboard(validation.example)}
            className="ml-2 p-2 hover:bg-slate-600 rounded transition text-gray-400 hover:text-white flex-shrink-0"
            title="Copiar"
          >
            <Copy size={18} />
          </button>
        </div>
      </div>

      {/* Onde encontro meu UID KuCoin */}
      {method === 'kucoin_uid' && (
        <div className="mb-6 bg-blue-500/10 border border-blue-500/50 rounded-lg p-4">
          <div className="flex gap-3">
            <Info size={20} className="text-blue-400 flex-shrink-0 mt-0.5" />
            <div className="text-sm text-blue-200">
              <p className="font-semibold mb-2">Onde encontrar seu UID na KuCoin:</p>
              <ol className="list-decimal list-inside space-y-1 opacity-90">
                <li>Faça login na KuCoin</li>
                <li>Clique em seu avatar no canto superior direito</li>
                <li>Selecione "Perfil"</li>
                <li>Seu UID aparece como um número (ex: 12345678)</li>
              </ol>
            </div>
          </div>
        </div>
      )}

      {/* Nome do Titular */}
      <div className="mb-6">
        <label className="block text-sm font-semibold text-gray-300 mb-2">
          Nome Completo do Titular
        </label>
        <input
          type="text"
          value={holderName}
          onChange={(e) => setHolderName(e.target.value)}
          placeholder="Seu nome completo"
          className="w-full bg-slate-700 text-white rounded-lg px-4 py-3 border border-slate-600 focus:border-blue-500 focus:outline-none"
        />
        <p className="text-xs text-gray-400 mt-2">Deve coincidir com o nome na conta bancária/KuCoin</p>
      </div>

      {/* Error Alert */}
      {error && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="mb-4 bg-red-500/10 border border-red-500/50 text-red-400 p-4 rounded-lg flex justify-between items-center"
        >
          <span>{error}</span>
          <button
            onClick={() => setError(null)}
            className="opacity-70 hover:opacity-100 transition"
          >
            ✕
          </button>
        </motion.div>
      )}

      {/* Success Alert */}
      {success && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="mb-4 bg-green-500/10 border border-green-500/50 text-green-400 p-4 rounded-lg flex items-center gap-2"
        >
          <Check size={20} />
          <span>Método de saque salvo com sucesso!</span>
        </motion.div>
      )}

      {/* Buttons */}
      <div className="flex gap-3">
        <button
          onClick={handleSave}
          disabled={loading}
          className="flex-1 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-700 disabled:cursor-not-allowed text-white px-6 py-3 rounded-lg font-semibold transition"
        >
          {loading ? '⏳ Salvando...' : '💾 Salvar Método'}
        </button>
        <button
          onClick={() => {
            setKey('');
            setHolderName('');
            setError(null);
          }}
          className="bg-slate-700 hover:bg-slate-600 text-white px-6 py-3 rounded-lg font-semibold transition"
        >
          Limpar
        </button>
      </div>

      {/* Info Footer */}
      <div className="mt-4 pt-4 border-t border-slate-700 text-xs text-gray-500">
        🔒 Suas informações são encriptadas e armazenadas com segurança.
        {method === 'kucoin_uid' && (
          <>
            <br />
            ⚠️ Certifique-se de copiar o UID correto. Saques para UIDs incorretos não podem ser revertidos.
          </>
        )}
      </div>
    </motion.div>
  );
};

export default WithdrawConfig;
