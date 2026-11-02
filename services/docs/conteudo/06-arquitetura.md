# 6. Arquitetura

!!! abstract "Resumo executivo"
    Tudo roda em Docker e sobe com um único `docker compose up`. O agente tem **uma única porta de saída**: o MCP gateway. Cada área do banco (cliente, consentimento, risco, seguradoras, pagamentos, atendimento) é um servidor MCP atrás desse gateway. Assim, o gateway é o lugar onde as regras são aplicadas e onde tudo o que acontece pode ser observado.

## Aprofundamento técnico

### Fluxo

Quem fala com quem. O diagrama é gerado no build a partir do `docker-compose.yml` e da lista de servidores do gateway (`mcp-gateway/config/upstreams.yaml`): um serviço novo aparece aqui sem ninguém editar a doc.

![Os serviços da demo e quem fala com quem](assets/diagramas/arquitetura.svg)

- O **agente** só conhece o **gateway** (MCP) e o **barramento** (eventos).
- Cada área do banco é um **servidor MCP** atrás do gateway.
- O **simulador** muda o mundo (o grafo e os domínios) e fica fora do alcance do agente.
- O **web** fala com o agente (`/api`), com o simulador (`/simulador`, só o apresentador) e serve estes bastidores (`/bastidores`).

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

A cidade e as rotas são relidas a cada 5 s: esse é o **trânsito**. Quando o simulador derruba a API da Âncora, um **farol** vermelho, com o ícone ✕ e o nome do sistema, sobe do bairro Parceiros. As rotas que passam por ele aparecem como interditadas, antes mesmo de qualquer viagem. Os faróis valem só para infraestrutura: sistemas, APIs, filas, canais e regras. O estado de um dado de cliente, como um consentimento revogado, aparece só dentro do bairro.

**Uma cidade em 3D, sem MapLibre:**
- A cidade usa coordenadas próprias (1000 × 700, gravadas no grafo pelo seed), não latitude e longitude. Um mapa geográfico pediria uma projeção falsa e um mapa-base vazio.
- O deck.gl, com `OrbitView`, desenha essas coordenadas em WebGL, com a câmera inclinada (cerca de 50°) e alinhada ao norte, sem giro: o 3D vem só da perspectiva. Tem luz ambiente e direcional, pan, zoom e seleção por clique.
- Os prédios genéricos são decoração gerada com semente fixa (`cidade3d.ts`): sempre os mesmos, na cor de cada bairro, fora das avenidas, das estradas e dos nós.
- Os nomes são **chips em HTML** (IBM Plex, a partir de 14 px), projetados da cena para a tela, e não texto desenhado no WebGL. Os que se sobreporiam ficam de fora, por prioridade (farol, parada, bairro, sistema), e nenhum cobre o robô.

**Dois níveis de leitura:**

| Nível | O que aparece | Como se chega |
| --- | --- | --- |
| Cidade | Bairros em relevo, prédios, rio, avenidas, as estradas da jornada, as 9 paradas, os faróis de incidente e o robô | A vista inicial, "Enquadrar a cidade" ou "Voltar à cidade" |
| Bairro aberto | Os nós daquele bairro viram **prédios-sistema**, com altura pela categoria, o status no telhado e placas com o nome. As relações internas aparecem no chão, e as do nó selecionado com outros bairros viram arcos | Ao clicar no bairro, ao aproximar bem o zoom, ou quando o agente chega a uma parada daquele bairro, com "Seguir o agente" ligado |

O bairro aberto não é um estado guardado: ele deriva da câmera. Perto o bastante, abre o bairro que está sob o centro da tela.

**As camadas:**

