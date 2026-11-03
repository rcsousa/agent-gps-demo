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
| <http://localhost:8080> | Tela de abertura: o infográfico navegável |
| <http://localhost:8080/mapa> | Modo Mapa: a cidade do banco e a viagem do agente (tecla P: painel do apresentador) |
| <http://localhost:8080/mapa?visao=raio-x> | Modo Raio-X: a mesma viagem por dentro, com o placar |
| <http://localhost:8080/mapa?eventos=consulta> | Modo Mapa sem SSE: para redes corporativas cujo proxy segura o stream (o mapa também troca sozinho, se nada chegar em 4 s) |
| <http://localhost:8080/status> | Dashboard de status: serviços, tools, skills e prompts por dentro |
| <http://localhost:8080/bastidores/> | Bastidores (documentação) |
| <http://localhost:7474> | Neo4j Browser |

## Testes

```bash
./scripts/testar.sh                           # lint e testes de unidade de todos os serviços
docker compose --profile test run --rm --build smoke  # ponta a ponta, com a demo no ar
docker compose --profile test run --rm --build e2e    # no navegador (roteiro, sem tokens)
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

O modelo padrão é o Claude Haiku 5.5. O Opus 5.5 pode ser escolhido no seletor do painel (`/status`) ou na barra de viagem do mapa. Cada execução mostra o custo em US$.

Para medir com o modelo real (gasta tokens): `./scripts/experimento.sh rodar [--modelo claude-haiku-5-5] [--repeticoes 3]`, depois `comparar`. Relatórios em [`docs/experimentos/`](docs/experimentos/).

Modos: `sem_contexto`, `sem_skill` e `com_skill`. Canais: `app` (padrão), `agencia` e `central`. Com o modelo configurado no `.env` (padrão: Claude Opus 5.5 no Microsoft Foundry, com `ANTHROPIC_FOUNDRY_BASE_URL` e `ANTHROPIC_FOUNDRY_API_KEY`), rode sem `--provedor`.

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
  e2e/                          testes no navegador com Playwright (perfil test)
gravacoes/                      viagens reais gravadas, para o replay offline das cenas
  web/                          React + Carbon + deck.gl, servido por nginx (abertura, mapa, status)
  docs/                         site de bastidores (MkDocs Material)
docs/                           spec e infográfico
```

## Fases

O desenvolvimento segue as fases da spec. Fase atual: **8 · Bastidores**.
