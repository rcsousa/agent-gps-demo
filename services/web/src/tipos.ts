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

// --- Modo Mapa: a cidade vem do grafo (contexto://mapa), as rotas de contexto.consultar_rota ---

export type Ponto = [number, number];

export interface Bairro {
  id: string;
  nome: string;
  cor: string;
  poligono: Ponto[];
}

export interface NoDoMapa {
  id: string;
  tipo: string;
  tipo_exibicao: string;
  nome: string;
  bairro: string;
  x: number;
  y: number;
  // Estado vivo (o trânsito): ok, degradado ou fora; null para o que não tem estado.
  status: 'ok' | 'degradado' | 'fora' | null;
  porta: Ponto | null; // onde o agente para, na rua, para "entrar" no lugar
  estilo: Estilo | null; // a construção; null para o que não é lugar (rotas, jornada)
}

// A grade da cidade: as linhas das ruas (xs, ys), as quadras e o tamanho dos lotes.
export interface Quadra {
  coluna: number;
  linha: number;
  bairro: string;
  agua: boolean;
  retangulo: [number, number, number, number];
}

export interface Grade {
  colunas: number;
  linhas: number;
  xs: number[];
  ys: number[];
  rua: number;
  avenida: number;
  avenidas_verticais: number[];
  avenidas_horizontais: number[];
  lote: [number, number];
  quadras: Quadra[];
}

export type Estilo = 'casa' | 'loja' | 'shopping' | 'fabrica' | 'publico' | 'torre' | 'tecnico' | 'escritorio' | 'placa';

export interface Cidade {
  mundo: { largura: number; altura: number };
  cidade: Grade;
  bairros: Bairro[];
  rio: Ponto[];
  nos: NoDoMapa[];
  arestas: { de: string; tipo: string; para: string }[];
}

export interface ParadaDaRota {
  ordem: number;
  numero: number | null;
  id: string;
  nome: string;
  bairro: string;
}

export interface RotaDaJornada {
  id: string;
  nome: string;
  descricao: string;
  paradas: ParadaDaRota[];
  estimativa: {
    tempo_texto: string;
    custo_operacional: number;
    risco: string;
    premio_anual_referencia: number | null;
    bloqueada: boolean;
  };
  alertas: { status?: string; mensagem: string; entidade?: { id: string } }[];
}

export interface EventoDaExecucao {
  tipo: string;
  origem: string;
  instante: string;
  dados: Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any
}

// --- Fase 7: placar e painel do apresentador ----------------------------------------------

export interface LinhaDoPlacar {
  modo: string;
  modelo: string;
  execucoes: number;
  cumpridas: number;
  total: number;
  perfeitas: number;
  segundos_medio: number;
  custo_medio_usd: number | null;
}

export interface ExecucaoNoPlacar {
  id: string;
  modo: string;
  modelo: string;
  provedor: string;
  caso: string;
  criada_em: string;
  status: string;
  apolice: string | null;
  cumpridas: number;
  total: number;
  regras: Record<string, boolean>;
  segundos: number;
  custo_usd: number | null;
  bloqueios: number;
  tools_irrelevantes: number;
}

export interface Placar {
  sessao: { execucoes: ExecucaoNoPlacar[]; agregado: LinhaDoPlacar[] };
  referencia: { fonte: string; data: string; descricao: string; linhas: LinhaDoPlacar[] };
}

export interface IncidenteDoSimulador {
  id: string;
  nome: string;
  metafora: string;
  reacao_esperada: string;
  ativo: boolean;
}

export interface TicketDeAprovacao {
  ticket_id: string;
  cliente_id: string;
  premio_anual: number;
  importancia_segurada: number;
  motivo: string;
  status: string;
  criado_em: string;
  decidido_por?: string;
}

export interface Gravacao {
  nome: string;
  execucao_id: string;
  cena: string | null;
  modo: string;
  canal: string;
  provedor: string;
  modelo: string;
  status: string;
  apolice: string | null;
  gravado_em: string;
  eventos: number;
  incidentes: string[];
}
