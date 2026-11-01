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
| <http://localhost:8080> | Demo |
| <http://localhost:8080/bastidores/> | Bastidores (documentação) |
| <http://localhost:7474> | Neo4j Browser |

## Testes

```bash
./scripts/testar.sh                           # lint e testes de unidade de todos os serviços
docker compose --profile test run --rm smoke  # ponta a ponta, com a demo no ar
```

## Estrutura

```
docker-compose.yml              todos os serviços
docker/python-service.Dockerfile imagem única dos serviços Python
libs/bussola_comum/             config, logs, rota /saude e fábrica de servidores MCP
services/
  agent/                        host MCP (fala só com o gateway)
  mcp-gateway/                  ponto único de acesso MCP; upstreams em config/upstreams.yaml
  skills-mcp/ contexto-mcp/ cliente-mcp/ consentimento-mcp/
  risco-mcp/ seguradoras-mcp/ pagamentos-mcp/ atendimento-mcp/
  simulator/                    injeta incidentes (fora do alcance do agente)
  smoke/                        checagem ponta a ponta (perfil test)
  web/                          React + Carbon, servido por nginx
  docs/                         site de bastidores (MkDocs Material)
docs/                           spec e infográfico
```

## Fases

O desenvolvimento segue as fases da spec. Fase atual: **1 · Fundação**.
