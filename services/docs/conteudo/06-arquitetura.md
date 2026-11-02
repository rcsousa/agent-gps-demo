# 6. Arquitetura

!!! abstract "Resumo executivo"
    Tudo roda em Docker e sobe com um único `docker compose up`. O agente tem **uma única porta de saída**: o MCP gateway. Cada área do banco (cliente, consentimento, risco, seguradoras, pagamentos, atendimento) é um servidor MCP atrás desse gateway. Assim, o gateway é o lugar onde as regras são aplicadas e onde tudo o que acontece pode ser observado.

## Aprofundamento técnico

### Fluxo

```
web ──► agent ──► mcp-gateway ──► skills-mcp
 │                    │          ├─► contexto-mcp ──► graph (Neo4j)
 │                    │          ├─► cliente-mcp
 │                    │          ├─► consentimento-mcp
 │                    │          ├─► risco-mcp
 │                    │          ├─► seguradoras-mcp
 │                    │          ├─► pagamentos-mcp
 │                    │          ├─► atendimento-mcp
 │                    │          └─► canais-mcp (prompts)
 │                    ▼
 │                   bus (Redis Streams) ◄── agent, simulator
 └─► /bastidores ──► docs

simulator ──► contexto-mcp /interno (grafo) e bus (domínios) · fora do alcance do agente
```

### Serviços

| Serviço | Papel | Stack |
| --- | --- | --- |
| `web` | Interface (Modo Mapa, Modo Raio-X, apresentador). Também serve os bastidores em `/bastidores/` | React + TypeScript, IBM Carbon, nginx |
| `docs` | Este site | MkDocs Material com tema Carbon |
| `agent` | Host MCP. Conhece só o gateway e o barramento | Python, FastAPI |
| `mcp-gateway` | Ponto único de acesso, governança e observação | Python, FastAPI, SDK MCP |
| `skills-mcp` | Catálogo de skills-workflow (`io.modelcontextprotocol/skills`) | Python, SDK MCP |
| `contexto-mcp` | Camada de contexto; único serviço que acessa o grafo | Python, SDK MCP, driver Neo4j |
| `cliente-mcp`, `consentimento-mcp`, `risco-mcp`, `seguradoras-mcp`, `pagamentos-mcp`, `atendimento-mcp` | Domínios de negócio | Python, SDK MCP |
| `canais-mcp` | Canais de atendimento: a persona do agente em cada canal, como prompts MCP | Python, SDK MCP |
| `graph` | Ontologia, instâncias e estado vivo | Neo4j 5 Community |
| `seed` | Recarrega o grafo com o estado-base da ontologia a cada subida e termina | Python (mesma imagem do `contexto-mcp`) |
| `bus` | Barramento de eventos | Redis 7 (Streams) |
| `simulator` | Injeta incidentes; decide o pedágio quando ninguém decide; fora do alcance do agente | Python, FastAPI |

### Decisões da Fase 1

**Barramento de eventos em Redis Streams.** A spec pede um barramento para os eventos `route.planned`, `step.started`, `tool.called`, `incident.detected`, `route.recalculated` e `human.required`, mas não fixava a tecnologia. Escolhemos Redis Streams, que é leve e guarda o histórico em ordem. Esse histórico serve de base para o replay offline e para o Raio-X provar que cada animação corresponde a um evento real.

**SDK MCP oficial v2.** Os servidores usam `MCPServer` (o antigo FastMCP) com transporte *streamable HTTP* em `/mcp`, em modo *stateless*.

**Saúde padronizada.** Todo serviço Python responde `GET /saude` com `{servico, status, versao, dependencias}`. Se uma dependência cai, a resposta vira HTTP 503, e o healthcheck do Docker passa a mostrar o problema. O `contexto-mcp`, por exemplo, só fica saudável quando o Neo4j responde.

**Upstreams por configuração.** A lista de servidores atrás do gateway fica em `services/mcp-gateway/config/upstreams.yaml`. Trocar, adicionar ou desligar um servidor não exige mudar o agente.

### O gateway: um endereço, todas as tools

O agente conecta em um único servidor MCP, `http://mcp-gateway:8000/mcp`, com `Authorization: Bearer $GATEWAY_TOKEN`. O gateway monta um **catálogo agregado**:

