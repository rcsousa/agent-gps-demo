// O balão de fala do robô: o anúncio do GPS, a partir de um evento real do barramento.
// A frase é fixa (arquivo de mensagens); os dados vêm do evento: a tool e o status, a rota e o
// motivo que o agente escreveu, a parada, a regra, a estimativa. Nada vem de um roteiro.

import { mensagens } from '../mensagens/pt-BR';
import type { EventoDaExecucao } from '../tipos';
import { produtoDaTool } from './viagem';

const t = mensagens.mapa.baloes;
const a = t.anuncios;

export type TipoDeBalao =
  | 'apresentacao'
  | 'roteiro'
  | 'rota'
  | 'parada'
  | 'tool'
  | 'incidente'
  | 'recalculo'
  | 'pedagio'
  | 'pergunta'
  | 'chegada';

export interface Balao {
  tipo: TipoDeBalao;
  texto: string; // o anúncio, numa frase
  subtexto?: string | null; // o porquê e o que vem depois (motivo, nova estimativa, próxima parada)
  detalhe: string | null; // em mono: a tool, a regra, o modelo (a honestidade técnica)
  ok: boolean; // false: falha ou incidente (vermelho, sempre com ícone)
  indice?: number; // a posição do evento na execução: cada balão tem o seu
}

// Os eventos que abrem balão.
export const EVENTOS_COM_BALAO = new Set([
  'run.started',
  'skill.loaded',
  'route.planned',
  'step.started',
  'tool.called',
  'incident.detected',
  'route.recalculated',
  'human.required',
  'client.asked',
  'run.finished',
]);

// A rota que o GPS está seguindo: vem do último route.planned ou route.recalculated.
export interface RotaAtual {
  id: string;
  nome: string;
  paradas: { numero: number | null; id: string; nome: string }[];
  tempo: string | null;
}

export interface ContextoDoAnuncio {
  nomeDoLugar: string | null; // o prédio aonde a tool leva o robô (para a frase de falha)
  nomeDaRota: (id: string) => string;
  rota: RotaAtual | null;
}

function fraseDaTool(tool: string, argumentos: Record<string, unknown>, produto: string | null): string {
  // No prédio do produto, a frase diz qual produto o agente está tratando.
  if (produto && t.toolsDoProduto[tool]) return t.toolsDoProduto[tool](produto);
  if (tool === 'seguradoras.cotar_seguro') {
    const id = typeof argumentos.seguradora === 'string' ? argumentos.seguradora : null;
    return t.cotar(id ? (t.seguradoras[id] ?? id) : null);
  }
  return t.tools[tool] ?? t.desconhecida(tool);
}

// A primeira frase de um texto longo (a pergunta do agente), para caber no balão.
export function primeiraFrase(texto: string, limite = 140): string {
  const linha = texto.split('\n').find((l) => l.trim()) ?? '';
  const fim = linha.search(/[.?!:](\s|$)/);
  const frase = (fim >= 0 ? linha.slice(0, fim + 1) : linha).trim();
  return frase.length > limite ? `${frase.slice(0, limite - 1).trimEnd()}…` : frase;
}

function juntar(...partes: (string | null | undefined)[]): string | null {
  const texto = partes.filter(Boolean).join(' ');
  return texto || null;
}

// A rota que um route.planned ou route.recalculated passa a seguir.
export function rotaDoEvento(evento: EventoDaExecucao, nomeDaRota: (id: string) => string): RotaAtual | null {
  if (evento.tipo !== 'route.planned' && evento.tipo !== 'route.recalculated') return null;
  const d = evento.dados;
  const id = evento.tipo === 'route.planned' ? d.rota : d.para;
  if (!id) return null;
  return {
    id,
    nome: d.nome ?? nomeDaRota(id),
    paradas: (d.paradas ?? []).map((p: { numero: number | null; id: string; nome: string }) => ({
      numero: p.numero ?? null,
      id: p.id,
      nome: p.nome,
    })),
    tempo: d.estimativa?.tempo_texto ?? null,
  };
}

function anuncioDaParada(d: Record<string, any>, rota: RotaAtual | null): Pick<Balao, 'texto' | 'subtexto'> {
  const nome = d.nome ?? d.id;
  const numeradas = (rota?.paradas ?? []).filter((p) => p.numero != null);
  const total = numeradas.length;
  const texto = d.numero != null && total ? a.parada(d.numero, total, nome) : a.paradaExtra(nome);
  const indice = numeradas.findIndex((p) => p.id === d.id);
  const proxima = indice >= 0 ? numeradas[indice + 1] : null;
  const depois = indice < 0 ? null : proxima ? a.aSeguir(proxima.nome) : a.ultima;
  return { texto, subtexto: juntar(a.nasParadas[d.id], depois) };
}

