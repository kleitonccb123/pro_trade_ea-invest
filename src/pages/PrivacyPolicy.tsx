import { useLanguage } from '@/hooks/use-language';
import { Shield, ArrowLeft } from 'lucide-react';
import { Link } from 'react-router-dom';

export default function PrivacyPolicy() {
  const { t } = useLanguage();

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 px-4 py-12">
      <div className="max-w-4xl mx-auto">
        <Link to="/login" className="inline-flex items-center gap-2 text-indigo-400 hover:text-indigo-300 mb-8 transition-colors">
          <ArrowLeft className="w-4 h-4" />
          Voltar
        </Link>

        <div className="flex items-center gap-4 mb-8">
          <div className="w-14 h-14 rounded-lg bg-gradient-to-br from-indigo-600 to-indigo-700 flex items-center justify-center shadow-lg">
            <Shield className="w-7 h-7 text-white" />
          </div>
          <div>
            <h1 className="text-3xl font-bold text-white">Política de Privacidade</h1>
            <p className="text-slate-400">Última atualização: 10 de março de 2026</p>
          </div>
        </div>

        <div className="glass-card p-8 rounded-xl border border-slate-700 bg-gradient-to-br from-slate-800/50 to-slate-900/50 prose prose-invert max-w-none space-y-6">
          <section>
            <h2 className="text-xl font-bold text-indigo-400">1. Introdução</h2>
            <p className="text-slate-300 leading-relaxed">
              A Crypto Trade Hub ("nós", "nosso" ou "plataforma") está comprometida com a proteção 
              de seus dados pessoais, em conformidade com a Lei Geral de Proteção de Dados (LGPD — Lei nº 13.709/2018). 
              Esta política descreve como coletamos, usamos, armazenamos e protegemos suas informações.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-bold text-indigo-400">2. Dados Coletados</h2>
            <p className="text-slate-300 leading-relaxed">Coletamos os seguintes tipos de dados:</p>
            <ul className="text-slate-300 list-disc list-inside space-y-1">
              <li><strong>Dados de cadastro:</strong> nome, email, senha (criptografada)</li>
              <li><strong>Dados de uso:</strong> logs de acesso, endereço IP, user-agent</li>
              <li><strong>Dados financeiros:</strong> histórico de trades, configurações de bots, saldo (via API da exchange)</li>
              <li><strong>Dados de exchange:</strong> chaves API (criptografadas com Fernet — nunca armazenamos em texto puro)</li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-bold text-indigo-400">3. Finalidade do Tratamento</h2>
            <ul className="text-slate-300 list-disc list-inside space-y-1">
              <li>Prestação do serviço de automação de trading</li>
              <li>Autenticação e segurança da conta</li>
              <li>Comunicação sobre status das operações e alertas</li>
              <li>Melhoria contínua da plataforma</li>
              <li>Cumprimento de obrigações legais</li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-bold text-indigo-400">4. Base Legal (Art. 7º LGPD)</h2>
            <ul className="text-slate-300 list-disc list-inside space-y-1">
              <li><strong>Consentimento:</strong> ao criar sua conta e aceitar os termos</li>
              <li><strong>Execução de contrato:</strong> para prestação do serviço</li>
              <li><strong>Legítimo interesse:</strong> para melhoria do serviço e segurança</li>
              <li><strong>Obrigação legal:</strong> retenção de registros financeiros</li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-bold text-indigo-400">5. Seus Direitos (Art. 18 LGPD)</h2>
            <p className="text-slate-300 leading-relaxed">Você tem direito a:</p>
            <ul className="text-slate-300 list-disc list-inside space-y-1">
              <li><strong>Acesso:</strong> obter cópia de todos os seus dados pessoais</li>
              <li><strong>Correção:</strong> atualizar dados incompletos ou incorretos</li>
              <li><strong>Anonimização/Bloqueio:</strong> solicitar anonimização de dados desnecessários</li>
              <li><strong>Eliminação:</strong> excluir sua conta e dados pessoais</li>
              <li><strong>Portabilidade:</strong> exportar seus dados para outro serviço</li>
              <li><strong>Revogação:</strong> retirar seu consentimento a qualquer momento</li>
            </ul>
            <p className="text-slate-300 leading-relaxed mt-2">
              Para exercer seus direitos, acesse <strong>Configurações → Privacidade & Dados</strong> em sua conta,
              ou entre em contato com nosso DPO pelo email <span className="text-indigo-400">privacidade@cryptotradehub.com</span>.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-bold text-indigo-400">6. Segurança dos Dados</h2>
            <ul className="text-slate-300 list-disc list-inside space-y-1">
              <li>Senhas armazenadas com hash bcrypt</li>
              <li>Credenciais de exchange criptografadas com Fernet (AES-128-CBC)</li>
              <li>Tokens JWT com expiração curta (15 min) + refresh via httpOnly cookie</li>
              <li>Autenticação 2FA disponível (TOTP)</li>
              <li>Rate limiting para prevenir ataques de força bruta</li>
              <li>HTTPS obrigatório em produção (HSTS habilitado)</li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-bold text-indigo-400">7. Retenção de Dados</h2>
            <p className="text-slate-300 leading-relaxed">
              Dados da conta são retidos enquanto ela estiver ativa. Após solicitação de exclusão,
              os dados são removidos em até 30 dias, exceto registros financeiros que podem ser 
              retidos por até 5 anos conforme obrigação legal.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-bold text-indigo-400">8. Compartilhamento</h2>
            <p className="text-slate-300 leading-relaxed">
              Não vendemos nem compartilhamos seus dados pessoais com terceiros para fins de marketing. 
              Dados podem ser compartilhados com:
            </p>
            <ul className="text-slate-300 list-disc list-inside space-y-1">
              <li>Exchanges de criptomoedas (apenas chaves API necessárias para operar)</li>
              <li>Provedores de infraestrutura (servidor, banco de dados) com contratos de confidencialidade</li>
              <li>Autoridades judiciais quando exigido por lei</li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-bold text-indigo-400">9. Contato do DPO</h2>
            <p className="text-slate-300 leading-relaxed">
              Encarregado de Proteção de Dados (DPO):<br />
              Email: <span className="text-indigo-400">privacidade@cryptotradehub.com</span><br />
              Prazo de resposta: até 15 dias úteis
            </p>
          </section>
        </div>
      </div>
    </div>
  );
}
