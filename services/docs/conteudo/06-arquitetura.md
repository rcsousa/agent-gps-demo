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

**Cada chamada vira um evento.** O gateway publica no Redis Stream `bussola:eventos` uma entrada `tool.called` com os mesmos campos, mais os argumentos e o erro, quando há. É desse stream que o Modo Raio-X lê: o que aparece na tela é o que de fato trafegou.

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

O mapa não é desenhado à mão. Tudo o que aparece nele vem de duas consultas, sempre pelo gateway, e do fluxo de eventos da viagem:

```
web ──► agent /api/mapa                ──► gateway ──► contexto://mapa              (grade, bairros, rio, lugares com posição, porta, estilo e status, arestas)
web ──► agent /api/mapa/entidade/{id}  ──► gateway ──► contexto.consultar_entidade  (atributos, estado, proveniência, vizinhos)
web ──► agent /api/execucoes/{id}/eventos  (SSE)    ──► a viagem
```

A cidade é relida a cada 5 s: esse é o **trânsito**. Quando o simulador derruba a API da Âncora, um **farol** vermelho, com o ícone ✕ e o nome do sistema, sobe do prédio dela. Os faróis valem só para infraestrutura: sistemas, APIs, filas, canais e regras. O estado de um dado de cliente, como um consentimento revogado, aparece só no painel.

**Uma cidade em grade, como num GPS** (`contexto_mcp/layout.py`, versionado em `ontologia/layout.json`):

- **A grade:** a cidade tem 10 × 7 quadras, cortadas por ruas, e as avenidas, mais largas, separam os bairros. Cada bairro é uma região de quadras e se distingue só pela cor do chão.
- **Um lugar por lote:** cada lugar do grafo (um sistema, um cliente, uma regra) ocupa um lote do seu bairro, com a **porta** voltada para a rua. Lugares ligados ficam perto, pelo layout de forças, com semente fixa. Num bairro com poucos lugares, eles se juntam perto do centro, e os lotes da borda viram praças.
- **As paradas** viram placas numeradas nas esquinas.
- **O rio:** as quadras que ele cruza viram água, e as ruas que o atravessam, pontes.

**Só o que existe:** cada lugar vira uma construção, e não há nenhum prédio decorativo. A forma vem do tipo e, quando o tipo não tem forma própria, de uma variante do bairro sorteada com semente pelo id (`layout.py:estilo`). O bairro tem cara de bairro, mas as construções não são todas iguais:

| Bairro | Construções |
| --- | --- |
| Cliente e Relacionamento | Casas, sobrados e prédios residenciais (o imóvel segue o que a cliente tem: apartamento, casa, sobrado); a sede laranja do Banco Bússola (CRM e core), a agência e a torre do app |
| Regras e Governança | Prédios públicos com colunas e frontão (políticas e bases legais), o edifício com cúpula (normas), escritórios (regras, scores e alçadas) e a central de vidro (motor de risco, cofre de consentimentos e registro) |
| Produtos e Ofertas | Lojas com toldo, galerias e o shopping (os produtos de seguro) |
| Serviços e Parceiros | Torres de vidro (seguradoras), prédios técnicos com antena (APIs e SLAs), a oficina (vistorias) e escritórios (especialistas e filas) |
| Pagamentos e Emissão | Agências (meios de pagamento), o data center com grelhas (gateway) e cartórios (APIs de emissão) |

As construções são malhas 3D simples, montadas em código (`mapa/construcoes.ts`) e desenhadas com `SimpleMeshLayer`. Cada uma tem três partes:

- o **corpo**, na cor do bairro, com o tom e a altura variando por construção;
- o **detalhe** (telhado, toldo, colunas, cúpula, letreiro, antena…);
- o **vidro**: janelas por andar, faixas de vidro, vitrines e a porta, sempre voltada para a rua.

O sol vem baixo, do sudeste, para marcar as fachadas que a câmera vê. Os lotes vazios viram praças.

**Câmera e rótulos:**

