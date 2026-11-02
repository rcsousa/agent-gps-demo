// Modo telão: a interface inteira fica maior (a fonte-base do html sobe 25%), para ser lida a 5 m
// num Full HD. Liga e desliga pela tecla T ou pelo painel do apresentador; fica guardado no navegador.

import { useEffect, useState } from 'react';

const CHAVE = 'bussola:telao';
const EVENTO = 'bussola:telao';
export const ESCALA_DO_TELAO = 1.25;

const ligadoAgora = () => localStorage.getItem(CHAVE) === 'sim';

function aplicar(ligado: boolean) {
  document.documentElement.classList.toggle('telao', ligado);
}
aplicar(ligadoAgora());

export function definirTelao(ligado: boolean) {
  localStorage.setItem(CHAVE, ligado ? 'sim' : 'nao');
  aplicar(ligado);
  window.dispatchEvent(new CustomEvent(EVENTO));
}

export const alternarTelao = () => definirTelao(!ligadoAgora());

// O estado do telão, para quem precisa medir em pixels (rótulos, balão, robô).
export function useTelao(): { ligado: boolean; escala: number } {
  const [ligado, setLigado] = useState(ligadoAgora);
  useEffect(() => {
    const atualizar = () => setLigado(ligadoAgora());
    window.addEventListener(EVENTO, atualizar);
    return () => window.removeEventListener(EVENTO, atualizar);
  }, []);
  return { ligado, escala: ligado ? ESCALA_DO_TELAO : 1 };
}

// Movimento reduzido (preferência do sistema): sem giros nem voos de câmera animados.
export const movimentoReduzido = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;
