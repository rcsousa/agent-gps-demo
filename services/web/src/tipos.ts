// Formatos da API do agent (/api/status e /api/catalogo), que repassa o que o gateway sabe.

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
  // Prompts e skills que o servidor oferece, já com o nome do gateway.
  prompts: string[];
  skills: string[];
}

export interface Status {
  gateway: Estado;
  barramento: Estado;
  // modelos: o padrão primeiro, depois os outros que uma execução pode pedir.
  llm: { provedor: string; plataforma: string | null; modelo: string; configurado: boolean; modelos: string[] };
  servicos: Servico[];
  ferramentas: number;
  ferramentas_fora: number;
  skills: number;
  prompts: number;
}

export interface OpcaoDeModelo {
  id: string;
  // Preço por milhão de tokens, em US$ (null se o modelo não tem preço configurado).
  precos: { entrada: number; saida: number } | null;
}

export interface EstadoDoModelo {
  modelo: string;
  padrao: string;
  modelos: OpcaoDeModelo[];
}

export interface SkillDaTool {
  uri: string;
  nome: string;
  // Falso quando a skill só permite a tool por reutilizar outra skill (usa-skills).
  direta: boolean;
}

export interface EsquemaJson {
  type?: string;
  title?: string;
  description?: string;
  properties?: Record<string, EsquemaJson>;
  required?: string[];
  items?: EsquemaJson;
  anyOf?: EsquemaJson[];
  enum?: unknown[];
  default?: unknown;
  [chave: string]: unknown;
}

export interface ToolDoCatalogo {
  nome: string;
  servidor: string;
  nome_original: string;
  descricao: string;
  fora: boolean;
  esquema_entrada: EsquemaJson;
  esquema_saida: EsquemaJson | null;
  anotacoes: Record<string, unknown>;
  skills: SkillDaTool[];
}

export interface ArquivoDeSkill {
  uri: string;
  digest: string;
  size: number;
}

export interface SkillDoCatalogo {
  uri: string;
  nome: string;
  descricao: string;
  servidor: string;
  frontmatter: Record<string, unknown> & { metadata?: Record<string, unknown> };
  tools: string[];
  tools_com_reuso: string[];
  usa_skills: string[];
  arquivos: ArquivoDeSkill[];
  // Ordem garantida pelo gateway (workflow.yaml): o que cada tool exige antes.
  ordem: { tool: string; exige: string[]; impedida_por: string[] }[];
}

export interface PromptDoCatalogo {
  nome: string;
  titulo: string | null;
  descricao: string;
  servidor: string;
  canal: string | null;
  interlocutor: string | null;
  argumentos: { nome: string; descricao: string | null; obrigatorio: boolean }[];
}

export interface Catalogo {
  tools: ToolDoCatalogo[];
  skills: SkillDoCatalogo[];
  prompts: PromptDoCatalogo[];
}

export interface Fonte {
  tipo: string;
  nome: string;
  arquivo: string;
  linha: number;
  linguagem: string;
  texto: string;
}

export interface Chamada {
  id: string;
  tipo: string;
  instante: string;
  tool: string | null;
  status: string;
  motivo: string | null;
  duracao_ms: number | null;
  skill: string | null;
  execucao_id: string | null;
  erro: string | null;
}