- O deck.gl, com `OrbitView`, desenha as coordenadas próprias da cidade (1000 × 700) em WebGL, sem mapa-base geográfico. O norte fica sempre para cima.
- **Câmera de GPS, com visão traseira:** durante a viagem, a câmera fica baixa (34°) e próxima e segue o robô **a cada quadro**.
  - O mapa gira para a direção da viagem ficar para cima, como num GPS de carro. O rumo vem do trecho atual, e o giro é suave, pelo menor ângulo.
  - A câmera mira um pouco à frente do robô, que aparece abaixo do centro.
  - Ao fim da viagem, ela sobe uma vez para a vista aérea da cidade inteira (55°), com o norte para cima, e fica livre para o apresentador.
- **Câmera livre:** o apresentador gira e inclina o mapa com o botão direito (ou Ctrl + arrastar) e com os botões de girar e inclinar. A bússola mostra o rumo e, ao clicar, volta o norte para cima.
- Mexer na câmera (arrastar, dar zoom, girar ou inclinar) pausa o seguimento até "Seguir o agente" ser religado. A cidade é relida a cada 5 s, e nada disso move a câmera.
- De longe, aparecem os nomes dos bairros, as placas das paradas e os faróis. De perto, os nomes das construções. No GPS, só os nomes dos lugares da viagem.
- Os nomes são **chips em HTML** (IBM Plex, a partir de 14 px). Os que se sobreporiam ficam de fora, por prioridade, e nenhum cobre o robô.
- Clicar numa construção mostra a proveniência daquele lugar.

**As 3 rotas da ontologia não aparecem no mapa.** O que aparece é o caminho que o robô realmente percorreu. A escolha e o recálculo de rota continuam como eventos: no Raio-X, e o recálculo também como aviso no mapa.

### O diretor de animações

O agente pode andar mais rápido do que a plateia consegue acompanhar: o roteiro termina em cerca de 9 s. Por isso, o mapa não aplica os eventos no instante em que chegam. O **diretor** (`mapa/diretor.ts`) os reproduz **na ordem**, com um tempo mínimo para cada um.

**O robô anda pelas ruas** (`mapa/ruas.ts`): a cada evento que o leva a um lugar, ele vai da porta onde está até a porta do destino, pelo meio das ruas, em ângulos retos.

- Um `step.started` o leva à placa da parada.
- Um `tool.called` o leva ao prédio do sistema chamado. Há uma exceção: a adequação, a proposta e o aceite tratam do produto, e levam o robô ao prédio do produto, no bairro de produtos. Sem isso, as paradas 5 e 7 ficavam sem balão, porque as ferramentas delas apontavam para prédios da governança.
- O tempo do trecho é proporcional à distância, entre 0,6 e 1,8 s.

| Evento | Tempo mínimo no mapa |
| --- | --- |
| `step.started` | o trecho até a placa e 0,6 s parado nela |
| `tool.called` | o trecho até o prédio e 0,35 s do pulso |
| `route.planned` | 0,8 s |
| `incident.detected`, `route.recalculated` | 1,6 s |
| `human.required` | 1,2 s |
| `client.asked`, `agent.message` | 0,8 s |
| Resposta da Ana e fim | imediato |

No código (`web/src/mapa/diretor.ts`):

```ts
--8<-- "web/diretor.ts:retencao"
```

### Os anúncios do GPS e os modos de pausa

O robô anuncia a viagem como um navegador de trânsito, num **balão de fala** preso acima do pino. Os anúncios que são a voz do GPS (apresentação, roteiro, rota, paradas, recálculo, pedágio, pergunta e chegada) vêm com o selo **GPS**, em azul-marinho. Os sistemas que o agente chama ficam com a borda laranja, e falhas e incidentes em vermelho, sempre com ícone.

Cada anúncio nasce de um evento real do barramento (`mapa/baloes.ts`). A frase é fixa, no arquivo de mensagens. Os dados vêm do evento: a rota e o motivo que o agente escreveu, a parada, a regra e a estimativa. Nada vem de um roteiro.