- Na subida, e depois a cada 30 s, ele lê `tools/list` e `resources/list` de cada servidor de `upstreams.yaml`.
- Os nomes ganham o prefixo do servidor: `obter_perfil` do `cliente-mcp` vira `cliente.obter_perfil`. São 41 tools ao todo.
- As tools `ping` dos servidores ficam de fora.
- Se um servidor cai, as tools dele continuam no catálogo, e a chamada devolve "trecho interditado". A rua continua no mapa; só fica bloqueada.
- Resources são roteados pelo esquema da URI (`contexto://mapa` → `contexto-mcp`).

Cerca de 15 dessas tools são **de distração**: plausíveis, às vezes perigosas, fora da jornada (`pagamentos.estornar`, `seguradoras.cancelar_apolice`, `consentimento.revogar`...). Elas existem para a cena 3 mostrar o que acontece quando o agente tem o mapa, mas não tem GPS. Três delas são **atalhos legados** tentadores (`seguradoras.contratacao_expressa`, `cliente.obter_dossie_completo`, `seguradoras.cotar_seguro_v1`): parecem certos para a tarefa, mas pulam regras (veja o capítulo 3).

**Ordem garantida por execução.** Quando a skill ativa tem um `workflow.yaml`, o gateway o lê na atualização do catálogo, com digest conferido, e guarda os fatos de cada execução no Redis (`bussola:fatos:<execucao_id>`, por 24 h): cada tool que deu certo, com o resultado estruturado. Antes de rotear, ele confere os pré-requisitos da tool contra esses fatos. A interpretação é pura e fica em `bussola_comum.workflow`.

**Proveniência em toda resposta.** O gateway acrescenta ao `_meta` de cada resultado:

```json
"bussola/proveniencia": {
  "chamada_id": "c380950190d7",
  "tool": "cliente.obter_perfil",
  "servidor": "cliente-mcp",
  "instante": "2026-11-01T14:13:58+00:00",
  "duracao_ms": 21,
  "status": "ok"
}
```

**Tools desligadas pelo apresentador.** O simulador guarda no barramento (`bussola:tools:fora`) as tools que o apresentador desligou. Antes de rotear cada chamada, o gateway consulta esse conjunto. Uma tool desligada devolve erro sem chegar ao servidor, com `status: erro` e `motivo: desligada` na proveniência e no evento.

**Cada chamada vira um evento.** O gateway publica no Redis Stream `bussola:eventos` uma entrada `tool.called` com os mesmos campos, mais os argumentos e o erro, quando há. É desse stream que o Raio-X (Fase 7) lê: o que aparece na tela é o que de fato trafegou.

### O mundo simulado

Os seis servidores de domínio operam sobre **dados mestres** comuns (`libs/bussola_comum/.../dados/cadastro.yaml`): clientes, imóveis, contas, consentimentos, laudos e áreas de risco. Os ids são os mesmos da ontologia. Os registros que a jornada cria (cotações, propostas, pagamentos, apólices, tickets) ficam no barramento, sob `bussola:dominio:*`.

O **simulador é o único escritor do estado vivo**. Quando o apresentador aplica um incidente, ele grava o efeito em dois lugares:

```
simulator ──► contexto-mcp /interno/estado ──► graph      (o mapa muda)
          └─► bus  bussola:estado:<id>     ──► domínios   (os sistemas mudam)
```

As rotas `/interno/*` do `contexto-mcp` são protegidas por `SIMULADOR_TOKEN`. Elas não são tools: o gateway não as enxerga, e o agente não as alcança. Assim continua valendo que só o `contexto-mcp` toca no Neo4j.

**Remover um incidente** volta tudo ao estado-base e reaplica os outros incidentes ativos, para nunca sobrar estado parcial. Duas reações acontecem sozinhas no relógio do simulador:

- **Pedágio:** se ninguém decidir em 30 s, a especialista Marina aprova.
- **Renovação de consentimento:** a cliente "confirma no app" depois de 5 s.

### Ordem de subida

Os `depends_on` usam `condition: service_healthy`, e o `seed` usa `service_completed_successfully`:

`graph` → `seed` (termina) → `contexto-mcp` · (`bus` + os 9 servidores MCP) → `mcp-gateway` → `agent` → `web` (junto com `docs`). O `simulator` sobe depois do `contexto-mcp`.

