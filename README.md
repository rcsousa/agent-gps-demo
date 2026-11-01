# Demo GPS de Contexto · Banco Bússola

> Agentes que chegam mais longe, porque entendem o caminho.

Esta demo mostra por que agentes de IA precisam de uma **camada de contexto** (o mapa) e de **skills** (o GPS) para navegar com segurança numa jornada bancária: a contratação de um seguro residencial.

A especificação completa está em [`docs/spec.md`](docs/spec.md).

## Subir a demo

Pré-requisito: Docker com Compose v2. Nada é instalado fora dos containers.

```bash
cp .env.example .env          # ajuste senhas e chaves
docker compose up -d --build
docker compose ps             # todos os serviços "healthy"
```

| Endereço | O que é |
| --- | --- |
| <http://localhost:8080/status> | Dashboard de status: serviços, tools, skills e prompts por dentro |
| <http://localhost:8080/bastidores/> | Bastidores (documentação) |
| <http://localhost:7474> | Neo4j Browser |

## Testes

```bash
./scripts/testar.sh                           # lint e testes de unidade de todos os serviços
docker compose --profile test run --rm --build smoke  # ponta a ponta, com a demo no ar
```

Dependências Python ficam travadas num `uv.lock` por serviço. Depois de mudar um `pyproject.toml`, rode `./scripts/travar-dependencias.sh <serviço>`.

## Explorar a demo

```bash
./scripts/gateway.sh --listar                          # as tools que o agente enxerga
./scripts/gateway.sh --skills                          # as skills (SEP-2640), com digests
./scripts/gateway.sh contexto.consultar_rota           # rotas com estimativas do trânsito atual
./scripts/incidente.sh aplicar cotacao-ancora-fora     # o apresentador derruba uma API
./scripts/incidente.sh reset                           # tudo volta ao estado-base
```

## Dirigir o agente

Sem chave de API, o provedor `roteiro` faz um ensaio determinístico pelas mesmas tools:

```bash
./scripts/agente.sh executar --modo com_skill --provedor roteiro   # a viagem ao vivo no terminal
./scripts/agente.sh responder <id> --sugestao 1                    # o apresentador responde pela Ana
./scripts/agente.sh executar --modo sem_skill --provedor roteiro --auto
./scripts/agente.sh executar --modo com_skill --provedor roteiro --canal agencia --auto
```

Modos: `sem_contexto`, `sem_skill` e `com_skill`. Canais: `app` (padrão), `agencia` e `central`. Com `ANTHROPIC_API_KEY` (ou as `AZURE_OPENAI_*`) no `.env`, rode sem `--provedor`.

## Estrutura

```
docker-compose.yml              todos os serviços
docker/python-service.Dockerfile imagem única dos serviços Python
libs/bussola_comum/             config, logs, rota /saude e fábrica de servidores MCP
services/
  agent/                        host MCP (fala só com o gateway); provedores de LLM em src/agent/llm/
  mcp-gateway/                  ponto único de acesso MCP; upstreams em config/upstreams.yaml
  skills-mcp/ contexto-mcp/ cliente-mcp/ consentimento-mcp/
  risco-mcp/ seguradoras-mcp/ pagamentos-mcp/ atendimento-mcp/
  canais-mcp/                   persona do agente por canal (prompts MCP em prompts/*.md)
  simulator/                    injeta incidentes (fora do alcance do agente)
  smoke/                        checagem ponta a ponta (perfil test)
  web/                          React + Carbon, servido por nginx
  docs/                         site de bastidores (MkDocs Material)
docs/                           spec e infográfico
```

## Fases

O desenvolvimento segue as fases da spec. Fase atual: **5.2 · Dashboard de status**.