| Evento | Anúncio |
| --- | --- |
| `run.started` | "Olá! Sou o GPS do Banco Bússola…", com a partida (o canal) e o destino (o pedido da cliente). Sem skill: "Saindo sem GPS…". Sem contexto: "Saindo sem mapa…" |
| `skill.loaded` | "Roteiro carregado: Contratação de seguro residencial. Vou seguir por ele, com 18 ferramentas liberadas no caminho." |
| `route.planned` | "Rota rápida traçada: 9 paradas, ~5 min, risco baixo.", com o motivo escrito pelo agente embaixo |
| `step.started` | "Parada 3 de 9: Consentimento e LGPD.", com o que o GPS vai fazer ali e "A seguir: Elegibilidade." (ou "É a última parada.") |
| `tool.called` | A frase da tool em pt-BR ("Cotando com a Farol"), com a tool e a duração em mono. Falha: "… não respondeu" ou "O gateway barrou a chamada", em vermelho |
| `incident.detected` | "Atenção: rua interditada à frente.", com a descrição do incidente |
| `route.recalculated` | "Recalculando… Saio da Rota rápida e sigo pela Rota assistida." (ou "Sigo na Rota econômica, por outro caminho."), com o motivo e "Nova estimativa: ~6 min (antes ~5 min).", e a regra em mono |
| `human.required` | "Pedágio à frente: preciso da aprovação de um especialista para seguir.", com o motivo |
| `client.asked` | "Preciso de uma resposta da cliente.", com a primeira frase da pergunta (a pergunta inteira fica no painel Conversa) |
| `run.finished` | "Você chegou ao destino: apólice FAR-… emitida." ou o motivo de a viagem ter parado |

**A voz do GPS** (interruptor "Voz do GPS" na barra, desligado por padrão e guardado no navegador) fala cada anúncio com a síntese de voz do navegador, em pt-BR. Usa as vozes do próprio sistema, como Microsoft Maria no Windows e Luciana no macOS, e funciona sem rede (`mapa/voz.ts`). Fala o anúncio e o porquê, mas não o detalhe em mono. Se o navegador não tem voz em português, o interruptor fica desligado e explica por quê. Com a voz ligada, o mapa espera a fala terminar antes do próximo anúncio. Um teto de tempo garante que nada trava se a voz não responder.

**Os modos de pausa** (seletor "Pausas" na barra, guardado no navegador):

| Modo | Quando o mapa espera |
| --- | --- |
| **Só quando precisa de você** (padrão) | Na pergunta à cliente, até a resposta chegar, e no pedágio, até o apresentador mandar seguir. O resto corre com cada anúncio no tempo de leitura |
| **Passo a passo** | Em cada anúncio, até o apresentador mandar seguir ("Seguir" no balão ou no painel, ou as teclas Espaço, Enter e →). A pergunta à cliente espera a resposta |
| **Contínuo** | Nunca espera o apresentador. Cada anúncio fica o tempo de ser lido (de 1,1 s a 7 s, conforme o tamanho), e a pergunta espera a resposta |

O selo mostra "Aguardando o apresentador" ou "Aguardando a resposta da Ana". Trocar de modo com um balão esperando solta o balão, se o novo modo não para ali. "Pular para o fim" fecha o balão, cala a voz e alcança o presente.

**O que fica parado é só o mapa.** O agente segue trabalhando de verdade, então os tempos, os custos e o Raio-X não mudam. O mapa só mostra o próximo evento real quando chega a vez dele. Os testes e os vídeos destes bastidores usam o modo contínuo, e o ensaio de palco usa o passo a passo.

**Por que isso é honesto:**

- nenhum evento é criado e a ordem não muda;
- o mapa só fica alguns segundos **atrás** do agente, e o selo mostra "Reproduzindo · +N eventos" até alcançar e passar a "Ao vivo";
- "Pular para o fim" alcança o presente de uma vez;
- a conversa também segue o diretor: a pergunta à Ana aparece quando o robô chega à parada que a gerou, e a resposta final, com a apólice, quando ele chega à emissão. O agente fica esperando a resposta, então nada trava: a pergunta é o último evento da fila;
- depois de responder, os botões ficam desligados até a próxima pergunta, para não haver resposta dupla.

