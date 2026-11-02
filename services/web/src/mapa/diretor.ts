// O diretor de animações: reproduz no mapa os eventos reais, na ordem, com um tempo mínimo
// para cada um. O agente pode andar mais rápido que a plateia consegue acompanhar; o mapa
// fica alguns segundos atrás e depois alcança. Nada é inventado: cada animação é um evento.
//
// O robô anda pelas ruas a cada evento que o leva a um lugar: um step.started (a placa da
// parada) ou um tool.called (o prédio do sistema chamado). O tempo do trecho vem da distância.

import { useCallback, useEffect, useReducer, useRef, useState } from 'react';

import type { EventoDaExecucao } from '../tipos';
import { type EstadoDaViagem, noDaTool, reduzir, VIAGEM_VAZIA } from './viagem';

const PAUSA_NA_PARADA_MS = 600;
const PULSO_MS = 350;

// --8<-- [start:retencao]
const RETENCAO_MS: Record<string, number> = {
  'run.started': 500,
  'skill.loaded': 700,
  'route.planned': 800,
  'step.started': PAUSA_NA_PARADA_MS, // mais o tempo de andar até a placa
  'tool.called': PULSO_MS, // mais o tempo de andar até o prédio
  'incident.detected': 1600,
  'route.recalculated': 1600,
  'human.required': 1200,
  // O protocolo também tem seu tempo na tela, para o Raio-X ser lido em voz alta.
  'skills.listed': 500,
  'resource.read': 500,
  'skill.read': 400,
  'prompt.read': 300,
};
// --8<-- [end:retencao]

// De onde o robô sai: o canal da viagem.
export const PONTO_DE_PARTIDA: Record<string, string> = {
  app: 'canal-app',
  agencia: 'canal-agencia',
  central: 'canal-central',
};

export interface Trecho {
  de: string; // o lugar de onde o robô sai
  para: string; // o lugar aonde ele vai
  inicio: number; // performance.now()
  duracao: number; // ms
  ok: boolean; // a chamada deu certo? (um trecho até um prédio fora do ar termina em vermelho)
}

export interface Direcao {
  exibido: EstadoDaViagem; // o que o mapa mostra agora
  partida: string | null; // o lugar de onde o robô saiu
  trechos: Trecho[]; // todos os trechos já começados, na ordem: o último é o atual
  fila: number; // eventos reais ainda não mostrados
  pularParaOFim: () => void;
}

// O lugar aonde um evento leva o robô (ou null, se ele não sai do lugar).
function destino(evento: EventoDaExecucao): string | null {
  if (evento.tipo === 'step.started') return evento.dados.id ?? null;
  if (evento.tipo === 'tool.called') return noDaTool(evento.dados.tool, evento.dados.argumentos);
  return null;
}

export function useDiretor(
  real: EstadoDaViagem,
  tempoDoTrecho: (de: string, para: string) => number | null, // ms, ou null se não há caminho
): Direcao {
  const [exibido, despachar] = useReducer(reduzir, VIAGEM_VAZIA);
  const [cursor, setCursor] = useState(0);
  const [partida, setPartida] = useState<string | null>(null);
  const [trechos, setTrechos] = useState<Trecho[]>([]);
  const [pular, setPular] = useState(false);
  const aplicado = useRef(-1);
  const timer = useRef<number | undefined>(undefined);
  const lugarAtual = useRef<string | null>(null);
  const tempo = useRef(tempoDoTrecho);
  tempo.current = tempoDoTrecho;

  // Nova execução: o diretor recomeça do zero.
  useEffect(() => {
    window.clearTimeout(timer.current);
    aplicado.current = -1;
    lugarAtual.current = null;
    despachar({ tipo: 'reiniciar', id: real.id });
    setCursor(0);
    setPartida(null);
    setTrechos([]);
    setPular(false);
  }, [real.id]);

  const eventos: EventoDaExecucao[] = real.eventos;
  useEffect(() => {
    if (cursor >= eventos.length || aplicado.current === cursor) return;
    aplicado.current = cursor;
    const evento = eventos[cursor];
    let andar = 0;
    if (evento.tipo === 'run.started') {
      lugarAtual.current = PONTO_DE_PARTIDA[evento.dados.canal] ?? 'canal-app';
      setPartida(lugarAtual.current);
    }
    const para = destino(evento);
    const de = lugarAtual.current;
    if (para && de && para !== de) {
      const duracao = tempo.current(de, para);
      if (duracao != null) {
        const ok = evento.tipo !== 'tool.called' || evento.dados.status === 'ok';
        setTrechos((t) => [...t, { de, para, inicio: performance.now(), duracao: pular ? 0 : duracao, ok }]);
        lugarAtual.current = para;
        andar = duracao;
      }
    }
    despachar({ tipo: 'evento', evento });
    const espera = pular ? 0 : andar + (RETENCAO_MS[evento.tipo] ?? 0);
    timer.current = window.setTimeout(() => setCursor((c) => c + 1), espera);
  }, [cursor, eventos, pular]);

  useEffect(() => () => window.clearTimeout(timer.current), []);

  const pularParaOFim = useCallback(() => setPular(true), []);
  return { exibido, partida, trechos, fila: Math.max(eventos.length - cursor, 0), pularParaOFim };
}
