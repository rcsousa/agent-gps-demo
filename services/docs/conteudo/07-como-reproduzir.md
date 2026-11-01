# 7. Como reproduzir

!!! abstract "Resumo executivo"
    Você só precisa do Docker. Copie o arquivo de configuração, rode um comando e abra o navegador. Nada é instalado fora dos containers.

## Aprofundamento técnico

### Subir a demo

```bash
cp .env.example .env        # preencha as chaves se for usar um LLM de verdade
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

### Desligar uma tool

Além dos incidentes, dá para criar falhas sob medida, tool a tool. No painel de status (<http://localhost:8080>), a seção **Tools por servidor** mostra:

- o que cada servidor MCP oferece;
- o nome com que cada tool aparece no gateway;
- o que fica oculto, como as tools `ping`.

O toggle de cada linha desliga ou religa a tool. **"Religar todas"** volta tudo ao normal.

Uma tool desligada **continua visível** para o agente, mas toda chamada falha com "trecho interditado". É a falha que o agente precisa perceber e contornar. O controle passa pelo simulador, pelo caminho `/simulador` do web; o agente não o alcança.

Pela linha de comando:

```bash
./scripts/incidente.sh desligar seguradoras.cotar_seguro
./scripts/incidente.sh tools                       # o que está fora do ar
./scripts/incidente.sh religar seguradoras.cotar_seguro
```

`incidente.sh reset` também religa todas as tools.

### Criar um novo incidente

Acrescente uma entrada em `services/simulator/incidentes.yaml`. Cada efeito aponta para uma entidade da ontologia, pelo id, e muda:

- `estado`: `status`, `latencia_ms`, `custo_estimado`, `vigencia_fim`;
- `atributos` ou `proveniencia`;
- relações (`relacoes_adicionar`).

Datas podem ser relativas (`$hoje`, `$ontem`). Depois de `docker compose up -d --build simulator`, o incidente aparece em `incidente.sh listar`. O smoke aplica todos os incidentes do catálogo ao mapa real, para garantir que nenhum aponta para entidade inexistente.

### Escrever uma nova skill

1. Crie `services/skills-mcp/skills/<nome>/SKILL.md`. O frontmatter precisa de `name` igual ao nome da pasta, de `description` (o que a skill faz e quando usar) e de `allowed-tools` com os nomes qualificados do gateway (`cliente.obter_perfil`...).
2. Se reutilizar outras skills, liste-as em `metadata.usa-skills` e aponte para elas pela URI (`skill://<nome>/SKILL.md`).
3. Coloque os trechos longos em `references/*.md` e cite cada um pela URI completa no `SKILL.md`.
4. `docker compose up -d --build skills-mcp`. Em até 30 s o gateway relê o catálogo, e `./scripts/gateway.sh --skills` mostra a skill nova.

Os testes recusam:

- skill com `name` diferente da pasta;
- tool fora do formato `prefixo.tool`;
- `usa-skills` que não existe;
- arquivo de apoio citado e ausente, ou presente e não citado.

O smoke confere que toda tool permitida existe no gateway.

Para testar a governança: `./scripts/gateway.sh <tool> '{...}' --skill <nome>`.

### Dirigir o agente

`agente.sh` inicia uma execução e mostra a viagem no terminal, evento a evento. Sem chave de API, use o provedor `roteiro`:

```bash
./scripts/agente.sh executar --modo com_skill --provedor roteiro
```

Quando o agente pergunta algo à Ana, a execução pausa e o terminal mostra as opções sugeridas. Responda de outro terminal:

```bash
./scripts/agente.sh responder <id> --sugestao 1               # a primeira opção sugerida
./scripts/agente.sh responder <id> "Sim, é esse apartamento"  # texto livre
./scripts/agente.sh estado <id>                               # status, pergunta pendente e métricas
```

Para ensaiar sem apresentador, `--auto` responde sempre com a primeira opção. Os três modos:

```bash
./scripts/agente.sh executar --modo sem_contexto --provedor roteiro --auto   # zero tools, resposta inventada
./scripts/agente.sh executar --modo sem_skill    --provedor roteiro --auto   # tools irrelevantes
./scripts/agente.sh executar --modo com_skill    --provedor roteiro --auto   # as 9 paradas até a apólice
```

Com um incidente aplicado antes ou durante a viagem, o agente percebe e recalcula:

```bash
./scripts/incidente.sh aplicar cotacao-ancora-fora
./scripts/agente.sh executar --modo com_skill --provedor roteiro --auto
#   ⚠ incidente: Rua interditada · A API de cotação da Âncora Seguros está fora do ar...
# ◆ rota recalculada: rota-rapida → rota-economica · ...
```

Com `ANTHROPIC_API_KEY` (ou as `AZURE_OPENAI_*`) no `.env`, rode sem `--provedor`: vale o `LLM_PROVIDER`. Depois de mudar o `.env`, recrie o agente com `docker compose up -d agent`.

Pela API, o mesmo caminho que o painel do apresentador vai usar:

```bash
curl -s -X POST localhost:8080/api/execucoes -H 'Content-Type: application/json' \
  -d '{"modo": "com_skill", "provedor": "roteiro"}'
curl -N localhost:8080/api/execucoes/<id>/eventos          # SSE
curl -s -X POST localhost:8080/api/execucoes/<id>/resposta -H 'Content-Type: application/json' \
  -d '{"texto": "Aceito"}'
```
