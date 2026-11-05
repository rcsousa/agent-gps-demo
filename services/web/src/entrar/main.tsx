// Ponto de entrada da tela de login: um build à parte (vite.entrar.config.ts), público,
// que não carrega nada da experiência. Tudo o mais exige sessão.
import '@fontsource/ibm-plex-sans/400.css';
import '@fontsource/ibm-plex-sans/600.css';
import '../estilos/entrar.scss';

import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

import { PaginaEntrar } from './PaginaEntrar';

createRoot(document.getElementById('raiz')!).render(
  <StrictMode>
    <PaginaEntrar />
  </StrictMode>,
);
