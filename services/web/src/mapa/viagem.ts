// O estado da viagem, montado só a partir dos eventos reais da execução (SSE do agente).
// Regra da demo: toda animação no mapa corresponde a um evento do barramento.

import { useEffect, useReducer } from 'react';

import type { EventoDaExecucao } from '../tipos';

export interface Mensagem {
  tipo: 'agente' | 'pergunta' | 'resposta' | 'sistema';
  texto: string;
  opcoes?: string[];
}

export interface Pulso {
  no: string;
  quando: number;
  ok: boolean;
}

// Por onde os eventos chegam: o stream ao vivo (SSE) ou a consulta por lotes, a alternativa
// para redes que seguram o stream (proxies e antivírus com inspeção de HTTPS).
export type Transporte = 'sse' | 'consulta';

export interface EstadoDaViagem {
  id: string | null;
  transporte: Transporte | null;
  modo: string | null;
  canal: string | null;
  modelo: string | null;
  provedor: string | null;
  skill: { nome: string; tools: number } | null;
  rota: string | null;
  motivoDaRota: string | null;
  recalculos: { de: string; para: string; motivo: string; regra: string }[];
  parada: string | null;
  paradaInfo: { numero: number | null; nome: string; bairro: string } | null;
  visitadas: string[];
  ultimaTool: { tool: string; ok: boolean } | null;
  pulsos: Pulso[];
  incidentes: {
    metafora: string;
    descricao: string;
    entidade: string | null;
    tool: string;
    parada: string | null; // onde o robô estava quando o incidente apareceu
  }[];
  pedagio: boolean;
  pergunta: { texto: string; opcoes: string[] } | null;
  mensagens: Mensagem[];
  eventos: EventoDaExecucao[]; // todos, na ordem: a fila do diretor de animações
  fim: { status: string; apolice: string | null; custo: number | null; duracao: number; erro: string | null } | null;
}

export const VIAGEM_VAZIA: EstadoDaViagem = {
  id: null,
  transporte: null,
  modo: null,
  canal: null,
  modelo: null,
  provedor: null,
  skill: null,
  rota: null,
  motivoDaRota: null,
  recalculos: [],
  parada: null,
  paradaInfo: null,
  visitadas: [],
  ultimaTool: null,
  pulsos: [],
  incidentes: [],
  pedagio: false,
  pergunta: null,
  mensagens: [],
  eventos: [],
  fim: null,
};

// Cada tool, no mapa, é uma rua até um sistema da cidade (os nós do grafo).
// O produto residencial que uma chamada trata, quando ela é sobre a oferta: a adequação traz o
// produto_id nos argumentos; a proposta e o aceite trazem a seguradora no resultado real.
// Só os produtos residenciais têm prédio no bairro de produtos; fora disso, null.
export function produtoDaTool(tool: string, argumentos: Record<string, unknown> = {}, resultado?: unknown): string | null {
  if (tool === 'risco.avaliar_adequacao') {
    const id = argumentos.produto_id;
    return typeof id === 'string' && PRODUTO_RESIDENCIAL.test(id) ? id : null;
  }
  if (tool === 'seguradoras.gerar_proposta' || tool === 'seguradoras.registrar_aceite') {
    const seguradora = typeof resultado === 'string' ? /"seguradora"\s*:\s*"seguradora-([a-z]+)"/.exec(resultado)?.[1] : null;
    return seguradora ? `produto-residencial-${seguradora}` : null;
  }
  return null;
}

const PRODUTO_RESIDENCIAL = /^produto-residencial-[a-z]+$/;