Abrir um link `/mapa?execucao=<id>` antigo reproduz a viagem inteira desde o início, pelo mesmo caminho.

**A linha do tempo no rodapé** espelha a faixa "As 9 paradas" do infográfico. Cada parada aparece como feita, atual ou pendente, e fica vermelha se um incidente apareceu ali. Acima dela, uma linha de narração diz o passo, por exemplo "Parada 6 · Cotação — chamou seguradoras.cotar_seguro".

**Toda animação é um evento:**

| Evento (SSE) | O que acontece no mapa |
| --- | --- |
| `run.started` | O robô aparece na porta do canal (o app, a agência ou a central) |
| `skill.loaded` | O painel Conversa mostra o navegador, isto é, a skill ativa |
| `step.started` | O robô anda pelas ruas até a placa da parada, e o caminho acende em laranja atrás dele. A placa fica laranja, e a linha do tempo avança. Com "Seguir o agente", a câmera de GPS vai junto |
| `tool.called` | O robô anda até o prédio do sistema chamado, que pulsa (laranja se deu certo, vermelho se falhou), e abre o balão de fala. No passo a passo, o mapa espera o apresentador |
| `incident.detected` | Um aviso vermelho com ícone e a metáfora (Rua interditada, Contramão...), e a parada fica vermelha na linha do tempo |
| `route.recalculated` | Um aviso de recálculo, com o motivo e a regra |
| `human.required` | O pedágio aparece na placa da aprovação |
| `client.asked` / `agent.message` | A pergunta e as opções aparecem no painel Conversa, para responder pela Ana, quando o robô chega à parada |
| `run.finished` | O pino de chegada com o número da apólice, ou o motivo da parada, com duração, custo e modelo. A câmera sobe para a cidade inteira |

**Os modos sem GPS:**

- **Sem contexto,** o agente não chama nenhum sistema, e o robô fica parado na porta do canal.
- **Sem skill,** ele chama os sistemas, então o robô anda de prédio em prédio, mas sem nenhuma placa de parada e sem roteiro. A narração diz "Sem GPS: o agente não planejou rota".

O desenho do caminho é o próprio argumento.

### Modo telão, acessibilidade e desempenho

**Modo telão** (tecla **T**, ou o painel do apresentador; fica guardado no navegador):

- a fonte-base do `html` sobe 25%, e tudo o que é medido em `rem` cresce junto: a barra, os painéis, a linha do tempo, os rótulos e o balão;
- o que é medido em pixels na cena (o pino do robô, as caixas do declutter, o espaço do balão) usa a mesma escala (`telao.ts`);
- o alvo é ler a 5 m num Full HD.

**Acessibilidade:**

- o e2e roda o **axe-core** (WCAG 2.1 AA) na abertura, no mapa, no Raio-X, no status e no painel do apresentador, e falha com qualquer violação séria ou crítica;
- os atalhos de teclado ficam num cartão (tecla `?`);
- com `prefers-reduced-motion`, os voos e o giro da câmera ficam instantâneos, e o balão aparece sem *fade*;
- a Conversa e o Raio-X são regiões com rótulo, e o balão e os avisos usam `aria-live`.

**Desempenho:**

- o relógio da animação (`requestAnimationFrame`) só corre enquanto algo se move: com o balão esperando o apresentador, a página para de re-renderizar;
- a barra de viagem (com os dropdowns do Carbon), a conversa, o Raio-X, a linha do tempo e a legenda são memorizados e não acompanham o relógio;
- `/mapa?fps=1` mostra um medidor: quadros por segundo, pior quadro, rótulos e camadas.

No container, o WebGL é por software: a página fica cerca de 80% ociosa esperando o desenho, e o número de lá só serve para comparar versões. O valor que importa é o do notebook do dia, conferido no checklist do capítulo 9. A fusão das 54 camadas de construções numa malha só foi avaliada e adiada: não houve ganho demonstrável, e ela complicaria o clique em cada construção.

### A tela de abertura: o infográfico navegável