### O agente: um host MCP que só conhece o gateway

O `agent` recebe um pedido ("Quero contratar um seguro residencial para meu apartamento"), conversa com a Ana e dirige a jornada chamando tools. Ele conhece só dois endereços: `GATEWAY_URL` e `BUS_URL`. Nenhum servidor de domínio aparece no código dele.

A mesma tarefa roda em **três modos**, que são as cenas 2 a 5 da demo:

| Modo | O que o modelo recebe | O que a plateia vê |
| --- | --- | --- |
| `sem_contexto` | Só o prompt de assistente e a conversa com a cliente. Nenhuma tool de negócio | Uma resposta confiante e inventada, sem consentimento |
| `sem_skill` | As 41 tools do gateway, sem skill e sem `_meta` de skill | O agente explora, chama tools irrelevantes e erra a ordem |
| `com_skill` | O catálogo de skills. Ao carregar uma, ganha só as tools permitidas, e toda chamada leva `_meta["bussola/skill"]` | A navegação guiada, parada a parada |

**Ferramentas do host.** Algumas tools são do próprio agente e não passam pelo gateway:

- `agente.carregar_skill` e `agente.ler_arquivo_skill`: leem o `SKILL.md` e as `references/*.md` sob demanda, conferindo tamanho e digest (*progressive disclosure*);
- `navegacao.planejar_rota`, `navegacao.iniciar_parada` e `navegacao.recalcular_rota`: o modelo narra a viagem, e cada uma vira um evento do mapa, com a estimativa lida em `contexto.consultar_rota`;
- `conversa.perguntar_cliente`: a execução pausa (`aguardando_cliente`) até o apresentador responder, no papel de quem está do outro lado no canal (a Ana, o gerente ou o atendente). A pergunta pode trazer opções sugeridas, para a resposta sair em um clique.

Toda chamada ao gateway leva também `_meta["bussola/execucao"]` com o id da execução. O gateway repete esse id na proveniência e no `tool.called`, e o Raio-X filtra o barramento por execução.

### O prompt do agente em três camadas

O system prompt não fica todo no código. Ele é montado a cada execução, em três camadas, e cada uma mora num lugar:

| Camada | O que diz | Onde mora |
| --- | --- | --- |
| **Persona do canal** | Quem é o agente, com quem fala e em que tom | Prompts MCP do `canais-mcp`, pelo gateway (`canais.atendimento_app`, `_agencia`, `_central`) |
| **Instruções do host** | Como usar as ferramentas que só o agente tem (`conversa.*`, `navegacao.*`, `agente.*`) | Código do agente (`agent/prompts.py`) |
| **Workflow do negócio** | Quais tools, em que ordem, o que fazer nos desvios | Skills (SEP-2640), carregadas sob demanda |

Cada execução escolhe um **canal**, que é uma entidade da ontologia:

| Canal | Com quem o agente fala | Como muda o atendimento |
| --- | --- | --- |
| `app` (padrão) | A própria Ana, no celular | Frases curtas, opções para tocar, confirmações dela pelo app |
| `agencia` | O gerente, ao lado da Ana | Fala com o gerente na terceira pessoa da Ana; o aceite é dela, dito ao gerente |
| `central` | O atendente, ao telefone com a Ana | Texto para ler em voz alta, sem tabelas nem links; o atendente confirma o aceite palavra por palavra |

O agente pede a persona com `prompts/get` ao gateway, passando o `cliente_id`. O gateway roteia o pedido ao `canais-mcp`, carimba a proveniência e publica `prompt.read`. O agente registra o que usou em `prompt.loaded`. Assim, até o jeito de atender vem do banco, versionado e observável no Raio-X, e um canal novo entra sem mudar o agente.

Duas exceções usam uma persona mínima embutida no agente, e o `prompt.loaded` diz `origem: embutido`:

- o modo `sem_contexto`, que por definição não consulta o banco;
- a persona indisponível (por exemplo, o `canais-mcp` fora do ar). A execução segue, com o motivo no evento.

O provedor `roteiro` não lê prompt, porque não tem LLM. Ele adapta as falas ao canal da execução, para o efeito aparecer no ensaio sem chave. Com um modelo de verdade, quem muda o comportamento é o texto da persona.

