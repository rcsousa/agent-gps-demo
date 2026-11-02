// Chamadas do web. Dados vêm do agent (/api); ações sobre o mundo vão ao simulador (/simulador).

import type { Catalogo, Chamada, EstadoDoModelo, Fonte, Status } from './tipos';

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

// Ligar e desligar é ação do apresentador sobre o mundo: vai ao simulador, nunca ao agente.
export async function mudarTool(caminho: string): Promise<void> {
  const resposta = await fetch(`/simulador/tools/${caminho}`, { method: 'POST' });
  if (!resposta.ok) throw new Error(String(resposta.status));
}

// URI de código-fonte servida pelo próprio servidor MCP (template fonte://).
export const uriDeFonte = (servidor: string, tipo: 'tool' | 'prompt', nome: string) =>
  `fonte://${servidor}/${tipo}/${nome}`;
