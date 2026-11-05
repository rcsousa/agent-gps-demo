// A sessão do lado do navegador. Quem garante o acesso é o nginx (cada requisição passa pelo auth);
// aqui só se reage a uma sessão que venceu no meio do uso e se oferece o "Sair".

import { useEffect, useState } from 'react';

export function irParaOLogin(): void {
  const destino = window.location.pathname + window.location.search + window.location.hash;
  window.location.replace(`/entrar/?volta=${encodeURIComponent(destino)}`);
}

function ehDaDemo(entrada: RequestInfo | URL): boolean {
  const url = new URL(entrada instanceof Request ? entrada.url : String(entrada), window.location.href);
  return url.origin === window.location.origin && /^\/(api|simulador)\//.test(url.pathname);
}

// Uma chamada de dados que volta 401 quer dizer que a sessão venceu: leva ao login, guardando
// onde a pessoa estava. Vale para todos os fetch do app, inclusive a consulta da viagem.
let vigiando = false;
export function vigiarSessao(): void {
  if (vigiando) return;
  vigiando = true;
  const original = window.fetch.bind(window);
  window.fetch = async (entrada: RequestInfo | URL, opcoes?: RequestInit) => {
    const resposta = await original(entrada, opcoes);
    if (resposta.status === 401 && ehDaDemo(entrada)) irParaOLogin();
    return resposta;
  };
}

export async function sair(): Promise<void> {
  try {
    await fetch('/auth/sair', { method: 'POST' });
  } finally {
    window.location.replace('/entrar/');
  }
}

export function useUsuario(): string | null {
  const [usuario, setUsuario] = useState<string | null>(null);
  useEffect(() => {
    fetch('/auth/eu', { cache: 'no-store' })
      .then((resposta) => (resposta.ok ? resposta.json() : null))
      .then((corpo) => setUsuario(corpo?.usuario ?? null))
      .catch(() => setUsuario(null));
  }, []);
  return usuario;
}