### A interface única de LLM

Cada provedor implementa o mesmo contrato (`agent/llm/base.py`): `passo(tools)` devolve o texto, as chamadas de tool, se acabou e o uso de tokens; `adicionar_resultados(...)` devolve os resultados ao modelo. O motor de execução não sabe com quem está falando.

| Provedor | Como funciona |
| --- | --- |
| `anthropic` | SDK oficial, Messages API com tools. Modelo padrão `claude-opus-5-5`, esforço `medium`, prompt de sistema em cache e *fallbacks* do lado do servidor ligados por padrão (`ANTHROPIC_FALLBACKS`) |
| `azure_openai` | SDK `openai`, Chat Completions com tools no seu *deployment* |
| `roteiro` | **Sem LLM.** Um ensaio determinístico que percorre a jornada chamando as mesmas tools pelo gateway e decide pelo resultado de cada uma. Serve para ensaiar sem chave e sem rede, e para o smoke. Aparece como "roteiro" nos eventos: não finge inteligência |

As APIs não aceitam ponto em nome de tool, então o adaptador troca `cliente.obter_perfil` por `cliente__obter_perfil` na ida e desfaz na volta.

### Como trocar o provedor de LLM

Mude `LLM_PROVIDER` no `.env` para `anthropic` ou `azure_openai` e preencha as variáveis do provedor.

| Onde o modelo roda | Variáveis |
| --- | --- |
| **Claude no Microsoft Foundry (Azure)**, o padrão da demo | `LLM_PROVIDER=anthropic`, `ANTHROPIC_PLATAFORMA=foundry`, `ANTHROPIC_FOUNDRY_BASE_URL` (o endpoint do recurso, terminando em `/anthropic/`), `ANTHROPIC_FOUNDRY_API_KEY` e `ANTHROPIC_MODEL` com o nome do deployment |
| Claude na API da Anthropic | `LLM_PROVIDER=anthropic`, `ANTHROPIC_PLATAFORMA=api`, `ANTHROPIC_API_KEY` e `ANTHROPIC_MODEL` |
| Azure OpenAI | `LLM_PROVIDER=azure_openai`, `AZURE_OPENAI_ENDPOINT`, `_API_KEY`, `_DEPLOYMENT` e `_API_VERSION` |

O Foundry é a mesma API do Claude, com outro cliente do SDK (`AsyncAnthropicFoundry`): o resto do provedor não muda. Duas diferenças tratadas no código:

- o Foundry não oferece *fallback* do lado do servidor, então ele fica desligado lá, mesmo com `ANTHROPIC_FALLBACKS=true`;
- deployments costumam ter limite de tokens por minuto. O provedor usa cache automático, que cobre também o histórico da conversa, e, se ainda assim receber um 429, espera o tempo pedido pela API e tenta de novo. Cada execução também pode pedir outro provedor, por exemplo `"provedor": "roteiro"`. Sem chave, a execução termina com status `erro` e uma mensagem dizendo qual variável falta.

### Modelo por execução

`ANTHROPIC_MODEL` é o padrão de fábrica: o Claude Haiku 5.5. `ANTHROPIC_MODELOS` lista outros deployments que podem ser escolhidos, como o Opus 5.5.

- **No painel:** o seletor do indicador de LLM troca o modelo das próximas execuções sem reiniciar nada. A escolha fica no barramento (`bussola:llm:modelo`), por `PUT /api/llm/modelo`.
- **Por execução:** `"modelo"` na API, ou `--modelo` nos scripts.
- **No evento:** o `run.started` registra o modelo usado.

**Custo por execução.** `LLM_PRECOS` traz o preço por token de cada modelo, e `CACHE_LEITURA_FATOR` e `CACHE_ESCRITA_FATOR` trazem o desconto do cache de prompt. Ao fim de cada execução, o agente calcula o custo em US$ (`agent.custos`) e o publica em `run.finished.metricas.custo_usd`, por componente, com e sem cache. É o dado do placar.

