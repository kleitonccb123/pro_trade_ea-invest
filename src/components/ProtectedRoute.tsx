import { Navigate } from 'react-router-dom';
import { useAuthStore } from '../context/AuthContext';

interface ProtectedRouteProps {
  children: React.ReactNode;
}

export default function ProtectedRoute({ children }: ProtectedRouteProps) {
  const { isAuthenticated, isLoading, isHydrated } = useAuthStore();

  console.log('[ProtectedRoute] Status:', { isAuthenticated, isLoading, isHydrated });

  // ✅ Esperar pela rehydratação do Zustand
  if (!isHydrated) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-black flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <div className="w-12 h-12 border-4 border-yellow-500/20 border-t-yellow-400 rounded-full animate-spin"></div>
          <p className="text-slate-400">Carregando sessão...</p>
        </div>
      </div>
    );
  }

  // ✅ Após hidratação, mostrar carregamento apenas se checkAuth ainda rodando
  if (isLoading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-black flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <div className="w-12 h-12 border-4 border-yellow-500/20 border-t-yellow-400 rounded-full animate-spin"></div>
          <p className="text-slate-400">Validando token...</p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    console.log('[ProtectedRoute] Redirecting to login');
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}
