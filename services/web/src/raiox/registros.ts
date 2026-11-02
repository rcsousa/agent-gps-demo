// O log do Raio-X: cada linha é um evento real do barramento, na ordem em que o mapa o mostrou.
// Nada aqui é montado à parte: é a mesma lista de eventos que o diretor de animações exibe.

import { mensagens } from '../mensagens/pt-BR';
import type { EventoDaExecucao } from '../tipos';

const t = mensagens.raioX.log;

export type TipoDeRegistro = 'protocolo' | 'tool' | 'modelo' | 'navegacao' | 'conversa' | 'incidente' | 'fim';

export interface Registro {
  indice: number;
  tipo: TipoDeRegistro;
  titulo: string; // como aparece no log, em Plex Mono
  detalhe: string;
  status: 'ok' | 'erro' | 'bloqueio' | null;
  duracaoMs: number | null;
  evento: EventoDaExecucao;
}

const BLOQUEIOS = new Set(['fora_da_skill', 'fora_de_ordem', 'skill_desconhecida', 'execucao_nao_identificada']);

const nomeDaSkill = (uri: string | null | undefined) => (uri ? uri.replace('skill://', '').split('/')[0] : '');

function argumentosCurtos(argumentos: Record<string, unknown> | undefined): string {
  const partes = Object.entries(argumentos ?? {}).map(([k, v]) => `${k}=${typeof v === 'object' ? '…' : String(v)}`);
  const texto = partes.join(', ');
  return texto.length > 60 ? `${texto.slice(0, 57)}…` : texto;
}

export function registro(evento: EventoDaExecucao, indice: number): Registro | null {
  const d = evento.dados;
  const base = { indice, evento, duracaoMs: (d.duracao_ms as number | undefined) ?? null };
  switch (evento.tipo) {
    case 'tools.listed':
      return { ...base, tipo: 'protocolo', titulo: 'tools/list', detalhe: t.tools(d.quantidade), status: 'ok' };
    case 'skills.listed':
      return {
        ...base,
        tipo: 'protocolo',
        titulo: 'skills/list',
        detalhe: (d.skills as string[]).map(nomeDaSkill).join(', '),
        status: 'ok',
      };
    case 'skill.read':
      return { ...base, tipo: 'protocolo', titulo: `skills/get (${nomeDaSkill(d.uri)})`, detalhe: d.uri, status: 'ok' };
    case 'resource.read':
      return {
        ...base,
        tipo: 'protocolo',
        titulo: `resources/read (${String(d.uri).replace('skill://', '')})`,
        detalhe: t.arquivo(d.tamanho, d.servidor),
        status: 'ok',
      };
    case 'prompt.read':
      return {
        ...base,
        tipo: 'protocolo',
        titulo: `prompts/get (${d.prompt})`,
        detalhe: d.servidor,
        status: d.status === 'erro' ? 'erro' : 'ok',
      };
    case 'tool.called': {
      const bloqueio = d.motivo && BLOQUEIOS.has(d.motivo);
      return {
        ...base,
        tipo: 'tool',
        titulo: `tool: ${d.tool}(${argumentosCurtos(d.argumentos)})`,
        detalhe: bloqueio ? t.bloqueada(d.motivo) : t.servidorESkill(d.servidor, nomeDaSkill(d.skill)),
        status: bloqueio ? 'bloqueio' : d.status === 'ok' ? 'ok' : 'erro',
      };
    }
    case 'model.step': {
      const tk = d.tokens ?? {};
      const entrada = (tk.entrada ?? 0) + (tk.cache_leitura ?? 0) + (tk.cache_escrita ?? 0);
      const pedidas = (d.tools_pedidas as string[]) ?? [];
      return {
        ...base,
        tipo: 'modelo',
        titulo: t.passo(d.passo),
        detalhe: t.tokens(entrada, tk.cache_leitura ?? 0, tk.saida ?? 0, pedidas.length),
        status: 'ok',
      };
    }
    case 'skill.loaded':
      return { ...base, tipo: 'navegacao', titulo: t.skill(d.nome), detalhe: t.permitidas((d.tools_permitidas ?? []).length), status: 'ok' };
    case 'route.planned':
      return { ...base, tipo: 'navegacao', titulo: t.rota(d.rota), detalhe: d.motivo, status: 'ok' };
    case 'route.recalculated':
      return { ...base, tipo: 'navegacao', titulo: t.recalculo(d.de, d.para), detalhe: t.motivoERegra(d.motivo, d.regra), status: 'ok' };
    case 'step.started':
      return { ...base, tipo: 'navegacao', titulo: t.parada(d.numero, d.nome ?? d.id), detalhe: d.bairro ?? '', status: 'ok' };
    case 'incident.detected':
      return { ...base, tipo: 'incidente', titulo: t.incidente(d.metafora), detalhe: d.descricao, status: 'erro' };
    case 'human.required':
      return { ...base, tipo: 'navegacao', titulo: t.pedagio, detalhe: d.motivo ?? '', status: 'ok' };
    case 'client.asked':
      return { ...base, tipo: 'conversa', titulo: t.pergunta, detalhe: d.pergunta, status: null };
    case 'client.answered':
      return { ...base, tipo: 'conversa', titulo: t.resposta, detalhe: d.texto, status: null };
    case 'run.finished':
      return {
        ...base,
        tipo: 'fim',
        titulo: t.fim(d.status, d.apolice),
        detalhe: d.metricas?.regras ? t.regras(d.metricas.regras.cumpridas, d.metricas.regras.total) : '',
        status: d.status === 'concluida' ? 'ok' : 'erro',
      };
    default:
      return null;
  }
}

