# Demo GPS de Contexto — Banco Bússola

Demo que mostra por que agentes de IA precisam de uma **camada de contexto** (o mapa) e de **skills** (o GPS) para navegar com segurança numa jornada bancária de contratação de seguro residencial.

A especificação completa está em `docs/spec.md`. Ela é a fonte da verdade: leia a seção relevante antes de implementar qualquer coisa. Se algo aqui conflitar com a spec, siga a spec e me avise.

## Regras permanentes (não negociáveis)

- **Tudo roda em Docker.** O projeto sobe com um único `docker compose up`. Nada é instalado ou executado fora dos containers. Comandos de teste, lint e scripts também rodam via `docker compose run`/`exec`.
- **Modelos:** Anthropic ou Azure OpenAI, escolhidos por `LLM_PROVIDER=anthropic|azure_openai`. Uma interface única no `agent`; trocar de provedor não muda nenhum fluxo.
- **Backend 100% Python** (FastAPI e SDK oficial do MCP). Front em React + TypeScript.
- **UI em IBM Carbon** (`@carbon/react`), cores neutras e aparência profissional. Tipografia IBM Plex.
- **Mapas e grafos engajadores, bonitos e navegáveis** (MapLibre GL, deck.gl): pan, zoom, clique em nós, zoom semântico.
- **Idioma: somente português do Brasil** em tudo que o usuário vê (UI, skills, ontologia, narração, bastidores). Textos da UI centralizados num arquivo de mensagens. Identificadores de código podem ficar em inglês.
- **Segredos só em `.env`**, nunca no código. Manter `.env.example` atualizado.

## Arquitetura (resumo)

- O `agent` fala **somente** com o `mcp-gateway`, como falaria com qualquer servidor MCP. Nenhuma URL de outro serviço no agente.
- Todo serviço de negócio é um servidor MCP atrás do gateway e chega ao agente como tools: `contexto-mcp`, `cliente-mcp`, `consentimento-mcp`, `risco-mcp`, `seguradoras-mcp`, `pagamentos-mcp`, `atendimento-mcp`.
- **Skills são workflows** servidos pelo `skills-mcp` via extensão `io.modelcontextprotocol/skills` (SEP-2640: `skills/list`, `skills/get`, `resources/read`). A skill instrui quais tools consumir, em que ordem e o que fazer em caso de desvio.
- O gateway é o ponto de governança (tools permitidas por skill, políticas, proveniência) e de observação (eventos do Modo Raio-X).
- O `simulator` injeta incidentes e fica fora do alcance do agente.
- `graph` (Neo4j) só é acessado pelo `contexto-mcp`.
- Um barramento de eventos (`route.planned`, `step.started`, `tool.called`, `incident.detected`, `route.recalculated`, `human.required`) alimenta o Modo Mapa e o Modo Raio-X. **Toda animação na tela corresponde a um evento real.**

## Identidade visual

- Banco fictício: **Banco Bússola**. Assinatura: "Seu próximo passo, com mais sentido."
- Cor de destaque laranja (aprox. `#F26522`), azul-marinho de apoio, cinzas neutros do Carbon na moldura. Vermelho só para incidentes, sempre com ícone e rótulo.
- O agente é o **robô** do infográfico. No mapa, aparece como um robô dentro de um pino.
- Seguradoras fictícias: Âncora, Farol e Horizonte.
- Referência visual oficial: `docs/assets/mapa-da-demo.png` (infográfico). Ele é a tela de abertura do site (rota `/`), com deep zoom e áreas clicáveis definidas em `hotspots.json`.

## Entregável obrigatório: bastidores

Além do software, manter o site de bastidores (serviço `docs`, MkDocs Material com tema Carbon) com os 8 capítulos da spec. Cada capítulo tem resumo executivo e aprofundamento técnico. Atualizar a doc junto com o código de cada fase.

## Como trabalhar

- Desenvolvimento em fases, na ordem da seção "Entregáveis, critérios de aceite e fases" da spec. **Uma fase por vez.**
- Antes de codar uma fase, apresente o plano e espere minha aprovação.
- Ao fim de cada fase: `docker compose up` sobe limpo, testes passam e você me mostra como verificar o resultado.
- Commits pequenos, com mensagem clara em português.
- Na dúvida sobre uma decisão de produto, pergunte em vez de inventar.
