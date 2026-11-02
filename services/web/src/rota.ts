// Rotas do dashboard sobre o history do navegador, sem biblioteca de roteamento:
//   /status/{aba}          a aba aberta
//   /status/{aba}/{item}   o painel lateral daquele item (link compartilhável)

import { useCallback, useState } from 'react';

import { useMudancaDeEndereco } from './navegacao';

export const ABAS = ['servicos', 'tools', 'skills', 'prompts'] as const;
export type Aba = (typeof ABAS)[number];

export interface Rota {
  aba: Aba;
  item: string | null;
}

function ler(): Rota {
  const [, raiz, aba, ...resto] = window.location.pathname.split('/');
  if (raiz !== 'status') return { aba: 'servicos', item: null };
  return {
    aba: (ABAS as readonly string[]).includes(aba) ? (aba as Aba) : 'servicos',
    item: resto.length ? decodeURIComponent(resto.join('/')) : null,
  };
}

const caminho = (r: Rota) => `/status/${r.aba}${r.item ? `/${encodeURIComponent(r.item)}` : ''}`;

export function useRota(): [Rota, (rota: Rota) => void] {
  const [rota, setRota] = useState<Rota>(ler);

  // Voltar/avançar do navegador e navegação vinda de outras páginas (ex.: /status no cabeçalho).
  useMudancaDeEndereco(useCallback(() => setRota(ler()), []));

  const ir = useCallback((nova: Rota) => {
    if (caminho(nova) !== window.location.pathname) window.history.pushState(null, '', caminho(nova));
    setRota(nova);
  }, []);

  return [rota, ir];
}
