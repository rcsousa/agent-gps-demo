// A voz do GPS: fala os anúncios com a síntese de voz do navegador, em português do Brasil.
// Funciona sem rede (usa as vozes do sistema: Microsoft Maria no Windows, Luciana no macOS...).
// Opcional e desligada por padrão; a escolha fica guardada no navegador.

import { useEffect, useState } from 'react';

const CHAVE = 'bussola:voz';
// Vozes conhecidas e mais naturais primeiro; qualquer outra pt-BR serve.
const PREFERIDAS = [/maria/i, /luciana/i, /francisca/i, /thalita/i, /google.*portugu/i, /natural/i];
const RITMO = 1.05;

function sintese(): SpeechSynthesis | null {
  return typeof window !== 'undefined' && 'speechSynthesis' in window ? window.speechSynthesis : null;
}

export function vozEmPortugues(): SpeechSynthesisVoice | null {
  const vozes = sintese()?.getVoices() ?? [];
  const ptBr = vozes.filter((v) => v.lang.replace('_', '-').toLowerCase() === 'pt-br');
  for (const preferida of PREFERIDAS) {
    const achada = ptBr.find((v) => preferida.test(v.name));
    if (achada) return achada;
  }
  return ptBr[0] ?? null;
}

export function calar(): void {
  sintese()?.cancel();
}

// Fala o texto e resolve quando terminar (ou falhar). Uma fala nova interrompe a anterior.
// Um teto de tempo garante que a viagem nunca trava esperando uma voz que não respondeu.
export function falar(texto: string): Promise<void> {
  const s = sintese();
  const voz = vozEmPortugues();
  if (!s || !voz || !texto) return Promise.resolve();
  s.cancel();
  return new Promise((resolver) => {
    const fala = new SpeechSynthesisUtterance(texto);
    fala.voice = voz;
    fala.lang = 'pt-BR';
    fala.rate = RITMO;
    const teto = window.setTimeout(resolver, 2000 + texto.length * 90);
    const fim = () => {
      window.clearTimeout(teto);
      resolver();
    };
    fala.onend = fim;
    fala.onerror = fim;
    s.speak(fala);
  });
}

// Ligada ou não (guardado), e se este navegador tem uma voz pt-BR (as vozes carregam depois).
export function useVoz(): { ligada: boolean; setLigada: (v: boolean) => void; disponivel: boolean } {
  const [ligada, setLigada] = useState(() => {
    try {
      return localStorage.getItem(CHAVE) === 'sim';
    } catch {
      return false;
    }
  });
  const [disponivel, setDisponivel] = useState(() => vozEmPortugues() != null);
  useEffect(() => {
    const s = sintese();
    if (!s) return;
    const atualizar = () => setDisponivel(vozEmPortugues() != null);
    atualizar();
    s.addEventListener('voiceschanged', atualizar);
    return () => s.removeEventListener('voiceschanged', atualizar);
  }, []);
  useEffect(() => {
    try {
      localStorage.setItem(CHAVE, ligada ? 'sim' : 'nao');
    } catch {
      // sem armazenamento: vale só nesta aba
    }
    if (!ligada) calar();
  }, [ligada]);
  return { ligada: ligada && disponivel, setLigada, disponivel };
}