**A lista de tools não muda durante a conversa.** Os modelos atuais vinculam o raciocínio já feito ao prefixo exato da conversa (pensamento preservado), e acrescentar tools no meio invalida esse vínculo: a API recusa a chamada seguinte. Por isso, no modo com skill, o modelo vê desde o primeiro passo as tools de alguma skill, e o host as recusa até a skill ser carregada. Depois, o gateway aplica a skill e a ordem.

### O dashboard: o código vem do próprio servidor

O dashboard de status (`/status`) mostra o código de cada tool e a fonte de cada prompt. Esse código não é copiado para o web nem para o agente: cada servidor MCP o serve, pela fábrica comum (`bussola_comum.mcp_servidor`), num **resource template**:

```
fonte://<servidor>/tool/<nome>     a função Python registrada (inspect.getsource), com arquivo e linha
fonte://<servidor>/prompt/<nome>   a fonte do prompt (no canais-mcp, o .md do canal)
```

Por ser um template, e não um resource listado, ele não aparece no `resources/list` e não entra no catálogo que o agente recebe. **O modelo nunca vê código.** O gateway roteia `fonte://` pelo nome do servidor.

Os dados do dashboard seguem o mesmo caminho de sempre:

```
web ──► agent /api/catalogo ──► mcp-gateway (tools/list, prompts/list, skills/list, fonte://, skill://)
                            └─► bus (últimas chamadas de cada tool, prompt ou skill)
web ──► /simulador ──► simulator   (só o liga/desliga das tools)
```

### O Modo Mapa: a cidade é o grafo

O mapa não é desenhado à mão. Tudo o que aparece nele vem de três consultas, sempre pelo gateway:

```
web ──► agent /api/mapa                ──► gateway ──► contexto://mapa              (bairros, rio, avenidas, nós com x/y e status, arestas)
web ──► agent /api/mapa/rotas          ──► gateway ──► contexto.consultar_rota      (as 3 rotas, paradas, tempo, custo, risco, alertas)
web ──► agent /api/mapa/entidade/{id}  ──► gateway ──► contexto.consultar_entidade  (atributos, estado, proveniência, vizinhos)
web ──► agent /api/execucoes/{id}/eventos  (SSE)    ──► a viagem
```

A cidade e as rotas são relidas a cada 5 s: esse é o **trânsito**. Quando o simulador derruba a API da Âncora, o nó fica vermelho, com o ícone ✕. As rotas que passam por ele aparecem como interditadas, antes mesmo de qualquer viagem.

**Por que deck.gl em vista ortográfica, e não MapLibre:**
- A cidade usa coordenadas próprias (1000 × 700, gravadas no grafo pelo seed), não latitude e longitude.
- Um mapa geográfico pediria uma projeção falsa e um mapa-base vazio.
- O deck.gl, com `OrthographicView`, desenha direto essas coordenadas em WebGL, com pan, zoom, seleção por clique e transições.

**As camadas, de baixo para cima:**

| Camada | deck.gl | De onde vem |
| --- | --- | --- |
| Bairros, rio e avenidas | `PolygonLayer`, `PathLayer`, `LineLayer` | `contexto://mapa` |
| Arestas do grafo | `LineLayer` (a partir de um certo zoom) | `contexto://mapa` |
| Rotas disponíveis, tracejadas | `PathLayer` + `PathStyleExtension` | `contexto.consultar_rota` |
| Rota da viagem e o rastro animado | `PathLayer` + `TripsLayer` | `route.planned` / `route.recalculated` |
| Nós com semáforo e ícone de status | `ScatterplotLayer` + `TextLayer` | status do nó no grafo |
| Paradas numeradas | `ScatterplotLayer` + `TextLayer` | paradas da rota |
| Pulsos nos sistemas chamados | `ScatterplotLayer` | `tool.called` |
| Robô e pino de chegada | `IconLayer` (SVG próprio) | `step.started` / `run.finished` |

**Zoom semântico:**
- de longe, aparecem os bairros e seus nomes;
- ao aproximar, surgem as arestas e depois os nomes dos nós;
- bem perto, aparece o tipo de cada relação.

Os nomes que se sobreporiam ficam de fora até haver espaço. As paradas e os nós com problema têm prioridade.

**Toda animação é um evento.** O mapa não anima nada por conta própria:

