import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Copy, Download, Clock, CheckCircle, TrendingUp, Eye, EyeOff } from 'lucide-react';
import api from '../services/api';

/**
 * AffiliateDashboard - Dashboard completo para gerenciamento de afiliados
 * 
 * Features:
 * - Carteira com saldos (Pendente, Disponível, Total)
 * - Método de saque (PIX, Crypto, Banco)
 * - Formulário de saque com validação
 * - Histórico de transações
 * - Contagem regressiva de liberação
 */
const AffiliateDashboard = () => {
  const [walletData, setWalletData] = useState(null);
  const [transactions, setTransactions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [withdrawing, setWithdrawing] = useState(false);
  const [error, setError] = useState(null);
  const [showWithdrawal, setShowWithdrawal] = useState(false);
  const [hideBalances, setHideBalances] = useState(false);

  // Form state
  const [withdrawAmount, setWithdrawAmount] = useState('');
  const [withdrawalMethod, setWithdrawalMethod] = useState({
    type: 'pix',
    key: '',
    holder_name: '',
  });

  // Fetch wallet data
  const fetchWalletData = async () => {
    try {
      setLoading(true);
      const response = await api.get('/affiliates/wallet');
      setWalletData(response.data);
      setError(null);
    } catch (err) {
      setError(err.response?.data?.message || 'Erro ao carregar carteira');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  // Fetch transactions
  const fetchTransactions = async () => {
    try {
      const response = await api.get('/affiliates/transactions');
      setTransactions(response.data.transactions);
    } catch (err) {
      console.error('Erro ao carregar transações:', err);
    }
  };

  useEffect(() => {
    fetchWalletData();
    fetchTransactions();
    
    // Refresh a cada 30 segundos
    const interval = setInterval(() => {
      fetchWalletData();
    }, 30000);

    return () => clearInterval(interval);
  }, []);

  // Handle withdrawal
  const handleWithdraw = async () => {
    if (!withdrawAmount || parseFloat(withdrawAmount) < 50) {
      setError('Valor mínimo de saque é $50');
      return;
    }

    if (!walletData?.withdrawal_method) {
      setError('Configure um método de saque primeiro');
      return;
    }

    try {
      setWithdrawing(true);
      const response = await api.post('/affiliates/withdraw', {
        amount_usd: parseFloat(withdrawAmount),
      });

      if (response.data.success) {
        setError(null);
        setWithdrawAmount('');
        setShowWithdrawal(false);
        
        // Recarrega dados
        setTimeout(() => {
          fetchWalletData();
          fetchTransactions();
        }, 1000);

        // Toast de sucesso
        alert('Saque processado com sucesso!');
      } else {
        setError(response.data.message);
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Erro ao processar saque');
    } finally {
      setWithdrawing(false);
    }
  };

  // Handle set withdrawal method
  const handleSetMethod = async () => {
    if (!withdrawalMethod.key || !withdrawalMethod.holder_name) {
      setError('Preencha todos os campos');
      return;
    }

    try {
      await api.post('/affiliates/withdrawal-method', withdrawalMethod);
      setError(null);
      fetchWalletData();
      setShowWithdrawal(false);
      alert('Método de saque cadastrado!');
    } catch (err) {
      setError(err.response?.data?.detail || 'Erro ao cadastrar método');
    }
  };

  // Format currency
  const formatCurrency = (value) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(value || 0);
  };

  // Format date
  const formatDate = (date) => {
    return new Date(date).toLocaleDateString('pt-BR', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  // Calculate days until release
  const daysUntilRelease = (releaseAt) => {
    if (!releaseAt) return null;
    const diff = new Date(releaseAt) - new Date();
    const days = Math.ceil(diff / (1000 * 60 * 60 * 24));
    return days > 0 ? days : 0;
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center h-96">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto mb-4"></div>
          <p className="text-gray-500">Carregando carteira...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 p-6">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-8"
        >
          <div className="flex justify-between items-center">
            <div>
              <h1 className="text-4xl font-bold text-white mb-2">💰 Carteira de Afiliado</h1>
              <p className="text-gray-400">Gerencie seus ganhos e saques</p>
            </div>
            <button
              onClick={() => setHideBalances(!hideBalances)}
              className="bg-slate-700 hover:bg-slate-600 text-white p-3 rounded-lg transition"
              title="Ocultar saldos"
            >
              {hideBalances ? <EyeOff size={24} /> : <Eye size={24} />}
            </button>
          </div>
        </motion.div>

        {/* Error Alert */}
        {error && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="bg-red-500/10 border border-red-500 text-red-400 p-4 rounded-lg mb-6 flex justify-between items-center"
          >
            <span>{error}</span>
            <button onClick={() => setError(null)} className="opacity-70 hover:opacity-100">
              ✕
            </button>
          </motion.div>
        )}

        {/* Wallet Cards */}
        {walletData && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ staggerChildren: 0.1 }}
            className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8"
          >
            {/* Pending Balance Card */}
            <motion.div
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              className="bg-gradient-to-br from-orange-500/20 to-orange-600/20 border border-orange-500/50 rounded-xl p-6 backdrop-blur"
            >
              <div className="flex justify-between items-start mb-4">
                <div>
                  <p className="text-gray-400 text-sm mb-1">Saldo em Carência</p>
                  <p className="text-gray-400 text-xs">⏱️ Libera em 7 dias</p>
                </div>
                <Clock className="text-orange-400" size={24} />
              </div>
              <p className="text-3xl font-bold text-orange-400">
                {hideBalances ? '•••••' : formatCurrency(walletData.pending_balance)}
              </p>
              <div className="mt-4 pt-4 border-t border-orange-500/30">
                <p className="text-xs text-gray-500">
                  {walletData.recent_transactions?.filter((t) => t.status === 'pending').length || 0} transações pendentes
                </p>
              </div>
            </motion.div>

            {/* Available Balance Card */}
            <motion.div
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ delay: 0.1 }}
              className="bg-gradient-to-br from-green-500/20 to-green-600/20 border border-green-500/50 rounded-xl p-6 backdrop-blur"
            >
              <div className="flex justify-between items-start mb-4">
                <div>
                  <p className="text-gray-400 text-sm mb-1">Saldo Disponível</p>
                  <p className="text-gray-400 text-xs">✅ Pronto para saque</p>
                </div>
                <CheckCircle className="text-green-400" size={24} />
              </div>
              <p className="text-3xl font-bold text-green-400">
                {hideBalances ? '•••••' : formatCurrency(walletData.available_balance)}
              </p>
              <div className="mt-4 pt-4 border-t border-green-500/30">
                <button
                  onClick={() => setShowWithdrawal(!showWithdrawal)}
                  disabled={walletData.available_balance < 50}
                  className={`w-full py-2 px-3 rounded-lg text-sm font-semibold transition ${
                    walletData.available_balance >= 50
                      ? 'bg-green-600 hover:bg-green-700 text-white cursor-pointer'
                      : 'bg-slate-700 text-gray-400 cursor-not-allowed'
                  }`}
                >
                  <Download size={16} className="inline mr-2" />
                  Sacar
                </button>
              </div>
            </motion.div>

            {/* Total Earned Card */}
            <motion.div
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ delay: 0.2 }}
              className="bg-gradient-to-br from-blue-500/20 to-blue-600/20 border border-blue-500/50 rounded-xl p-6 backdrop-blur"
            >
              <div className="flex justify-between items-start mb-4">
                <div>
                  <p className="text-gray-400 text-sm mb-1">Total Ganho</p>
                  <p className="text-gray-400 text-xs">📈 Em toda carreira</p>
                </div>
                <TrendingUp className="text-blue-400" size={24} />
              </div>
              <p className="text-3xl font-bold text-blue-400">
                {hideBalances ? '•••••' : formatCurrency(walletData.total_earned)}
              </p>
              <div className="mt-4 pt-4 border-t border-blue-500/30">
                <p className="text-xs text-gray-500">
                  {formatCurrency(walletData.total_withdrawn)} já sacados
                </p>
              </div>
            </motion.div>
          </motion.div>
        )}

        {/* Withdrawal Form */}
        {showWithdrawal && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-slate-800/50 border border-slate-700 rounded-xl p-6 mb-8 backdrop-blur"
          >
            <h2 className="text-xl font-bold text-white mb-6">📤 Solicitar Saque</h2>

            {/* Withdrawal Method */}
            {!walletData?.withdrawal_method ? (
              <div className="mb-6">
                <h3 className="text-white mb-4">Cadastre um método de saque:</h3>
                
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm text-gray-400 mb-2">Tipo</label>
                    <select
                      value={withdrawalMethod.type}
                      onChange={(e) =>
                        setWithdrawalMethod({ ...withdrawalMethod, type: e.target.value })
                      }
                      className="w-full bg-slate-700 text-white rounded-lg px-4 py-2 border border-slate-600 focus:border-blue-500 focus:outline-none"
                    >
                      <option value="pix">🔐 PIX (Instantâneo)</option>
                      <option value="crypto">₿ Crypto - TRC20</option>
                      <option value="bank_transfer">🏦 Transferência Bancária (1-3 dias)</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-sm text-gray-400 mb-2">
                      {withdrawalMethod.type === 'pix' ? 'Chave PIX' : 
                       withdrawalMethod.type === 'crypto' ? 'Endereço Carteira' :
                       'Agência e Conta'}
                    </label>
                    <input
                      type="text"
                      value={withdrawalMethod.key}
                      onChange={(e) =>
                        setWithdrawalMethod({ ...withdrawalMethod, key: e.target.value })
                      }
                      placeholder="Digite aqui..."
                      className="w-full bg-slate-700 text-white rounded-lg px-4 py-2 border border-slate-600 focus:border-blue-500 focus:outline-none"
                    />
                  </div>

                  <div>
                    <label className="block text-sm text-gray-400 mb-2">Nome do Titular</label>
                    <input
                      type="text"
                      value={withdrawalMethod.holder_name}
                      onChange={(e) =>
                        setWithdrawalMethod({ ...withdrawalMethod, holder_name: e.target.value })
                      }
                      placeholder="Seu nome completo"
                      className="w-full bg-slate-700 text-white rounded-lg px-4 py-2 border border-slate-600 focus:border-blue-500 focus:outline-none"
                    />
                  </div>

                  <button
                    onClick={handleSetMethod}
                    className="w-full bg-blue-600 hover:bg-blue-700 text-white px-6 py-2 rounded-lg font-semibold transition"
                  >
                    Salvar Método
                  </button>
                </div>
              </div>
            ) : (
              <div className="bg-slate-700/50 border border-slate-600 rounded-lg p-4 mb-6">
                <div className="flex justify-between items-start">
                  <div>
                    <p className="text-gray-400 text-sm mb-1">Método cadastrado:</p>
                    <p className="text-white font-semibold">
                      {walletData.withdrawal_method?.type.toUpperCase()} - {walletData.withdrawal_method?.key}
                    </p>
                  </div>
                  <button
                    onClick={() => {
                      setShowWithdrawal(false);
                      setWithdrawalMethod({ type: 'pix', key: '', holder_name: '' });
                    }}
                    className="text-gray-400 hover:text-white transition"
                  >
                    ✕
                  </button>
                </div>
              </div>
            )}

            {/* Withdrawal Amount */}
            {walletData?.withdrawal_method && (
              <div className="mb-6">
                <label className="block text-sm text-gray-400 mb-2">Valor (USD)</label>
                <div className="flex gap-2">
                  <input
                    type="number"
                    value={withdrawAmount}
                    onChange={(e) => setWithdrawAmount(e.target.value)}
                    placeholder="Mínimo: $50.00"
                    min="50"
                    step="0.01"
                    className="flex-1 bg-slate-700 text-white rounded-lg px-4 py-2 border border-slate-600 focus:border-blue-500 focus:outline-none"
                  />
                  <button
                    onClick={() => setWithdrawAmount(walletData.available_balance.toString())}
                    className="bg-slate-700 hover:bg-slate-600 text-gray-400 px-4 py-2 rounded-lg transition text-sm"
                  >
                    Max
                  </button>
                </div>
                {walletData.available_balance < 50 && (
                  <p className="text-red-400 text-sm mt-2">
                    ⚠️ Faltam {formatCurrency(50 - walletData.available_balance)} para atingir o mínimo
                  </p>
                )}
              </div>
            )}

            {/* Action Buttons */}
            {walletData?.withdrawal_method && (
              <div className="flex gap-4">
                <button
                  onClick={handleWithdraw}
                  disabled={withdrawing || !withdrawAmount || parseFloat(withdrawAmount) < 50}
                  className="flex-1 bg-green-600 hover:bg-green-700 disabled:bg-slate-700 text-white px-6 py-2 rounded-lg font-semibold transition disabled:cursor-not-allowed"
                >
                  {withdrawing ? 'Processando...' : 'Confirmar Saque'}
                </button>
                <button
                  onClick={() => setShowWithdrawal(false)}
                  className="px-6 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg font-semibold transition"
                >
                  Cancelar
                </button>
              </div>
            )}
          </motion.div>
        )}

        {/* Transactions History */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.3 }}
          className="bg-slate-800/50 border border-slate-700 rounded-xl p-6 backdrop-blur"
        >
          <h2 className="text-xl font-bold text-white mb-6">📋 Histórico de Transações</h2>

          {transactions.length === 0 ? (
            <p className="text-gray-500 text-center py-8">Nenhuma transação ainda</p>
          ) : (
            <div className="space-y-3 max-h-96 overflow-y-auto">
              {transactions.map((tx) => (
                <motion.div
                  key={tx.id}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="bg-slate-700/50 border border-slate-600 rounded-lg p-4 flex justify-between items-center hover:bg-slate-700 transition"
                >
                  <div>
                    <p className="text-white font-semibold">
                      {tx.type === 'commission' ? '💰 Comissão' :
                       tx.type === 'withdrawal' ? '💳 Saque' :
                       tx.type === 'reversal' ? '⚠️ Reversão' :
                       '🔄 Reembolso'}
                    </p>
                    <p className="text-gray-400 text-sm">{tx.notes}</p>
                    <p className="text-gray-500 text-xs mt-1">{formatDate(tx.created_at)}</p>
                    
                    {/* Release countdown */}
                    {tx.status === 'pending' && tx.release_at && (
                      <p className="text-orange-400 text-xs mt-1">
                        ⏱️ Libera em {daysUntilRelease(tx.release_at)} dias
                      </p>
                    )}
                  </div>

                  <div className="text-right">
                    <p className="text-white font-bold">{formatCurrency(tx.amount_usd)}</p>
                    <span className={`text-xs px-2 py-1 rounded-full ${
                      tx.status === 'pending' ? 'bg-orange-500/20 text-orange-400' :
                      tx.status === 'available' ? 'bg-blue-500/20 text-blue-400' :
                      tx.status === 'completed' ? 'bg-green-500/20 text-green-400' :
                      'bg-red-500/20 text-red-400'
                    }`}>
                      {tx.status === 'pending' ? '⏳ Pendente' :
                       tx.status === 'available' ? '✅ Disponível' :
                       tx.status === 'completed' ? '✓ Completo' :
                       '✕ Falhou'}
                    </span>
                  </div>
                </motion.div>
              ))}
            </div>
          )}
        </motion.div>
      </div>
    </div>
  );
};

export default AffiliateDashboard;