export function balaoDoEvento(evento: EventoDaExecucao, contexto: ContextoDoAnuncio): Balao | null {
  const d = evento.dados;
  switch (evento.tipo) {
    case 'run.started': {
      const texto = a.apresentacao[d.modo] ?? a.apresentacao.com_skill;
      const subtexto = juntar(a.canal[d.canal], d.pedido ? a.destino(d.pedido) : null);
      return { tipo: 'apresentacao', texto, subtexto, detalhe: d.modelo ?? null, ok: true };
    }
    case 'skill.loaded': {
      const skill = a.skills[d.nome] ?? d.nome;
      return {
        tipo: 'roteiro',
        texto: a.roteiro(skill, (d.tools_permitidas ?? []).length),
        detalhe: d.uri ?? d.nome ?? null,
        ok: true,
      };
    }
    case 'route.planned': {
      const rota = rotaDoEvento(evento, contexto.nomeDaRota);
      const est = d.estimativa ?? {};
      const texto = a.rota(
        rota?.nome ?? contexto.nomeDaRota(d.rota),
        (rota?.paradas ?? []).filter((p) => p.numero != null).length,
        est.tempo_texto ?? '',
        a.riscos[est.risco] ?? est.risco ?? '',
      );
      return { tipo: 'rota', texto, subtexto: d.motivo ?? null, detalhe: d.rota ?? null, ok: true };
    }
    case 'step.started':
      return { tipo: 'parada', ...anuncioDaParada(d, contexto.rota), detalhe: d.id ?? null, ok: true };
    case 'tool.called': {
      const detalhe = [d.tool, d.duracao_ms != null ? `${d.duracao_ms} ms` : null].filter(Boolean).join(' · ');
      const lugar = contexto.nomeDoLugar;
      if (d.status === 'ok') {
        const produto = produtoDaTool(d.tool, d.argumentos ?? {}, d.resultado) ? lugar : null;
        return { tipo: 'tool', texto: fraseDaTool(d.tool, d.argumentos ?? {}, produto), detalhe, ok: true };
      }
      // O gateway barrou (fora da skill ou fora de ordem): o evento traz o motivo.
      if (d.motivo) return { tipo: 'tool', texto: t.barrada, detalhe, ok: false };
      const erro = String(d.erro ?? '').replace(/^Error executing tool [\w.]+: /, '');
      if (/não respondeu/.test(erro)) return { tipo: 'tool', texto: t.falhou(lugar), detalhe, ok: false };
      return { tipo: 'tool', texto: t.erro(lugar, erro.slice(0, 140)), detalhe, ok: false };
    }
    case 'incident.detected':
      return {
        tipo: 'incidente',
        texto: a.incidente(d.metafora ?? ''),
        subtexto: d.descricao ?? null,
        detalhe: d.tool ?? null,
        ok: false,
      };
    case 'route.recalculated': {
      const de = contexto.rota?.nome ?? (d.de ? contexto.nomeDaRota(d.de) : null);
      const para = contexto.nomeDaRota(d.para);
      const texto = de && d.de !== d.para ? a.recalculoTroca(de, para) : a.recalculoMesma(para);
      const tempo = d.estimativa?.tempo_texto;
      const estimativa = tempo ? a.novaEstimativa(tempo, contexto.rota?.tempo ?? null) : null;
      return { tipo: 'recalculo', texto, subtexto: juntar(d.motivo, estimativa), detalhe: d.regra ?? null, ok: true };
    }
    case 'human.required':
      return { tipo: 'pedagio', texto: a.pedagio, subtexto: d.motivo ?? null, detalhe: d.ticket_id ?? null, ok: true };
    case 'client.asked':
      return {
        tipo: 'pergunta',
        texto: a.pergunta,
        subtexto: d.pergunta ? primeiraFrase(d.pergunta) : null,
        detalhe: null,
        ok: true,
      };
    case 'run.finished': {
      if (d.apolice) return { tipo: 'chegada', texto: a.chegada(d.apolice), detalhe: null, ok: true };
      if (d.erro) return { tipo: 'chegada', texto: a.fimComErro, subtexto: String(d.erro).slice(0, 140), detalhe: null, ok: false };
      return { tipo: 'chegada', texto: a.fimSemApolice, detalhe: d.status ?? null, ok: true };
    }
    default:
      return null;
  }
}

// O que a voz do GPS fala: o anúncio e o porquê (sem o detalhe técnico em mono).
export function falaDoBalao(balao: Balao): string {
  return [balao.texto, balao.subtexto].filter(Boolean).join(' ');
}
