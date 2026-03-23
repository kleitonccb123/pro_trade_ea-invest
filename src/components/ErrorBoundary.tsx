import React, { Component, ReactNode, ErrorInfo } from 'react';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { 
      hasError: false,
      error: null,
      errorInfo: null,
    };
  }

  static getDerivedStateFromError(error: Error): State {
    return { 
      hasError: true,
      error,
      errorInfo: null,
    };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('[ErrorBoundary] Erro capturado:', error, errorInfo);
    
    this.setState({
      errorInfo,
    });
    
    // Aqui você poderia enviar o erro para um serviço de logging
    // logErrorToService(error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-gradient-to-b from-background via-background to-primary/5 flex items-center justify-center p-4">
          <div className="max-w-md mx-auto">
            <div className="bg-red-950/50 border border-red-500/50 rounded-lg p-6">
              <h1 className="text-2xl font-bold text-red-400 mb-4">⚠️ Erro na Aplicação</h1>
              
              <div className="bg-black/50 rounded p-4 max-h-96 overflow-auto mb-4">
                <p className="text-red-300 text-sm font-mono break-words">
                  {this.state.error?.toString()}
                </p>
                
                {this.state.errorInfo && (
                  <div className="mt-4 text-red-200 text-xs">
                    <p className="font-bold mb-2">Stack Trace:</p>
                    <pre className="overflow-auto whitespace-pre-wrap break-words">
                      {this.state.errorInfo.componentStack}
                    </pre>
                  </div>
                )}
              </div>
              
              <button
                onClick={() => window.location.reload()}
                className="w-full bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded transition"
              >
                🔄 Recarregar Página
              </button>
              
              <button
                onClick={() => window.location.href = '/login'}
                className="w-full bg-slate-600 hover:bg-slate-700 text-white font-bold py-2 px-4 rounded transition mt-2"
              >
                🔑 Ir para Login
              </button>

              <p className="text-slate-400 text-sm mt-4 text-center">
                Se o erro persistir, contate o suporte.
              </p>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