| Evento (SSE) | O que acontece no mapa |
| --- | --- |
| `run.started` | O robô aparece no ponto de partida do canal (app, agência ou central) |
| `skill.loaded` | O painel Conversa mostra o navegador, isto é, a skill ativa |
| `route.planned` | A rota escolhida vira a linha laranja com rastro animado, e um aviso mostra o motivo da escolha |
| `step.started` | O robô anda até a parada em 600 ms e ela fica laranja. Com "Seguir o agente", a câmera vai junto |
| `tool.called` | Um pulso no nó do sistema chamado: laranja se deu certo, vermelho se falhou |
| `incident.detected` | Um aviso vermelho com ícone e a metáfora (Rua interditada, Contramão...) e um anel no nó |
| `route.recalculated` | Um aviso de recálculo, com motivo e regra, e a troca da linha da rota |
| `human.required` | O pedágio aparece na parada de aprovação |
| `client.asked` / `agent.message` | A pergunta e as opções aparecem no painel Conversa, para responder pela Ana |
| `run.finished` | O pino de chegada com o número da apólice, ou o motivo da parada, com duração, custo e modelo |

Nos modos sem contexto e sem skill, o agente não planeja rota. Por isso, o mapa mostra só os pulsos nos sistemas e a conversa. A ausência da linha laranja é o próprio argumento: **sem GPS, não há rota**.

### A tela de abertura: o infográfico navegável

Em `/`, o infográfico oficial (`docs/assets/mapa-da-demo.png`, 4096 × 6144) abre em deep zoom com o OpenSeadragon. Os tiles são gerados no build do Docker do `web`, com `vips dzsave`, num estágio Debian. O PNG original fica só no repositório.

As 36 áreas clicáveis estão em `services/web/src/abertura/hotspots.json`, em porcentagem da imagem, e acompanham o pan e o zoom. Cada área leva a um de três destinos:
- uma cena do mapa (`/mapa?cena=N`);
- uma parada (`/mapa?parada=N`);
- um capítulo destes bastidores.

### Catálogo de eventos

Tudo vai para o stream `bussola:eventos`, no formato `{tipo, origem, instante, dados}`, sempre com `execucao_id`:

| Evento | Quem emite | Quando |
| --- | --- | --- |
| `run.started` / `run.finished` | agent | Início (sempre o primeiro evento) e fim, com modo, canal, provedor, modelo, status, apólice e métricas |
| `prompt.loaded` | agent | A persona usada: nome, canal e origem (`gateway` ou `embutido`, com o motivo) |
| `skill.loaded` | agent | A skill foi carregada e verificada |
| `route.planned`, `step.started`, `route.recalculated` | agent | Ferramentas de navegação |
| `incident.detected` | agent | O resultado de uma tool revela um incidente (API fora, contramão, pedágio...) |
| `human.required` | agent | Pedido de aprovação a um especialista |
| `client.asked` / `client.answered` | agent | Conversa com a Ana |
| `agent.message` | agent | Texto do agente para a cliente |
| `tool.called` | gateway | Toda chamada de tool, com a skill ativa e o `execucao_id` |
| `skills.listed`, `resource.read` | gateway | Leituras do catálogo de skills |
| `prompt.read` | gateway | Leitura de um prompt, com proveniência e `execucao_id` |

O agente não sabe o que o simulador fez. O `incident.detected` vem do que as tools responderam, já com a metáfora do mapa (Rua interditada, Contramão, Pedágio...).

**Métricas no `run.finished`:** chamadas de tool, tools distintas, tools irrelevantes (as que não estão em nenhuma skill), bloqueios do gateway, incidentes, erros, tokens (entrada, saída e cache) e duração. São a base do placar comparativo da Fase 7.

### Fluxo de uma execução

```
POST /api/execucoes {modo}  ──► run.started
  └─ laço: passo do modelo ──► tools pedidas
       ├─ do host (skill, navegação, conversa)            ──► eventos do mapa
       └─ do gateway (com _meta de skill e de execução)   ──► tool.called
            └─ incidente no resultado?                    ──► incident.detected
  └─ fim natural, limite de 40 passos ou erro             ──► run.finished
GET /api/execucoes/{id}/eventos  ◄── SSE: o stream desde o início, depois ao vivo
```

O estado de cada execução fica em `bussola:execucoes:<id>`: status, pergunta pendente e métricas.
