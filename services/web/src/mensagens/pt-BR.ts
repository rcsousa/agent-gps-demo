// Todos os textos visíveis da interface. Nada de texto solto nos componentes.

export const mensagens = {
  marca: {
    prefixo: 'Banco',
    nome: 'Bússola',
    assinatura: 'Seu próximo passo, com mais sentido.',
  },
  navegacao: {
    rotulo: 'Navegação principal',
    bastidores: 'Bastidores',
  },
  status: {
    titulo: 'Status dos serviços',
    descricao:
      'O agente consulta o gateway, que verifica cada servidor MCP. Nenhuma outra rota existe entre eles.',
    atualizar: 'Atualizar',
    carregando: 'Consultando o agente…',
    ultimaAtualizacao: 'Atualizado às',
    erroAgente: 'O agente não respondeu.',
    erroAgenteDetalhe: 'Verifique se o serviço agent está no ar (docker compose ps).',
    noAr: 'No ar',
    foraDoAr: 'Fora do ar',
    latencia: (ms: number) => `${ms} ms`,
    ferramentas: (n: number) => `${n} tools`,
    grupos: {
      plataforma: 'Plataforma',
      servidores: 'Servidores MCP atrás do gateway',
    },
    llm: {
      titulo: 'Provedor de LLM',
      configurado: 'Chave configurada',
      ausente: 'Chave ausente',
      provedores: {
        anthropic: 'Anthropic',
        azure_openai: 'Azure OpenAI',
      } as Record<string, string>,
    },
  },
  servicos: {
    gateway: 'MCP gateway',
    barramento: 'Barramento de eventos',
    'skills-mcp': 'Skills',
    'contexto-mcp': 'Camada de contexto',
    'cliente-mcp': 'Cliente',
    'consentimento-mcp': 'Consentimento',
    'risco-mcp': 'Risco',
    'seguradoras-mcp': 'Seguradoras',
    'pagamentos-mcp': 'Pagamentos',
    'atendimento-mcp': 'Atendimento',
  } as Record<string, string>,
};
