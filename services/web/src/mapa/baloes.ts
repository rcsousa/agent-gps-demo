// O balão de fala do robô: o que o agente está fazendo, a partir de um evento real do barramento.
// O texto vem da tool, dos argumentos e do status do evento (nunca de um roteiro).

import { mensagens } from '../mensagens/pt-BR';
import type { EventoDaExecucao } from '../tipos';

const t = mensagens.mapa.baloes;

export type TipoDeBalao = 'tool' | 'incidente' | 'recalculo' | 'pedagio';

export interface Balao {
  tipo: TipoDeBalao;
  texto: string;
  detalhe: string | null; // a tool e a duração, em mono: a honestidade técnica
  ok: boolean; // false: falha ou incidente (vermelho, sempre com ícone)
  indice?: number; // a posição do evento na execução: cada balão tem o seu
}

// Os eventos que abrem balão (e, no passo a passo, esperam o apresentador).
export const EVENTOS_COM_BALAO = new Set(['tool.called', 'incident.detected', 'route.recalculated', 'human.required']);

function fraseDaTool(tool: string, argumentos: Record<string, unknown>): string {
  if (tool === 'seguradoras.cotar_seguro') {
    const id = typeof argumentos.seguradora === 'string' ? argumentos.seguradora : null;
    return t.cotar(id ? (t.seguradoras[id] ?? id) : null);
  }
  return t.tools[tool] ?? t.desconhecida(tool);
}

// nomeDoLugar: o nome do prédio aonde a tool leva o robô (para a frase de falha).
export function balaoDoEvento(evento: EventoDaExecucao, nomeDoLugar: string | null): Balao | null {
  const d = evento.dados;
  switch (evento.tipo) {
    case 'tool.called': {
      const detalhe = [d.tool, d.duracao_ms != null ? `${d.duracao_ms} ms` : null].filter(Boolean).join(' · ');
      if (d.status === 'ok') return { tipo: 'tool', texto: fraseDaTool(d.tool, d.argumentos ?? {}), detalhe, ok: true };
      // O gateway barrou (fora da skill ou fora de ordem): o evento traz o motivo.
      if (d.motivo) return { tipo: 'tool', texto: t.barrada, detalhe, ok: false };
      const erro = String(d.erro ?? '').replace(/^Error executing tool [\w.]+: /, '');
      if (/não respondeu/.test(erro)) return { tipo: 'tool', texto: t.falhou(nomeDoLugar), detalhe, ok: false };
      return { tipo: 'tool', texto: t.erro(nomeDoLugar, erro.slice(0, 140)), detalhe, ok: false };
    }
    case 'incident.detected':
      return { tipo: 'incidente', texto: `${d.metafora}: ${d.descricao}`, detalhe: d.tool ?? null, ok: false };
    case 'route.recalculated':
      return { tipo: 'recalculo', texto: t.recalculo(d.motivo), detalhe: d.regra ?? null, ok: true };
    case 'human.required':
      return { tipo: 'pedagio', texto: t.pedagio(d.motivo), detalhe: d.ticket_id ?? null, ok: true };
    default:
      return null;
  }
}
