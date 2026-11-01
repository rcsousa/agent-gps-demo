# 7. Como reproduzir

!!! abstract "Resumo executivo"
    Você só precisa do Docker. Copie o arquivo de configuração, rode um comando e abra o navegador. Nada é instalado fora dos containers.

## Aprofundamento técnico

### Subir a demo

```bash
cp .env.example .env        # preencha as chaves se for usar o LLM
docker compose up -d --build
docker compose ps           # todos os serviços devem aparecer como "healthy"
```

| Endereço | O que é |
| --- | --- |
| <http://localhost:8080> | Demo (por enquanto, o painel de status dos serviços) |
| <http://localhost:8080/bastidores/> | Este site |
| <http://localhost:7474> | Neo4j Browser (usuário e senha do `.env`) |

### Rodar os testes

Os testes rodam dentro dos containers:

```bash
# Testes de um serviço
docker compose run --rm --no-deps agent pytest

# Todos os testes de unidade e o lint
./scripts/testar.sh

# Checagem ponta a ponta, com a demo no ar
docker compose --profile test run --rm --build smoke
```

### Atualizar dependências

Cada serviço Python tem um `uv.lock` versionado, e o build usa `uv sync --locked`. Na prática, duas máquinas instalam exatamente as mesmas versões. Se alguém mudar um `pyproject.toml` e esquecer o lock, o build falha logo, em vez de instalar versões diferentes sem aviso.

```bash
# Depois de mudar um pyproject.toml
./scripts/travar-dependencias.sh agent        # só o serviço alterado
./scripts/travar-dependencias.sh              # todos

# Para subir as versões dentro das faixas permitidas
./scripts/travar-dependencias.sh --upgrade
```

O script roda o `uv` dentro de um container, então não é preciso instalar nada na máquina.

### Chamar tools como o agente

Com a demo no ar, `gateway.sh` chama qualquer tool pelo MCP gateway, com o mesmo caminho e o mesmo token do agente. A resposta mostra o `_meta` com a proveniência:

```bash
./scripts/gateway.sh --listar                                  # as 38 tools
./scripts/gateway.sh cliente.obter_perfil '{"cliente_id": "cliente-ana"}'
./scripts/gateway.sh seguradoras.cotar_seguro '{"cliente_id": "cliente-ana", "seguradora": "farol"}'
./scripts/gateway.sh contexto.consultar_rota
./scripts/gateway.sh contexto://mapa
```

Para ver as chamadas no barramento:

```bash
docker compose exec bus redis-cli XREVRANGE bussola:eventos + - COUNT 5
```

No Neo4j Browser, a vizinhança da Ana:

```cypher
MATCH p=(:Cliente {id:'cliente-ana'})-[*1..2]-() RETURN p
```

### Mudar a ontologia

1. Edite os arquivos em `services/contexto-mcp/ontologia/`.
2. Se adicionou ou removeu entidades, recalcule o layout da cidade: `./scripts/gerar-layout.sh`.
3. Versione `ontologia/layout.json` junto. O seed se recusa a subir com layout desatualizado, e um teste também acusa.
4. `docker compose up -d --build`: o `seed` recarrega o grafo.

### Simular um serviço fora do ar

```bash
docker compose stop risco-mcp    # o tile "Risco" fica vermelho em até 5 s
docker compose start risco-mcp   # e volta ao verde
```

### Aplicar incidentes

`incidente.sh` é o painel do apresentador por linha de comando:

```bash
./scripts/incidente.sh listar
./scripts/incidente.sh aplicar cotacao-ancora-fora     # rua interditada
./scripts/gateway.sh contexto.consultar_rota            # a rota rápida aparece bloqueada
./scripts/incidente.sh remover cotacao-ancora-fora
./scripts/incidente.sh reset                           # tudo volta ao estado-base
```

No pedágio (`alcada-ana-excedida`), a proposta exige um especialista. Depois de `atendimento.solicitar_aprovacao`, decida com `./scripts/incidente.sh aprovar <ticket>` (ou `recusar`). Se ninguém decidir em 30 s, a especialista Marina aprova.

| Incidente | Metáfora |
| --- | --- |
| `cotacao-ancora-fora` | Rua interditada |
| `emissao-lenta` | Congestionamento |
| `consentimento-ana-expirado` | Contramão |
| `vistoria-zona-sul` | Desvio por obra |
| `alcada-ana-excedida` | Pedágio |
| `proveniencia-fraca-ana` | Ponte interditada |

### Criar um novo incidente

Acrescente uma entrada em `services/simulator/incidentes.yaml`. Cada efeito aponta para uma entidade da ontologia, pelo id, e muda:

- `estado`: `status`, `latencia_ms`, `custo_estimado`, `vigencia_fim`;
- `atributos` ou `proveniencia`;
- relações (`relacoes_adicionar`).

Datas podem ser relativas (`$hoje`, `$ontem`). Depois de `docker compose up -d --build simulator`, o incidente aparece em `incidente.sh listar`. O smoke aplica todos os incidentes do catálogo ao mapa real, para garantir que nenhum aponta para entidade inexistente.

### Escrever uma nova skill

Este conteúdo chega na Fase 4, com o `skills-mcp`.
