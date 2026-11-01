// Formato de /api/status (agent), que repassa o que o gateway sabe.

export type Estado = 'ok' | 'fora';

export interface Ferramenta {
  nome: string;
  qualificado: string | null;
  visivel: boolean;
  fora: boolean;
}

export interface Servico {
  nome: string;
  prefixo: string;
  status: Estado;
  latencia_ms: number;
  ferramentas: Ferramenta[];
}

export interface Status {
  gateway: Estado;
  barramento: Estado;
  llm: { provedor: string; configurado: boolean };
  servicos: Servico[];
  ferramentas: number;
  ferramentas_fora: number;
}