Em `/`, o infográfico oficial (`docs/assets/infografico_horizontal.jpeg`, 2198 × 1446) abre à direita, com zoom e pan do OpenSeadragon. À esquerda, um painel apresenta a demo, a camada de contexto e o impacto medido em precisão e custo. Ele sempre começa aberto e recolhe pela tecla **I**; ao recolher ou mostrar, o infográfico se reenquadra no novo espaço. Os tiles são gerados no build do Docker do `web`, com `vips dzsave`, num estágio Debian.

As 38 áreas clicáveis estão em `services/web/src/abertura/hotspots.json`, em porcentagem da imagem, e acompanham o pan e o zoom. Cada área leva a um de três destinos:

- uma cena do mapa (`/mapa?cena=N`);
- uma parada (`/mapa?parada=N`, que aproxima a câmera da placa da parada);
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

O verificador, citado do repositório. As regras gerais valem para todos os casos; as do caso vêm a seguir:

```python
--8<-- "comum/regras.py:regras"
```

Um caso, por exemplo, a Âncora fora do ar:

```python
--8<-- "comum/regras.py:ancora"
```

### Gravações e replay offline

```
POST /api/gravacoes {execucao, cena, incidentes}  ──► gravacoes/cena-<n>.jsonl (cabeçalho + eventos)
GET  /api/gravacoes                               ──► a lista (cabeçalhos)
GET  /api/gravacoes/<nome>/eventos                ──► SSE no mesmo formato do ao vivo, no ritmo original
GET  /api/gravacoes/<nome>/eventos/lote           ──► a alternativa: a gravação inteira, com as pausas
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
GET /api/execucoes/{id}/eventos       ◄── SSE: o stream desde o início, depois ao vivo
GET /api/execucoes/{id}/eventos/lote  ◄── a alternativa: um lote por consulta (?apos=<id>)
```

O estado de cada execução fica em `bussola:execucoes:<id>`: status, pergunta pendente e métricas.

### Eventos até o navegador: SSE, com alternativa por consulta

**Resumo:** os eventos chegam ao mapa por SSE. Numa rede corporativa, porém, proxies e antivírus com inspeção de HTTPS costumam guardar a resposta inteira antes de entregá-la, e um stream que só termina no fim da viagem nunca chega: a tela abre, mas a viagem não anda. Para isso o mapa tem uma alternativa automática, a consulta por lotes.

- **O SSE continua sendo o caminho principal.** Ele sai com `Cache-Control: no-cache, no-transform` e `X-Accel-Buffering: no`, e começa com um comentário de 2 KB, que alguns filtros exigem antes de repassar qualquer coisa. Clientes SSE ignoram comentários, então o CLI, o smoke e o ensaio não mudam.
- **A troca é automática** (`mapa/viagem.ts`). Se nenhum evento chegar em 4 s, ou se o navegador desistir do SSE (a resposta nem era um stream), o mapa fecha o SSE e segue pela consulta. Numa rede normal o primeiro evento chega na hora, porque o servidor começa do início da execução.
- **A consulta é long-polling.** `GET /api/execucoes/{id}/eventos/lote?apos=<id>` espera até 1,5 s por eventos novos e responde. Cada resposta termina, então passa por qualquer proxy. No replay, `GET /api/gravacoes/<nome>/eventos/lote` devolve a gravação inteira com as pausas, e o navegador toca no ritmo original.
- **Nada se perde nem se repete na troca.** Os ids são os mesmos nos dois caminhos (o id do Redis Stream ao vivo, o índice no replay), e o mapa descarta o que já viu. Toda animação continua correspondendo a um evento real.
- **Fica visível.** Nesse modo, o selo "Eventos por consulta" aparece no mapa, e `.mapa[data-transporte]` diz `sse` ou `consulta`.
- **Dá para forçar.** `?eventos=consulta` na URL pula o SSE (e `?eventos=sse` volta ao normal). A escolha vale para a aba inteira, útil quando já se sabe que a rede do evento segura streams.
- **Testado no navegador** (`e2e/tests/test_rede_corporativa.py`). O Playwright faz o papel do proxy, pendurando a requisição do SSE sem resposta, e a viagem precisa chegar à apólice pela consulta, ao vivo e no replay.