| Camada | deck.gl | De onde vem |
| --- | --- | --- |
| Chão, rio, bairros em relevo, avenidas | `SolidPolygonLayer` extrudada, `PathLayer` | `contexto://mapa` |
| Prédios e árvores | `SolidPolygonLayer` extrudada, `ColumnLayer` | gerados a partir dos bairros (decoração) |
| Prédios-sistema e telhados de status | `SolidPolygonLayer` extrudada | os nós do bairro aberto e seu status |
| Estradas da jornada | `PathLayer` + `PathStyleExtension` (curvas Catmull-Rom) | `contexto.consultar_rota` |
| Trecho já percorrido | `TripsLayer`, até a posição do robô | `route.planned` / `step.started` |
| Paradas | marcos 3D (`SolidPolygonLayer`) | paradas da rota |
| Faróis de incidente | colunas finas (`SolidPolygonLayer`) e anel | status dos nós de infraestrutura |
| Chamadas do agente | `ArcLayer` do robô ao sistema e pulso no chão | `tool.called` |
| Robô e pino de chegada | `IconLayer` (SVG próprio), sempre por cima | `step.started` / `run.finished` |

### O diretor de animações

O agente pode andar mais rápido do que a plateia consegue acompanhar: o roteiro termina em cerca de 9 s. Por isso, o mapa não aplica os eventos no instante em que chegam. O **diretor** (`mapa/diretor.ts`) os reproduz **na ordem**, com um tempo mínimo para cada um:

| Evento | Tempo mínimo no mapa |
| --- | --- |
| `step.started` | 1,6 s de deslocamento pela estrada e 0,6 s parado na parada |
| `route.planned` | 1,3 s |
| `incident.detected`, `route.recalculated` | 1,6 s |
| `human.required` | 1,2 s |
| `tool.called` | 0,35 s (o arco e o pulso) |
| Conversa e fim | imediato |

**Por que isso é honesto:**
- nenhum evento é criado e a ordem não muda;
- o mapa só fica alguns segundos **atrás** do agente, e o selo mostra "Reproduzindo · +N eventos" até alcançar e passar a "Ao vivo";
- "Pular para o fim" alcança o presente de uma vez;
- a conversa com a Ana usa o estado real, sem atraso: dá para responder enquanto o mapa ainda anima.

Abrir um link `/mapa?execucao=<id>` antigo reproduz a viagem inteira desde o início, pelo mesmo caminho.

**A linha do tempo no rodapé** espelha a faixa "As 9 paradas" do infográfico: cada parada aparece como feita, atual ou pendente, e fica vermelha se um incidente apareceu ali. Acima dela, uma linha de narração diz o passo, por exemplo "Parada 6 · Cotação — chamou seguradoras.cotar_seguro".

**Toda animação é um evento:**

| Evento (SSE) | O que acontece no mapa |
| --- | --- |
| `run.started` | O robô aparece no ponto de partida do canal (app, agência ou central) |
| `skill.loaded` | O painel Conversa mostra o navegador, isto é, a skill ativa |
| `route.planned` | A estrada escolhida fica laranja, e um aviso mostra o motivo da escolha |
| `step.started` | O robô percorre a estrada até a parada e o trecho percorrido acende. A parada cresce e a linha do tempo avança. Com "Seguir o agente", a câmera vai junto e abre o bairro |
| `tool.called` | Um arco do robô até o sistema chamado e um pulso no chão: laranja se deu certo, vermelho se falhou |
| `incident.detected` | Um aviso vermelho com ícone e a metáfora (Rua interditada, Contramão...), e a parada fica vermelha na linha do tempo |
| `route.recalculated` | Um aviso de recálculo, com motivo e regra, e a troca da estrada |
| `human.required` | O pedágio aparece na parada de aprovação |
| `client.asked` / `agent.message` | A pergunta e as opções aparecem no painel Conversa, para responder pela Ana |
| `run.finished` | O pino de chegada com o número da apólice, ou o motivo da parada, com duração, custo e modelo |

Nos modos sem contexto e sem skill, o agente não planeja rota. O robô fica no ponto de partida e os arcos saem dele para os sistemas que ele chama. A narração diz "Sem GPS: o agente não planejou rota". A ausência da estrada laranja é o próprio argumento: **sem GPS, não há rota**.

### A tela de abertura: o infográfico navegável

