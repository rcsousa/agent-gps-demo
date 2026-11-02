// Chamadas do web. Dados vêm do agent (/api); ações sobre o mundo vão ao simulador (/simulador).

import type {
  Catalogo,
  Chamada,
  Cidade,
  EstadoDoModelo,
  Fonte,
  Gravacao,
  IncidenteDoSimulador,
  Placar,
  RotaDaJornada,
  Status,
  TicketDeAprovacao,
} from './tipos';

async function obter<T>(caminho: string): Promise<T> {
  const resposta = await fetch(caminho);
  if (!resposta.ok) throw new Error(String(resposta.status));
  return resposta.json();
}

export const api = {
  status: () => obter<Status>('/api/status'),
  catalogo: () => obter<Catalogo>('/api/catalogo'),
  fonte: (uri: string) => obter<Fonte>(`/api/catalogo/fonte?uri=${encodeURIComponent(uri)}`),
  arquivoDeSkill: (uri: string) =>
    obter<{ uri: string; texto: string; digest: string; size: number; verificado: boolean }>(
      `/api/catalogo/skill?uri=${encodeURIComponent(uri)}`,
    ),
  previa: (nome: string) =>
    obter<{ texto: string; cliente_id: string }>(`/api/catalogo/prompt/${encodeURIComponent(nome)}/previa`),
  modelo: () => obter<EstadoDoModelo>('/api/llm/modelo'),
  placar: () => obter<Placar>('/api/placar'),
  gravacoes: () => obter<Gravacao[]>('/api/gravacoes'),
  cidade: () => obter<Cidade>('/api/mapa'),
  rotas: () => obter<{ rotas: RotaDaJornada[] }>('/api/mapa/rotas'),
  entidade: (id: string) => obter<Record<string, unknown>>(`/api/mapa/entidade/${encodeURIComponent(id)}`),
  chamadas: (filtro: { tool?: string; prompt?: string; skill?: string }) =>
    obter<Chamada[]>(`/api/catalogo/chamadas?${new URLSearchParams(filtro as Record<string, string>)}`),
};

// O modelo das próximas execuções: escolha do apresentador, guardada pelo agente.
export async function escolherModelo(modelo: string): Promise<EstadoDoModelo> {
  const resposta = await fetch('/api/llm/modelo', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ modelo }),
  });
  if (!resposta.ok) throw new Error(String(resposta.status));
  return resposta.json();
}

async function enviar<T>(caminho: string, corpo: unknown): Promise<T> {
  const resposta = await fetch(caminho, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(corpo),
  });
  if (!resposta.ok) throw new Error((await resposta.text()) || String(resposta.status));
  return resposta.json();
}

export interface PedidoDeViagem {
  modo: string;
  canal?: string;
  modelo?: string;
  provedor?: string;
  incidentes?: string[]; // ativos no mundo ao iniciar: o caso do placar
}

export const gravar = (pedido: { execucao: string; cena?: string | null; incidentes: string[] }) =>
  enviar<Gravacao>('/api/gravacoes', pedido);

// Uma viagem do agente e a resposta da Ana (o apresentador responde por ela).
export const viagem = {
  iniciar: (pedido: PedidoDeViagem) => enviar<{ id: string }>('/api/execucoes', pedido),
  responder: (id: string, texto: string) => enviar<{ ok: boolean }>(`/api/execucoes/${id}/resposta`, { texto }),
};

// Incidentes são ação do apresentador sobre o mundo: vão ao simulador, nunca ao agente.
export async function aplicarIncidente(id: string): Promise<void> {
  const resposta = await fetch(`/simulador/incidentes/${id}/aplicar`, { method: 'POST' });
  if (!resposta.ok) throw new Error(String(resposta.status));
}

// O painel do apresentador: o estado do mundo e as ações sobre ele, sempre pelo simulador.
export const simulador = {
  incidentes: () => obter<IncidenteDoSimulador[]>('/simulador/incidentes'),
  aprovacoes: () => obter<TicketDeAprovacao[]>('/simulador/aprovacoes'),
  toolsFora: () => obter<{ fora: string[] }>('/simulador/tools'),
  acao: async (caminho: string) => {
    const resposta = await fetch(`/simulador${caminho}`, { method: 'POST' });
    if (!resposta.ok) throw new Error((await resposta.text()) || String(resposta.status));
  },
};

export async function incidentesAtivos(): Promise<string[]> {
  try {
    return (await simulador.incidentes()).filter((i) => i.ativo).map((i) => i.id);
  } catch {
    return [];
  }
}

// Ligar e desligar é ação do apresentador sobre o mundo: vai ao simulador, nunca ao agente.
export async function mudarTool(caminho: string): Promise<void> {
  const resposta = await fetch(`/simulador/tools/${caminho}`, { method: 'POST' });
  if (!resposta.ok) throw new Error(String(resposta.status));
}

// URI de código-fonte servida pelo próprio servidor MCP (template fonte://).
export const uriDeFonte = (servidor: string, tipo: 'tool' | 'prompt', nome: string) =>
  `fonte://${servidor}/${tipo}/${nome}`;