export function noDaTool(tool: string, argumentos: Record<string, unknown> = {}, resultado?: unknown): string | null {
  const [dominio, nome] = tool.split('.');
  const seguradora = typeof argumentos.seguradora === 'string' ? argumentos.seguradora : null;
  // Adequação, proposta e aceite são sobre o produto: o robô vai ao prédio dele, no bairro de produtos.
  const produto = produtoDaTool(tool, argumentos, resultado);
  if (produto) return produto;
  if (dominio === 'cliente') return 'sistema-crm';
  if (dominio === 'consentimento') return 'sistema-cofre-consentimentos';
  if (dominio === 'risco') return nome === 'agendar_vistoria' ? 'sistema-vistoria' : 'sistema-motor-risco';
  if (dominio === 'pagamentos') return 'sistema-gateway-pagamentos';
  if (dominio === 'atendimento') return 'fila-aprovacao-alcada';
  if (dominio === 'seguradoras') {
    if (nome.startsWith('cotar') && seguradora) return `api-cotacao-${seguradora}`;
    if (nome === 'emitir_apolice') return 'sistema-registro-operacoes';
    return 'sistema-registro-operacoes';
  }
  return null;
}

export type Acao =
  | { tipo: 'evento'; evento: EventoDaExecucao }
  | { tipo: 'reiniciar'; id: string | null }
  | { tipo: 'transporte'; transporte: Transporte };

export function reduzir(anterior: EstadoDaViagem, acao: Acao): EstadoDaViagem {
  if (acao.tipo === 'reiniciar') return { ...VIAGEM_VAZIA, id: acao.id };
  if (acao.tipo === 'transporte') return { ...anterior, transporte: acao.transporte };
  const { tipo, dados } = acao.evento;
  const estado = { ...anterior, eventos: [...anterior.eventos, acao.evento] };
  switch (tipo) {
    case 'run.started':
      return { ...estado, modo: dados.modo, canal: dados.canal, modelo: dados.modelo, provedor: dados.provedor };
    case 'skill.loaded':
      return { ...estado, skill: { nome: dados.nome, tools: (dados.tools_permitidas ?? []).length } };
    case 'route.planned':
      return { ...estado, rota: dados.rota, motivoDaRota: dados.motivo };
    case 'route.recalculated':
      return {
        ...estado,
        rota: dados.para,
        recalculos: [
          ...estado.recalculos,
          { de: dados.de, para: dados.para, motivo: dados.motivo, regra: dados.regra },
        ],
      };
    case 'step.started':
      return {
        ...estado,
        parada: dados.id,
        paradaInfo: { numero: dados.numero ?? null, nome: dados.nome, bairro: dados.bairro },
        visitadas: estado.visitadas.includes(dados.id) ? estado.visitadas : [...estado.visitadas, dados.id],
      };
    case 'tool.called': {
      const ultimaTool = { tool: dados.tool, ok: dados.status === 'ok' };
      const no = noDaTool(dados.tool, dados.argumentos, dados.resultado);
      if (!no) return { ...estado, ultimaTool };
      const pulso = { no, quando: performance.now(), ok: dados.status === 'ok' };
      return { ...estado, ultimaTool, pulsos: [...estado.pulsos.slice(-20), pulso] };
    }
    case 'incident.detected':
      return {
        ...estado,
        incidentes: [
          ...estado.incidentes,
          {
            metafora: dados.metafora,
            descricao: dados.descricao,
            entidade: dados.entidade,
            tool: dados.tool,
            parada: estado.parada,
          },
        ],
      };
    case 'human.required':
      return { ...estado, pedagio: true };
    case 'client.asked':
      return {
        ...estado,
        pergunta: { texto: dados.pergunta, opcoes: dados.opcoes ?? [] },
        mensagens: [...estado.mensagens, { tipo: 'pergunta', texto: dados.pergunta, opcoes: dados.opcoes ?? [] }],
      };
    case 'client.answered':
      return { ...estado, pergunta: null, mensagens: [...estado.mensagens, { tipo: 'resposta', texto: dados.texto }] };
    case 'agent.message':
      return { ...estado, mensagens: [...estado.mensagens, { tipo: 'agente', texto: dados.texto }] };
    case 'run.finished':
      return {
        ...estado,
        pergunta: null,
        fim: {
          status: dados.status,
          apolice: dados.apolice,
          erro: dados.erro,
          duracao: dados.metricas?.duracao_s ?? 0,
          custo: dados.metricas?.custo_usd?.total ?? null,
        },
      };
    default:
      return estado;
  }
}

