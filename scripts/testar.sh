#!/usr/bin/env sh
# Roda lint e testes de unidade de todos os serviços Python, dentro dos containers.
# Uso: ./scripts/testar.sh
set -e

SERVICOS="agent mcp-gateway skills-mcp contexto-mcp cliente-mcp consentimento-mcp risco-mcp seguradoras-mcp pagamentos-mcp atendimento-mcp simulator"

docker compose build $SERVICOS

for s in $SERVICOS; do
  echo "== $s"
  docker compose run --rm --no-deps "$s" sh -c "ruff check . && pytest -q"
done

echo "== web (typecheck)"
docker compose build web

echo "Tudo certo."
