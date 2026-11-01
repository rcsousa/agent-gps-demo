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
 │                    │          └─► atendimento-mcp
 │                    ▼
 │                   bus (Redis Streams) ◄── agent, simulator
 └─► /bastidores ──► docs

simulator ──► graph e servidores de domínio (fora do alcance do agente)
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
| `graph` | Ontologia, instâncias e estado vivo | Neo4j 5 Community |
| `bus` | Barramento de eventos | Redis 7 (Streams) |
| `simulator` | Injeta incidentes e trânsito | Python, FastAPI |

### Decisões da Fase 1

**Barramento de eventos em Redis Streams.** A spec pede um barramento para os eventos `route.planned`, `step.started`, `tool.called`, `incident.detected`, `route.recalculated` e `human.required`, mas não fixava a tecnologia. Escolhemos Redis Streams, que é leve e guarda o histórico em ordem. Esse histórico serve de base para o replay offline e para o Raio-X provar que cada animação corresponde a um evento real.

**SDK MCP oficial v2.** Os servidores usam `MCPServer` (o antigo FastMCP) com transporte *streamable HTTP* em `/mcp`, em modo *stateless*.

**Saúde padronizada.** Todo serviço Python responde `GET /saude` com `{servico, status, versao, dependencias}`. Se uma dependência cai, a resposta vira HTTP 503, e o healthcheck do Docker passa a mostrar o problema. O `contexto-mcp`, por exemplo, só fica saudável quando o Neo4j responde.

**Upstreams por configuração.** A lista de servidores atrás do gateway fica em `services/mcp-gateway/config/upstreams.yaml`. Trocar, adicionar ou desligar um servidor não exige mudar o agente.

### Ordem de subida

Os `depends_on` usam `condition: service_healthy`:

`graph` → `contexto-mcp` · (`bus` + os 8 servidores MCP) → `mcp-gateway` → `agent` → `web` (junto com `docs`).

### Como trocar o provedor de LLM

Mude `LLM_PROVIDER` no `.env` para `anthropic` ou `azure_openai` e preencha as variáveis do provedor escolhido. A interface única do agente chega na Fase 5; na Fase 1 o agente já lê a variável e mostra no painel de status se a chave está configurada.