const TIPOS = [
  'run.started',
  'skill.loaded',
  'route.planned',
  'route.recalculated',
  'step.started',
  'tool.called',
  'incident.detected',
  'human.required',
  'client.asked',
  'client.answered',
  'agent.message',
  'run.finished',
  // Para o Raio-X: o que trafegou entre o agente, o gateway e o modelo.
  'prompt.loaded',
  'prompt.read',
  'tools.listed',
  'skills.listed',
  'skill.read',
  'resource.read',
  'model.step',
];

// Prefixo do id de uma viagem tocada de uma gravação (replay offline).
export const PREFIXO_GRAVACAO = 'gravacao:';
export const ehReplay = (id: string | null) => Boolean(id?.startsWith(PREFIXO_GRAVACAO));

// Quanto esperar pelo primeiro evento do SSE antes de concluir que o stream está preso no caminho.
// O servidor começa do início da execução, então numa rede normal o primeiro evento chega na hora.
export const ESPERA_DO_SSE_MS = 4000;
// Pausa entre tentativas da consulta quando ela falha (cresce até o teto).
const PAUSA_APOS_FALHA_MS = 1000;
const PAUSA_MAXIMA_MS = 5000;

// `?eventos=consulta` na URL pula o SSE: útil quando já se sabe que a rede segura streams
// (e `?eventos=sse` volta ao normal). A escolha fica na sessão da aba, porque o mapa reescreve
// a URL ao iniciar uma viagem.
const CHAVE_CONSULTA = 'bussola:eventos';

export function lembrarEscolhaDeEventos(): void {
  const escolha = new URLSearchParams(window.location.search).get('eventos');
  if (escolha !== 'consulta' && escolha !== 'sse') return;
  try {
    window.sessionStorage.setItem(CHAVE_CONSULTA, escolha);
  } catch {
    // Sem armazenamento (aba privada, bloqueio): vale só enquanto o parâmetro estiver na URL.
  }
}

function consultaForcada(): boolean {
  lembrarEscolhaDeEventos();
  if (new URLSearchParams(window.location.search).get('eventos') === 'consulta') return true;
  try {
    return window.sessionStorage.getItem(CHAVE_CONSULTA) === 'consulta';
  } catch {
    return false;
  }
}

// Logo que o módulo carrega, antes de qualquer reescrita da URL.
lembrarEscolhaDeEventos();

interface LoteDeEventos {
  eventos: { id: string; espera?: number; evento: EventoDaExecucao }[];
  cursor?: string;
  fim: boolean;
}

