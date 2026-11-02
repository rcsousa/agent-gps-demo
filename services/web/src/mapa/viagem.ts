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

export interface EstadoDaViagem {
  id: string | null;
  modo: string | null;
  canal: string | null;
  modelo: string | null;
  provedor: string | null;
  skill: { nome: string; tools: number } | null;
  rota: string | null;
  motivoDaRota: string | null;
  recalculos: { de: string; para: string; motivo: string; regra: string }[];
  parada: string | null;
  visitadas: string[];
  pulsos: Pulso[];
  incidentes: { metafora: string; descricao: string; entidade: string | null; tool: string }[];
  pedagio: boolean;
  pergunta: { texto: string; opcoes: string[] } | null;
  mensagens: Mensagem[];
  fim: { status: string; apolice: string | null; custo: number | null; duracao: number; erro: string | null } | null;
}

export const VIAGEM_VAZIA: EstadoDaViagem = {
  id: null,
  modo: null,
  canal: null,
  modelo: null,
  provedor: null,
  skill: null,
  rota: null,
  motivoDaRota: null,
  recalculos: [],
  parada: null,
  visitadas: [],
  pulsos: [],
  incidentes: [],
  pedagio: false,
  pergunta: null,
  mensagens: [],
  fim: null,
};

// Cada tool, no mapa, é uma rua até um sistema da cidade (os nós do grafo).
export function noDaTool(tool: string, argumentos: Record<string, unknown> = {}): string | null {
  const [dominio, nome] = tool.split('.');
  const seguradora = typeof argumentos.seguradora === 'string' ? argumentos.seguradora : null;
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

type Acao = { tipo: 'evento'; evento: EventoDaExecucao } | { tipo: 'reiniciar'; id: string | null };

function reduzir(estado: EstadoDaViagem, acao: Acao): EstadoDaViagem {
  if (acao.tipo === 'reiniciar') return { ...VIAGEM_VAZIA, id: acao.id };
  const { tipo, dados } = acao.evento;
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
        visitadas: estado.visitadas.includes(dados.id) ? estado.visitadas : [...estado.visitadas, dados.id],
      };
    case 'tool.called': {
      const no = noDaTool(dados.tool, dados.argumentos);
      if (!no) return estado;
      const pulso = { no, quando: performance.now(), ok: dados.status === 'ok' };
      return { ...estado, pulsos: [...estado.pulsos.slice(-20), pulso] };
    }
    case 'incident.detected':
      return {
        ...estado,
        incidentes: [
          ...estado.incidentes,
          { metafora: dados.metafora, descricao: dados.descricao, entidade: dados.entidade, tool: dados.tool },
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
];

// Acompanha uma execução: os eventos desde o início e, depois, ao vivo, até o run.finished.
export function useViagem(id: string | null): EstadoDaViagem {
  const [estado, despachar] = useReducer(reduzir, VIAGEM_VAZIA);

  useEffect(() => {
    despachar({ tipo: 'reiniciar', id });
    if (!id) return;
    const fonte = new EventSource(`/api/execucoes/${id}/eventos`);
    // Numa reconexão, o servidor reenvia desde o início: cada evento (id do stream) vale uma vez só.
    const vistos = new Set<string>();
    for (const tipo of TIPOS) {
      fonte.addEventListener(tipo, (mensagem) => {
        const { data, lastEventId } = mensagem as MessageEvent;
        if (lastEventId && vistos.has(lastEventId)) return;
        if (lastEventId) vistos.add(lastEventId);
        const evento = JSON.parse(data) as EventoDaExecucao;
        despachar({ tipo: 'evento', evento });
        // O servidor encerra o fluxo no fim; sem fechar, o navegador reconectaria e repetiria tudo.
        if (tipo === 'run.finished') fonte.close();
      });
    }
    return () => fonte.close();
  }, [id]);

  return estado;
}
