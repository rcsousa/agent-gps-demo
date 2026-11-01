#!/usr/bin/env sh
# Chama uma tool do contexto-mcp na demo em execução e mostra a resposta real.
# Exemplos:
#   ./scripts/contexto.sh consultar_entidade '{"id": "cliente-ana"}'
#   ./scripts/contexto.sh consultar_rota '{"rota": "rota-rapida"}'
#   ./scripts/contexto.sh consultar_regras '{"id": "produto-residencial-farol"}'
#   ./scripts/contexto.sh contexto://mapa
set -e

cd "$(dirname "$0")/.."
docker compose --profile test run --rm --no-deps --build -T smoke python -m smoke.contexto "$@"