// Acompanha uma execução: os eventos desde o início e, depois, ao vivo, até o run.finished.
// Com o id "gravacao:<nome>", toca a gravação no mesmo formato (replay offline).
//
// O caminho principal é o SSE. Proxies e antivírus corporativos com inspeção de HTTPS costumam
// segurar a resposta inteira antes de entregá-la, e um stream que só termina no fim da viagem
// nunca chega. Se nenhum evento chegar em ESPERA_DO_SSE_MS, ou se o navegador desistir do SSE,
// o hook passa para a consulta por lotes (long-polling), que termina a cada resposta e passa por
// qualquer proxy. Os ids são os mesmos nos dois caminhos: nada se perde nem se repete na troca.
export function useViagem(id: string | null): EstadoDaViagem {
  const [estado, despachar] = useReducer(reduzir, VIAGEM_VAZIA);

  useEffect(() => {
    despachar({ tipo: 'reiniciar', id });
    if (!id) return;
    const replay = ehReplay(id);
    const base = replay
      ? `/api/gravacoes/${encodeURIComponent(id.slice(PREFIXO_GRAVACAO.length))}/eventos`
      : `/api/execucoes/${id}/eventos`;

    let encerrado = false; // o efeito foi desmontado (outra viagem, outra tela)
    let terminou = false; // chegou o run.finished
    let recebeuPeloSse = false;
    let ultimoId: string | null = null;
    let fonte: EventSource | null = null;
    const timers = new Set<number>();
    const cancelar = new AbortController();
    // Numa reconexão ou na troca de caminho, o servidor reenvia desde o início:
    // cada evento (id do stream) vale uma vez só.
    const vistos = new Set<string>();

    const esperar = (ms: number) =>
      new Promise<void>((resolver) => {
        const timer = window.setTimeout(() => {
          timers.delete(timer);
          resolver();
        }, ms);
        timers.add(timer);
      });

    const receber = (evento: EventoDaExecucao, idDoEvento: string) => {
      if (encerrado || terminou) return;
      if (idDoEvento) {
        if (vistos.has(idDoEvento)) return;
        vistos.add(idDoEvento);
        ultimoId = idDoEvento;
      }
      despachar({ tipo: 'evento', evento });
      if (evento.tipo === 'run.finished') {
        terminou = true;
        // O servidor encerra o fluxo no fim; sem fechar, o navegador reconectaria e repetiria tudo.
        fonte?.close();
      }
    };

    const buscarLote = async (url: string): Promise<LoteDeEventos> => {
      const resposta = await fetch(url, { cache: 'no-store', signal: cancelar.signal });
      if (!resposta.ok) throw new Error(`HTTP ${resposta.status}`);
      return (await resposta.json()) as LoteDeEventos;
    };

    // Ao vivo: um lote por consulta, a partir do último id visto (o servidor espera um pouco
    // por eventos novos antes de responder vazio).
    const consultarAoVivo = async () => {
      let cursor = ultimoId;
      let falhas = 0;
      while (!encerrado && !terminou) {
        try {
          const lote = await buscarLote(cursor ? `${base}/lote?apos=${encodeURIComponent(cursor)}` : `${base}/lote`);
          for (const { id: idDoEvento, evento } of lote.eventos) receber(evento, idDoEvento);
          cursor = lote.cursor ?? cursor;
          falhas = 0;
          if (lote.fim) return;
        } catch {
          if (encerrado) return;
          falhas += 1;
          await esperar(Math.min(PAUSA_APOS_FALHA_MS * falhas, PAUSA_MAXIMA_MS));
        }
      }
    };

    // Replay: a gravação inteira de uma vez, tocada aqui no ritmo original.
    const tocarAGravacao = async () => {
      let falhas = 0;
      while (!encerrado) {
        try {
          const lote = await buscarLote(`${base}/lote`);
          for (const { id: idDoEvento, espera, evento } of lote.eventos) {
            if (vistos.has(idDoEvento)) continue;
            if (espera) await esperar(espera * 1000);
            receber(evento, idDoEvento);
          }
          return;
        } catch {
          if (encerrado) return;
          falhas += 1;
          await esperar(Math.min(PAUSA_APOS_FALHA_MS * falhas, PAUSA_MAXIMA_MS));
        }
      }
    };

    const passarParaConsulta = () => {
      if (encerrado || terminou) return;
      fonte?.close();
      fonte = null;
      despachar({ tipo: 'transporte', transporte: 'consulta' });
      void (replay ? tocarAGravacao() : consultarAoVivo());
    };

    if (consultaForcada()) {
      passarParaConsulta();
    } else {
      const sse = new EventSource(base);
      fonte = sse;
      despachar({ tipo: 'transporte', transporte: 'sse' });
      for (const tipo of TIPOS) {
        sse.addEventListener(tipo, (mensagem) => {
          if (fonte !== sse) return;
          recebeuPeloSse = true;
          const { data, lastEventId } = mensagem as MessageEvent;
          receber(JSON.parse(data) as EventoDaExecucao, lastEventId);
        });
      }
      // Erros de rede passageiros o EventSource resolve sozinho, reconectando. Se ele desiste
      // (a resposta nem é um stream: o proxy devolveu um erro ou uma página), segue pela consulta.
      sse.onerror = () => {
        if (fonte === sse && sse.readyState === EventSource.CLOSED) passarParaConsulta();
      };
      // Nenhum evento no prazo: o stream está preso no caminho.
      const timer = window.setTimeout(() => {
        timers.delete(timer);
        if (!recebeuPeloSse) passarParaConsulta();
      }, ESPERA_DO_SSE_MS);
      timers.add(timer);
    }

    return () => {
      encerrado = true;
      fonte?.close();
      cancelar.abort();
      for (const timer of timers) window.clearTimeout(timer);
    };
  }, [id]);

  return estado;
}