Em `/`, o infográfico oficial (`docs/assets/infografico_horizontal.jpeg`, 2198 × 1446) abre com zoom e pan do OpenSeadragon. Os tiles são gerados no build do Docker do `web`, com `vips dzsave`, num estágio Debian.

As 38 áreas clicáveis estão em `services/web/src/abertura/hotspots.json`, em porcentagem da imagem, e acompanham o pan e o zoom. Cada área leva a um de três destinos:
- uma cena do mapa (`/mapa?cena=N`);
- uma parada (`/mapa?parada=N`, que abre o bairro da parada);
- um capítulo destes bastidores. A tabela "A metáfora", por exemplo, leva ao capítulo 8.

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
| `model.step` | agent | Cada chamada ao modelo: tokens (entrada, saída e cache), duração e tools pedidas. Nenhum texto do modelo |
| `tool.called` | gateway | Toda chamada de tool, com a skill ativa, o `execucao_id`, a duração, o resultado resumido (até 2.000 caracteres) e o erro |
| `tools.listed` | gateway | O `tools/list` de uma execução |
| `skills.listed`, `skill.read` | gateway | `skills/list` e `skills/get` (SEP-2640) |
| `resource.read` | gateway | A leitura de um arquivo de skill (`skill://`), com tamanho, duração e skill ativa |
| `prompt.read` | gateway | Leitura de um prompt, com proveniência e `execucao_id` |

**Toda requisição do agente ao gateway leva `_meta`** com a execução (e a skill ativa, se houver): tools, `tools/list`, `skills/list`, `skills/get`, `resources/read` e `prompts/get`. É assim que o Raio-X mostra o protocolo inteiro de uma viagem, sem misturar com o que outras execuções ou o dashboard pediram.

O agente não sabe o que o simulador fez. O `incident.detected` vem do que as tools responderam, já com a metáfora do mapa (Rua interditada, Contramão, Pedágio...).

**Métricas no `run.finished`:** chamadas de tool, tools distintas, tools irrelevantes (as que não estão em nenhuma skill), bloqueios do gateway, incidentes, erros, tokens (entrada, saída e cache), duração, custo e **as regras do banco cumpridas**.

### O placar: regras conferidas nos eventos

O verificador de regras (`bussola_comum.regras`) é o mesmo do experimento com o modelo real (`./scripts/experimento.sh`).
- **O caso da viagem** vem dos incidentes ativos quando ela começa: o web pergunta ao simulador e os envia no pedido. Sem incidente, o caso é o caminho feliz.
- **No fim de cada execução**, o agente lê os eventos dela no barramento (os dele e os do gateway) e confere as regras do caso. O resultado vai em `run.finished.metricas.regras`.
- **Só conta o que trafegou:** uma tentativa barrada pelo gateway (fora de ordem ou contramão) não aconteceu.
- `GET /api/placar` agrega as execuções terminadas por modo × modelo (regras, execuções perfeitas, tempo e custo médios) e traz, ao lado, a **referência** versionada do experimento Opus × Haiku (`agent/dados/placar-referencia.json`).

### Gravações e replay offline

```
POST /api/gravacoes {execucao, cena, incidentes}  ──► gravacoes/cena-<n>.jsonl (cabeçalho + eventos)
GET  /api/gravacoes                               ──► a lista (cabeçalhos)
GET  /api/gravacoes/<nome>/eventos                ──► SSE no mesmo formato do ao vivo, no ritmo original
```

- **Uma gravação é a execução real**, como saiu do barramento. O cabeçalho guarda cena, modo, canal, modelo, apólice, data e os incidentes ativos.
- **A pasta `gravacoes/` é um volume do `agent` e fica versionada no repositório.** Numa máquina nova, sem rede e sem chave, as cenas tocam do mesmo jeito.
- **No replay:**
  - o web reaplica os incidentes da gravação pelo simulador, para o trânsito do mapa bater;
  - o agente serve os eventos com as esperas originais, com teto de 3 s;
  - o mesmo diretor de animações desenha tudo;
  - ninguém responde pela Ana (as respostas estão gravadas);
  - o selo "Replay · gravado em … com …" fica na tela o tempo todo.

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
