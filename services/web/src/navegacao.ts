// Páginas do site sobre o history do navegador, sem biblioteca de roteamento:
//   /          tela de abertura (o infográfico navegável)
//   /mapa      Modo Mapa (?execucao=, ?modo=, ?cena=, ?parada=)
//   /status    dashboard de status (abas e painel lateral: veja rota.ts)

import { useEffect, useState } from 'react';

export type Pagina = 'abertura' | 'mapa' | 'status';

const EVENTO = 'bussola:navegou';

export function paginaAtual(): Pagina {
  const caminho = window.location.pathname;
  if (caminho.startsWith('/status')) return 'status';
  if (caminho.startsWith('/mapa')) return 'mapa';
  return 'abertura';
}

// Navega sem recarregar a página; os hooks de página e de rota ouvem a mudança.
export function navegar(destino: string, substituir = false) {
  if (destino.startsWith('/bastidores')) {
    window.location.assign(destino); // site de documentação, fora do app
    return;
  }
  if (destino !== window.location.pathname + window.location.search) {
    window.history[substituir ? 'replaceState' : 'pushState'](null, '', destino);
  }
  window.dispatchEvent(new Event(EVENTO));
}

export function useMudancaDeEndereco(aoMudar: () => void) {
  useEffect(() => {
    window.addEventListener('popstate', aoMudar);
    window.addEventListener(EVENTO, aoMudar);
    return () => {
      window.removeEventListener('popstate', aoMudar);
      window.removeEventListener(EVENTO, aoMudar);
    };
  }, [aoMudar]);
}

export function usePagina(): Pagina {
  const [pagina, setPagina] = useState<Pagina>(paginaAtual);
  useMudancaDeEndereco(() => setPagina(paginaAtual()));
  return pagina;
}

export function parametro(nome: string): string | null {
  return new URLSearchParams(window.location.search).get(nome);
}

// Link de verdade (abre em outra aba, copia a URL) que navega sem recarregar.
export function aoClicarLink(destino: string) {
  return (evento: { preventDefault: () => void; ctrlKey?: boolean; metaKey?: boolean }) => {
    if (evento.ctrlKey || evento.metaKey) return;
    evento.preventDefault();
    navegar(destino);
  };
}
