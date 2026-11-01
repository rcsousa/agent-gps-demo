#!/usr/bin/env sh
# Chama qualquer tool pelo MCP gateway, como o agente faria, e mostra a resposta real
# com a proveniência carimbada pelo gateway (_meta).
# Exemplos:
#   ./scripts/gateway.sh --listar
#   ./scripts/gateway.sh cliente.obter_perfil '{"cliente_id": "cliente-ana"}'
#   ./scripts/gateway.sh seguradoras.cotar_seguro '{"cliente_id": "cliente-ana", "seguradora": "farol"}'
#   ./scripts/gateway.sh contexto.consultar_rota
#   ./scripts/gateway.sh contexto://mapa
set -e

cd "$(dirname "$0")/.."
docker compose --profile test run --rm --no-deps --build -T smoke python -m smoke.gateway "$@"
