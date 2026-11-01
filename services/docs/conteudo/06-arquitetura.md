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
- Os nomes ganham o prefixo do servidor: `obter_perfil` do `cliente-mcp` vira `cliente.obter_perfil`. São 38 tools ao todo.
- As tools `ping` dos servidores ficam de fora.
- Se um servidor cai, as tools dele continuam no catálogo, e a chamada devolve "trecho interditado". A rua continua no mapa; só fica bloqueada.
- Resources são roteados pelo esquema da URI (`contexto://mapa` → `contexto-mcp`).

Cerca de 15 dessas tools são **de distração**: plausíveis, às vezes perigosas, fora da jornada (`pagamentos.estornar`, `seguradoras.cancelar_apolice`, `consentimento.revogar`...). Elas existem para a cena 3 mostrar o que acontece quando o agente tem o mapa, mas não tem GPS.

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

`graph` → `seed` (termina) → `contexto-mcp` · (`bus` + os 8 servidores MCP) → `mcp-gateway` → `agent` → `web` (junto com `docs`). O `simulator` sobe depois do `contexto-mcp`.

### Como trocar o provedor de LLM

Mude `LLM_PROVIDER` no `.env` para `anthropic` ou `azure_openai` e preencha as variáveis do provedor escolhido. A interface única do agente chega na Fase 5; na Fase 1 o agente já lê a variável e mostra no painel de status se a chave está configurada.
