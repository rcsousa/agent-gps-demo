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
| <http://localhost:8080> | Demo (na Fase 1, o painel de status dos serviços) |
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
docker compose --profile test run --rm smoke
```

### Simular um serviço fora do ar

```bash
docker compose stop risco-mcp    # o tile "Risco" fica vermelho em até 5 s
docker compose start risco-mcp   # e volta ao verde
```

### Criar um novo incidente

Este conteúdo chega na Fase 3, com o `simulator`.

### Escrever uma nova skill

Este conteúdo chega na Fase 4, com o `skills-mcp`.
