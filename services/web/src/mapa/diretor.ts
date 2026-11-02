// O diretor de animações: reproduz no mapa os eventos reais, na ordem, com um tempo mínimo
// para cada um. O agente pode andar mais rápido que a plateia consegue acompanhar; o mapa
// fica alguns segundos atrás e depois alcança. Nada é inventado: cada animação é um evento.

import { useCallback, useEffect, useReducer, useRef, useState } from 'react';

import type { EventoDaExecucao } from '../tipos';
import { type EstadoDaViagem, reduzir, VIAGEM_VAZIA } from './viagem';

// Quanto o robô leva entre duas paradas, e quanto fica parado na chegada.
export const DESLOCAMENTO_MS = 1600;
const PAUSA_NA_PARADA_MS = 600;

const RETENCAO_MS: Record<string, number> = {
  'run.started': 500,
  'skill.loaded': 700,
  'route.planned': 1300,
  'step.started': DESLOCAMENTO_MS + PAUSA_NA_PARADA_MS,
  'tool.called': 350,
  'incident.detected': 1600,
  'route.recalculated': 1600,
  'human.required': 1200,
  // O protocolo também tem seu tempo na tela, para o Raio-X ser lido em voz alta.
  'skills.listed': 500,
  'resource.read': 500,
  'skill.read': 400,
  'prompt.read': 300,
};

export interface Trecho {
  de: string | null; // parada de onde o robô sai (null: o ponto de partida do canal)
  para: string;
  inicio: number; // performance.now()
}

export interface Direcao {
  exibido: EstadoDaViagem; // o que o mapa mostra agora
  trecho: Trecho | null; // o deslocamento em curso (ou o último)
  fila: number; // eventos reais ainda não mostrados
  pularParaOFim: () => void;
}

export function useDiretor(real: EstadoDaViagem): Direcao {
  const [exibido, despachar] = useReducer(reduzir, VIAGEM_VAZIA);
  const [cursor, setCursor] = useState(0);
  const [trecho, setTrecho] = useState<Trecho | null>(null);
  const [pular, setPular] = useState(false);
  const aplicado = useRef(-1);
  const timer = useRef<number | undefined>(undefined);
  const paradaAtual = useRef<string | null>(null);

  // Nova execução: o diretor recomeça do zero.
  useEffect(() => {
    window.clearTimeout(timer.current);
    aplicado.current = -1;
    paradaAtual.current = null;
    despachar({ tipo: 'reiniciar', id: real.id });
    setCursor(0);
    setTrecho(null);
    setPular(false);
  }, [real.id]);

  const eventos: EventoDaExecucao[] = real.eventos;
  useEffect(() => {
    if (cursor >= eventos.length || aplicado.current === cursor) return;
    aplicado.current = cursor;
    const evento = eventos[cursor];
    if (evento.tipo === 'step.started') {
      setTrecho({ de: paradaAtual.current, para: evento.dados.id, inicio: performance.now() });
      paradaAtual.current = evento.dados.id;
    }
    despachar({ tipo: 'evento', evento });
    const espera = pular ? 0 : (RETENCAO_MS[evento.tipo] ?? 0);
    timer.current = window.setTimeout(() => setCursor((c) => c + 1), espera);
  }, [cursor, eventos, pular]);

  useEffect(() => () => window.clearTimeout(timer.current), []);

  const pularParaOFim = useCallback(() => setPular(true), []);
  return { exibido, trecho, fila: Math.max(eventos.length - cursor, 0), pularParaOFim };
}
