// O diretor de animações: reproduz no mapa os eventos reais, na ordem, com um tempo mínimo
// para cada um. O agente pode andar mais rápido que a plateia consegue acompanhar; o mapa
// fica alguns segundos atrás e depois alcança. Nada é inventado: cada animação é um evento.
//
// O robô anda pelas ruas a cada evento que o leva a um lugar: um step.started (a placa da
// parada) ou um tool.called (o prédio do sistema chamado). O tempo do trecho vem da distância.
//
// Ao chegar, o robô abre um balão de fala: o anúncio do GPS (a apresentação, o roteiro, a rota, cada
// parada, cada sistema chamado, incidentes, recálculos, o pedágio, a pergunta à cliente e a chegada).
// Quanto o mapa espera depende do modo de pausas:
//   contínuo   o balão fica o tempo de ser lido (e falado, com a voz ligada) e a viagem segue;
//   input      igual, mas para no pedágio até o apresentador mandar seguir;
//   passo      para em cada anúncio até o apresentador mandar seguir.
// Em todos, a pergunta à cliente fica na tela até a resposta chegar. O agente não espera o mapa:
// ele continua trabalhando, e o mapa só mostra o próximo evento real quando chega a vez dele.

import { useCallback, useEffect, useReducer, useRef, useState } from 'react';

import type { EventoDaExecucao } from '../tipos';
import { type Balao, balaoDoEvento, EVENTOS_COM_BALAO, type RotaAtual, rotaDoEvento } from './baloes';
import { type EstadoDaViagem, noDaTool, reduzir, VIAGEM_VAZIA } from './viagem';
import { calar } from './voz';

const PAUSA_NA_PARADA_MS = 600;
const PULSO_MS = 350;
// Sem pausa, o balão fica o tempo de leitura do anúncio: um mínimo, mais um tanto por caractere.
const BALAO_MS = 1100;
const LEITURA_BASE_MS = 900;
const LEITURA_POR_CARACTERE_MS = 45;
const LEITURA_MAXIMA_MS = 7000;

export type Pausas = 'continuo' | 'input' | 'passo';
export const PAUSAS: Pausas[] = ['continuo', 'input', 'passo'];

// Em que balões o mapa espera o apresentador mandar seguir. A pergunta à cliente nunca espera o
// apresentador: ela espera a resposta (que é a ação de quem está no palco).
export function paraNoBalao(balao: Balao, pausas: Pausas): boolean {
  if (balao.tipo === 'pergunta') return false;
  return pausas === 'passo' || (pausas === 'input' && balao.tipo === 'pedagio');
}

export function tempoDeLeitura(balao: Balao): number {
  const caracteres = balao.texto.length + (balao.subtexto?.length ?? 0);
  return Math.min(Math.max(BALAO_MS, LEITURA_BASE_MS + caracteres * LEITURA_POR_CARACTERE_MS), LEITURA_MAXIMA_MS);
}

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
  // A conversa também espera: a plateia lê a pergunta e a resposta do agente antes do próximo passo.
  'client.asked': 800,
  'agent.message': 800,
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
  balao: Balao | null; // o balão de fala aberto agora
  aguardando: boolean; // o mapa está parado, esperando o apresentador mandar seguir
  aguardandoResposta: boolean; // o mapa mostra a pergunta à cliente e espera a resposta chegar
  seguir: () => void;
  pularParaOFim: () => void;
}

// O lugar aonde um evento leva o robô (ou null, se ele não sai do lugar).
function destino(evento: EventoDaExecucao): string | null {
  if (evento.tipo === 'step.started') return evento.dados.id ?? null;
  if (evento.tipo === 'tool.called') return noDaTool(evento.dados.tool, evento.dados.argumentos, evento.dados.resultado);
  return null;
}

