import { createRoot } from "react-dom/client";
import { GoogleOAuthProvider } from '@react-oauth/google';
import App from "./App.tsx";
import "./index.css";
import "./styles/tokens.css";

console.log('[APP] Iniciando aplicação...');

const googleClientId = import.meta.env.VITE_GOOGLE_CLIENT_ID || "477006347863-4c65hjv7hck8qegdu830vcfd6olpror0.apps.googleusercontent.com";
console.log('[APP] Google Client ID:', googleClientId.substring(0, 20) + '...');

const rootElement = document.getElementById("root");
if (!rootElement) {
  console.error('[APP] 🚨 Root element não encontrado!');
  throw new Error('Root element (#root) not found in index.html');
}

console.log('[APP] Root element encontrado, renderizando aplicação...');

createRoot(rootElement).render(
  <GoogleOAuthProvider clientId={googleClientId}>
    <App />
  </GoogleOAuthProvider>
);

console.log('[APP] ✅ Aplicação renderizada com sucesso!');
