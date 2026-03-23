import { useLanguage } from '@/hooks/use-language';
import { FileText, ArrowLeft } from 'lucide-react';
import { Link } from 'react-router-dom';

export default function TermsOfService() {
  const { t } = useLanguage();

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 px-4 py-12">
      <div className="max-w-4xl mx-auto">
        <Link to="/login" className="inline-flex items-center gap-2 text-indigo-400 hover:text-indigo-300 mb-8 transition-colors">
          <ArrowLeft className="w-4 h-4" />
          Voltar
        </Link>

        <div className="flex items-center gap-4 mb-8">
          <div className="w-14 h-14 rounded-lg bg-gradient-to-br from-emerald-600 to-emerald-700 flex items-center justify-center shadow-lg">
            <FileText className="w-7 h-7 text-white" />
          </div>
          <div>
            <h1 className="text-3xl font-bold text-white">Termos de Serviço</h1>
            <p className="text-slate-400">Última atualização: 10 de março de 2026</p>
          </div>
        </div>

        <div className="glass-card p-8 rounded-xl border border-slate-700 bg-gradient-to-br from-slate-800/50 to-slate-900/50 prose prose-invert max-w-none space-y-6">
          <section>
            <h2 className="text-xl font-bold text-emerald-400">1. Aceitação dos Termos</h2>
            <p className="text-slate-300 leading-relaxed">
              Ao utilizar a plataforma Crypto Trade Hub, você concorda com estes Termos de Serviço.
              Caso não concorde, não utilize o serviço. Reservamo-nos o direito de alterar estes termos
              a qualquer momento, notificando os usuários sobre mudanças significativas.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-bold text-emerald-400">2. Descrição do Serviço</h2>
            <p className="text-slate-300 leading-relaxed">
              A Crypto Trade Hub é uma plataforma SaaS de automação de trading de criptomoedas que oferece:
            </p>
            <ul className="text-slate-300 list-disc list-inside space-y-1">
              <li>Robôs de trading automatizado configuráveis</li>
              <li>Ferramentas de análise e monitoramento</li>
              <li>Conteúdo educacional sobre trading</li>
              <li>Sistema de gamificação e ranking</li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-bold text-emerald-400">3. Isenção de Responsabilidade — Risco Financeiro</h2>
            <p className="text-slate-300 leading-relaxed font-semibold text-amber-300">
              ⚠️ AVISO IMPORTANTE: O trading de criptomoedas envolve riscos significativos de perda financeira.
            </p>
            <ul className="text-slate-300 list-disc list-inside space-y-1">
              <li>Resultados passados <strong>não</strong> garantem resultados futuros</li>
              <li>A plataforma NÃO é uma consultoria financeira</li>
              <li>Você é o único responsável por suas decisões de investimento</li>
              <li>Nunca invista mais do que pode perder</li>
              <li>A Crypto Trade Hub não se responsabiliza por perdas decorrentes do uso de robôs automatizados</li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-bold text-emerald-400">4. Conta e Segurança</h2>
            <ul className="text-slate-300 list-disc list-inside space-y-1">
              <li>Você é responsável por manter a segurança de sua conta</li>
              <li>Recomendamos fortemente ativar a autenticação em dois fatores (2FA)</li>
              <li>Nunca compartilhe suas credenciais de acesso</li>
              <li>Notifique-nos imediatamente sobre qualquer uso não autorizado</li>
              <li>Contas inativas por mais de 12 meses podem ser desativadas</li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-bold text-emerald-400">5. Chaves API de Exchange</h2>
            <ul className="text-slate-300 list-disc list-inside space-y-1">
              <li>Configure suas chaves API com permissões mínimas necessárias (apenas trading)</li>
              <li>NUNCA habilite permissão de saque (withdrawal) nas chaves API</li>
              <li>Suas chaves são criptografadas em nossos servidores com AES-128</li>
              <li>Você pode remover suas chaves a qualquer momento em Configurações</li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-bold text-emerald-400">6. Uso Aceitável</h2>
            <p className="text-slate-300 leading-relaxed">É proibido:</p>
            <ul className="text-slate-300 list-disc list-inside space-y-1">
              <li>Usar a plataforma para atividades ilegais (lavagem de dinheiro, financiamento de terrorismo)</li>
              <li>Tentar acessar contas de outros usuários</li>
              <li>Explorar vulnerabilidades do sistema sem autorização</li>
              <li>Criar múltiplas contas para burlar limites ou promoções</li>
              <li>Realizar engenharia reversa da plataforma</li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-bold text-emerald-400">7. Planos e Pagamentos</h2>
            <ul className="text-slate-300 list-disc list-inside space-y-1">
              <li>Os planos são cobrados conforme indicado no momento da assinatura</li>
              <li>Renovação automática pode ser cancelada a qualquer momento</li>
              <li>Reembolsos seguem a política vigente no momento da compra</li>
              <li>A plataforma pode alterar preços com aviso prévio de 30 dias</li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-bold text-emerald-400">8. Interrupção do Serviço</h2>
            <p className="text-slate-300 leading-relaxed">
              A Crypto Trade Hub não garante disponibilidade ininterrupta. O serviço pode ser 
              interrompido para manutenção, atualizações ou por fatores fora de nosso controle 
              (exchanges offline, falhas de rede). Recomendamos sempre configurar stop-loss em suas operações.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-bold text-emerald-400">9. Propriedade Intelectual</h2>
            <p className="text-slate-300 leading-relaxed">
              Todo o código, design, conteúdo e marca da Crypto Trade Hub são propriedade da plataforma.
              Estratégias criadas por você são de sua propriedade intelectual.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-bold text-emerald-400">10. Privacidade</h2>
            <p className="text-slate-300 leading-relaxed">
              O tratamento de dados pessoais é regido pela nossa{' '}
              <Link to="/privacy-policy" className="text-indigo-400 hover:text-indigo-300 underline">
                Política de Privacidade
              </Link>
              , que faz parte integral destes Termos de Serviço.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-bold text-emerald-400">11. Lei Aplicável</h2>
            <p className="text-slate-300 leading-relaxed">
              Estes termos são regidos pelas leis da República Federativa do Brasil. 
              Qualquer disputa será resolvida pelo foro da comarca da sede da empresa.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-bold text-emerald-400">12. Contato</h2>
            <p className="text-slate-300 leading-relaxed">
              Dúvidas sobre estes termos: <span className="text-indigo-400">suporte@cryptotradehub.com</span>
            </p>
          </section>
        </div>
      </div>
    </div>
  );
}