export function useDiretor(
  real: EstadoDaViagem,
  tempoDoTrecho: (de: string, para: string) => number | null, // ms, ou null se não há caminho
  pausas: Pausas,
  nomeDoLugar: (id: string) => string | null,
  nomeDaRota: (id: string) => string,
  anunciar?: (balao: Balao) => Promise<void>, // a voz do GPS; resolve quando terminar de falar
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
  const nome = useRef(nomeDoLugar);
  nome.current = nomeDoLugar;
  const rotaNome = useRef(nomeDaRota);
  rotaNome.current = nomeDaRota;
  const pausa = useRef(pausas);
  pausa.current = pausas;
  const voz = useRef(anunciar);
  voz.current = anunciar;
  const timerDoBalao = useRef<number | undefined>(undefined);
  const rotaAtual = useRef<RotaAtual | null>(null);
  // Cada balão tem a sua vez: esperas de um balão antigo (leitura, voz) não avançam o mapa.
  const vez = useRef(0);
  const [balao, setBalao] = useState<Balao | null>(null);
  const [aguardando, setAguardando] = useState(false);
  const [aguardandoResposta, setAguardandoResposta] = useState(false);

  const avancar = useCallback(() => {
    vez.current += 1;
    window.clearTimeout(timerDoBalao.current);
    setBalao(null);
    setAguardando(false);
    setAguardandoResposta(false);
    setCursor((c) => c + 1);
  }, []);

  // Nova execução: o diretor recomeça do zero.
  useEffect(() => {
    window.clearTimeout(timer.current);
    window.clearTimeout(timerDoBalao.current);
    vez.current += 1;
    calar();
    setBalao(null);
    setAguardando(false);
    setAguardandoResposta(false);
    aplicado.current = -1;
    lugarAtual.current = null;
    rotaAtual.current = null;
    despachar({ tipo: 'reiniciar', id: real.id });
    setCursor(0);
    setPartida(null);
    setTrechos([]);
    setPular(false);
  }, [real.id]);

  const eventos: EventoDaExecucao[] = real.eventos;
  const totalDeEventos = useRef(0);
  totalDeEventos.current = eventos.length;
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
    const retencao = RETENCAO_MS[evento.tipo] ?? 0;
    // O anúncio usa a rota de antes do evento (o recálculo compara a estimativa nova com a anterior).
    const lugar = para ?? lugarAtual.current;
    const anuncio = EVENTOS_COM_BALAO.has(evento.tipo)
      ? balaoDoEvento(evento, {
          nomeDoLugar: lugar ? nome.current(lugar) : null,
          nomeDaRota: rotaNome.current,
          rota: rotaAtual.current,
        })
      : null;
    rotaAtual.current = rotaDoEvento(evento, rotaNome.current) ?? rotaAtual.current;
    if (pular || !anuncio) {
      timer.current = window.setTimeout(avancar, pular ? 0 : andar + retencao);
      return;
    }
    // O balão abre quando o robô chega.
    const fala: Balao = { ...anuncio, indice: cursor };
    const minhaVez = vez.current;
    timerDoBalao.current = window.setTimeout(() => {
      if (vez.current !== minhaVez) return;
      setBalao(fala);
      const falado = voz.current?.(fala) ?? Promise.resolve();
      if (paraNoBalao(fala, pausa.current)) {
        setAguardando(true);
        return;
      }
      const lido = new Promise<void>((resolver) => {
        timer.current = window.setTimeout(resolver, Math.max(retencao, tempoDeLeitura(fala)));
      });
      void Promise.all([lido, falado]).then(() => {
        if (vez.current !== minhaVez) return;
        // A pergunta fica até a resposta chegar; o resto segue.
        if (fala.tipo === 'pergunta') setAguardandoResposta(true);
        else avancar();
      });
    }, andar);
  }, [cursor, eventos, pular, avancar]);

  // A pergunta já foi lida: quando o próximo evento real chegar (a resposta), a viagem segue.
  useEffect(() => {
    if (aguardandoResposta && eventos.length > cursor + 1) avancar();
  }, [aguardandoResposta, eventos.length, cursor, avancar]);

  // Trocar de modo com o balão esperando: se o novo modo não para aqui, a viagem segue.
  useEffect(() => {
    if (aguardando && balao && !paraNoBalao(balao, pausas)) avancar();
  }, [pausas, aguardando, balao, avancar]);

  useEffect(
    () => () => {
      window.clearTimeout(timer.current);
      window.clearTimeout(timerDoBalao.current);
    },
    [],
  );

  const seguir = useCallback(() => {
    if (aguardando) avancar();
  }, [aguardando, avancar]);
  const pularParaOFim = useCallback(() => {
    window.clearTimeout(timer.current);
    window.clearTimeout(timerDoBalao.current);
    vez.current += 1;
    calar();
    setBalao(null);
    setAguardando(false);
    setAguardandoResposta(false);
    setPular(true);
    // O evento atual (talvez esperando o balão) termina já; os próximos passam sem tempo.
    setCursor((c) => (aplicado.current === c && c < totalDeEventos.current ? c + 1 : c));
  }, []);
  return {
    exibido,
    partida,
    trechos,
    fila: Math.max(eventos.length - cursor, 0),
    balao,
    aguardando,
    aguardandoResposta,
    seguir,
    pularParaOFim,
  };
}
