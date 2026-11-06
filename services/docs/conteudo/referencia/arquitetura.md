# Arquitetura técnica

!!! abstract "Resumo"
    A demo é um `docker compose` com um único endereço exposto: o `web`, um nginx que exige sessão em tudo, exceto no login. O **agent** é um host MCP que fala com **um** servidor MCP só, o `mcp-gateway`, e com o provedor de LLM. Os serviços de negócio são servidores MCP atrás do gateway, e o grafo de contexto fica no Neo4j, acessado só pelo `contexto-mcp`. Tudo o que acontece vira evento num Redis Stream, e é dele que o mapa e o Raio-X se alimentam.

## Nível 1 · Contexto

Quem usa a demo e do que ela depende fora dela.

![C4 nível 1: a demo, quem a usa e o provedor de LLM](../assets/diagramas/c4-contexto.svg)

- **Só o `agent` sai da rede do compose,** para falar com o provedor de LLM escolhido em `LLM_PROVIDER`: o Microsoft Foundry, a API da Anthropic ou o Azure OpenAI.
- **O resto é interno:** o grafo, o barramento e os servidores MCP.

## Nível 2 · Containers

Cada serviço do compose, a tecnologia, a porta e as rotas que o nginx do `web` publica. As setas verdes são as rotas públicas, sem sessão. As tracejadas são as dependências de subida (`depends_on`).

![C4 nível 2: os containers do compose e as rotas do nginx](../assets/diagramas/c4-containers.svg)

- **Uma porta publicada para a demo** (`WEB_PORT`, o `web`). O Neo4j publica as portas dele só em `127.0.0.1` (`NEO4J_BIND`), para administração por túnel SSH: pela rede, o grafo furaria o login.
- **Login em toda requisição:** o nginx usa `auth_request` contra o serviço `auth`. Só `/entrar/`, `/auth/*` e o favicon passam sem sessão. Os detalhes estão no capítulo 6, em "Login".
- **Ordem de subida:**
  - cada serviço Python tem um healthcheck (`/saude`);
  - o compose só sobe um serviço depois que as dependências dele estão *healthy*;
  - o `seed` roda uma vez a cada subida, recarrega o grafo do zero e termina com `Exited (0)`. O `contexto-mcp` espera por ele.

## Nível 3 · Componentes

Os módulos do `agent`, do `mcp-gateway` e do `contexto-mcp`, com a primeira linha da docstring de cada um. As setas cinza são os imports entre módulos do mesmo serviço, lidos do código. As laranjas são as conexões MCP entre serviços.

![C4 nível 3: os módulos do agent, do gateway e do contexto-mcp](../assets/diagramas/c4-componentes.svg)

## O barramento de eventos

- **Um Redis Stream só,** o `bussola:eventos`, limitado aos 10 mil eventos mais recentes.
- **Quem publica:**
  - o `agent`, sobre a execução:
    - `run.*`, `model.step`, `skill.loaded` e `prompt.loaded`;
    - `route.*` e `step.started`;
    - `client.*` e `agent.message`;
    - `incident.detected` e `human.required`, quando percebe o incidente ou o pedágio no resultado de uma tool;
  - o `mcp-gateway`, sobre o que passa por ele: `tool.called`, `tools.listed`, `skills.listed`, `skill.read`, `resource.read` e `prompt.read`;
  - o `simulator` não publica no barramento das execuções. Ele grava as próprias ações num stream separado (`bussola:simulacao`) e muda o estado vivo do grafo pela rota interna do `contexto-mcp` (`/interno/estado`, com o `SIMULADOR_TOKEN`), e o agente só fica sabendo quando consulta.
- **Todo evento** tem o formato `{tipo, origem, instante, dados}`, e o `execucao_id` vai em `dados`.
- **O navegador recebe os eventos de uma execução por SSE.** Em redes que seguram o stream, recebe por consulta em lotes, com os mesmos ids.
- **O catálogo completo,** com o que cada evento anima no mapa, está no capítulo 6, em "Catálogo de eventos".

## Uma viagem real, chamada por chamada

A sequência abaixo **não foi desenhada**. Ela é gerada da gravação da cena 5, uma execução real com o Claude Haiku 5.5 e com skill.

- Cada linha é um evento do barramento.
- As setas cheias são pedidos, e as tracejadas são respostas e eventos.
- As faixas marcam a skill carregada, a rota planejada e cada parada.

![Sequência da cena 5: a viagem completa, do navegador ao provedor de LLM, ao gateway e aos servidores MCP](../assets/diagramas/sequencia-cena-5.svg)

**Como ler:**

- **O agente decide, o gateway executa.** Cada `passo n` é uma ida ao LLM, que devolve as tools que quer chamar. Toda tool de negócio passa por `tools/call` no gateway, que encaminha ao servidor dono dela, publica `tool.called` e devolve o resultado com a proveniência carimbada.
- **A skill chega por MCP:** `skills/list` e `resources/read` em `skill://…`, servidos pelo `skills-mcp` através do gateway.
- **O prompt de persona também:** `prompts/get canais.atendimento_app`, servido pelo `canais-mcp`.

## Fontes no repositório

| O quê | Onde |
| --- | --- |
| Serviços, portas e dependências | `docker-compose.yml` |
| Rotas públicas e com sessão | `services/web/nginx.conf` |
| Módulos de cada serviço | `services/agent/src/agent/`, `services/mcp-gateway/src/mcp_gateway/` e `services/contexto-mcp/src/contexto_mcp/` |
| Barramento | `libs/bussola_comum/src/bussola_comum/eventos.py` |
| Sequência | `gravacoes/cena-5.jsonl` |
| Gerador | `services/docs/gerar/diagramas_referencia.py` |
