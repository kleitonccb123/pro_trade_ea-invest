import { useEffect } from "react";
import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { LanguageProvider } from "@/hooks/use-language";
import { LicenseProvider } from "@/hooks/use-license";
import { useTokenRefreshMonitoring } from "@/hooks/use-token-refresh-monitoring";
import { AppLayout } from "@/components/layout";
import { useAuthStore } from "@/context/AuthContext";
import { ConnectionStatusProvider } from "@/context/ConnectionStatusContext";
import ProtectedRoute from "@/components/ProtectedRoute";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { BackendStatusBanner } from "@/components/BackendStatusBanner";

// P3-10: Crisp support chat — configure VITE_CRISP_WEBSITE_ID in .env to enable
function CrispWidget() {
  useEffect(() => {
    const crispId = import.meta.env.VITE_CRISP_WEBSITE_ID as string | undefined;
    if (!crispId) return;
    (window as Record<string, unknown>).$crisp = [];
    (window as Record<string, unknown>).CRISP_WEBSITE_ID = crispId;
    const script = document.createElement('script');
    script.src = 'https://client.crisp.chat/l.js';
    script.async = true;
    document.head.appendChild(script);
  }, []);
  return null;
}

console.log('[App.tsx] Importações carregadas com sucesso');

// Auth pages
import Login from "./pages/Login";
import Signup from "./pages/Signup";
import AuthCallback from "./pages/AuthCallback";
import ForgotPassword from "./pages/ForgotPassword";
import TwoFactorVerify from "./components/auth/TwoFactorVerify";

// App pages
import Dashboard from "./pages/Dashboard";
import Robots from "./pages/Robots";
import CryptoRobots from "./pages/CryptoRobots";
import RobotsPage from "./pages/RobotsPage";
import RobotsGameMarketplace from "./pages/RobotsGameMarketplace";
import Settings from "./pages/Settings";
import VideoAulas from "./pages/VideoAulas";
import Affiliate from "./pages/Affiliate";
import Strategy from "./pages/Strategy";
import { StrategySubmission } from "./pages/StrategySubmission";
import MyStrategies from "./pages/MyStrategies";
import PublicStrategies from "./pages/PublicStrategies";
import StrategiesPageImproved from "./pages/StrategiesPageImproved";
import BacktestPage from "./pages/BacktestPage";
import PerformanceDashboard from "./pages/PerformanceDashboard";
import KuCoinConnection from "./pages/KuCoinConnection";
import Licenses from "./pages/Licenses";
import WalletPage from "./pages/WalletPage";

import NotFound from "./pages/NotFound";
import PrivacyPolicy from "./pages/PrivacyPolicy";
import TermsOfService from "./pages/TermsOfService";

const queryClient = new QueryClient();

const AppContent = () => {
  const { checkAuth, isHydrated, isAuthenticated } = useAuthStore();
  
  console.log('[AppContent] Renderizando...');

  // Monitor token refresh and handle WebSocket reconnection
  useTokenRefreshMonitoring();

  useEffect(() => {
    // ✅ WAIT FOR HYDRATION BEFORE VALIDATING
    if (!isHydrated) {
      console.log('[AppContent] Aguardando rehydratação...');
      return;
    }

    // ✅ ONLY VALIDATE TOKEN IF USER IS AUTHENTICATED
    if (isAuthenticated) {
      console.log('[AppContent] Validando token autenticado...');
      checkAuth();
    } else {
      console.log('[AppContent] Usuário não autenticado, pulando validação');
    }
  }, [isHydrated, isAuthenticated]);

  return (
    <Routes>
      {/* Redirect root to login */}
      <Route path="/" element={<Navigate to="/dashboard" replace />} />
      
      {/* Auth routes */}
      <Route path="/login" element={<Login />} />
      <Route path="/signup" element={<Signup />} />
      <Route path="/auth-callback" element={<AuthCallback />} />
      <Route path="/forgot-password" element={<ForgotPassword />} />
      <Route path="/2fa-verify" element={<TwoFactorVerify />} />
      
      {/* Public routes */}
      {/* LGPD: Legal pages */}
      <Route path="/privacy-policy" element={<PrivacyPolicy />} />
      <Route path="/terms-of-service" element={<TermsOfService />} />
      
      {/* App routes with layout - Protected */}
      <Route
        element={
          <ProtectedRoute>
            <AppLayout />
          </ProtectedRoute>
        }
      >
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/strategies" element={<StrategiesPageImproved />} />
        <Route path="/strategies/legacy" element={<PublicStrategies />} />
        <Route path="/robots" element={<RobotsGameMarketplace />} />
        <Route path="/robots/crypto" element={<CryptoRobots />} />
        <Route path="/strategy" element={<Strategy />} />
        <Route path="/strategy/submit" element={<StrategySubmission />} />
        <Route path="/my-strategies" element={<MyStrategies />} />
        <Route path="/backtest" element={<BacktestPage />} />
        <Route path="/performance" element={<PerformanceDashboard />} />
        <Route path="/video-aulas" element={<VideoAulas />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="/affiliate" element={<Affiliate />} />
        <Route path="/licenses" element={<Licenses />} />
        <Route path="/kucoin" element={<KuCoinConnection />} />
        <Route path="/ea-monitor" element={<WalletPage />} />
      </Route>
      
      {/* Catch-all */}
      <Route path="*" element={<NotFound />} />
    </Routes>
  );
};

const App = () => (
  <ErrorBoundary>
    <LanguageProvider>
      <QueryClientProvider client={queryClient}>
        <TooltipProvider>
          <LicenseProvider>
            <ConnectionStatusProvider>
              <CrispWidget />
              <BackendStatusBanner />
              <Toaster />
              <Sonner />
              <BrowserRouter>
                <AppContent />
              </BrowserRouter>
            </ConnectionStatusProvider>
          </LicenseProvider>
        </TooltipProvider>
      </QueryClientProvider>
    </LanguageProvider>
  </ErrorBoundary>
);

export default App;