export const registros = (eventos: EventoDaExecucao[]): Registro[] =>
  eventos.map(registro).filter((r): r is Registro => r !== null);

// --- Métricas, a partir dos mesmos eventos ---------------------------------------------------

export interface Metricas {
  passos: { passo: number; entrada: number; cache: number; saida: number; duracaoMs: number; tools: number }[];
  tools: { tool: string; chamadas: number; mediaMs: number; erros: number }[];
  totais: { entrada: number; cache: number; saida: number; modeloMs: number; toolsMs: number };
  custo: number | null;
  regras: { cumpridas: number; total: number; regras: Record<string, boolean> } | null;
  caso: string | null;
}

export function metricas(eventos: EventoDaExecucao[]): Metricas {
  const passos = eventos
    .filter((e) => e.tipo === 'model.step')
    .map(({ dados: d }) => ({
      passo: d.passo,
      entrada: d.tokens?.entrada ?? 0,
      cache: (d.tokens?.cache_leitura ?? 0) + (d.tokens?.cache_escrita ?? 0),
      saida: d.tokens?.saida ?? 0,
      duracaoMs: d.duracao_ms ?? 0,
      tools: (d.tools_pedidas ?? []).length,
    }));
  const porTool = new Map<string, { chamadas: number; soma: number; erros: number }>();
  for (const { dados: d } of eventos.filter((e) => e.tipo === 'tool.called')) {
    const t = porTool.get(d.tool) ?? { chamadas: 0, soma: 0, erros: 0 };
    t.chamadas += 1;
    t.soma += d.duracao_ms ?? 0;
    t.erros += d.status === 'ok' ? 0 : 1;
    porTool.set(d.tool, t);
  }
  const tools = [...porTool.entries()]
    .map(([tool, t]) => ({ tool, chamadas: t.chamadas, mediaMs: Math.round(t.soma / t.chamadas), erros: t.erros }))
    .sort((a, b) => b.chamadas - a.chamadas);
  const fim = eventos.find((e) => e.tipo === 'run.finished')?.dados;
  return {
    passos,
    tools,
    totais: {
      entrada: passos.reduce((s, p) => s + p.entrada, 0),
      cache: passos.reduce((s, p) => s + p.cache, 0),
      saida: passos.reduce((s, p) => s + p.saida, 0),
      modeloMs: passos.reduce((s, p) => s + p.duracaoMs, 0),
      toolsMs: [...porTool.values()].reduce((s, t) => s + t.soma, 0),
    },
    custo: fim?.metricas?.custo_usd?.total ?? null,
    regras: fim?.metricas?.regras ?? null,
    caso: fim?.metricas?.caso ?? null,
  };
}
