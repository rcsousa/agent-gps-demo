#!/usr/bin/env sh
# Recalcula o layout fixo da cidade (ontologia/layout.json) a partir da ontologia.
# Rode depois de adicionar ou remover entidades, e versione o resultado.
set -e

cd "$(dirname "$0")/.."
RAIZ=$(pwd -W 2>/dev/null || pwd)
ONTOLOGIA=/src/services/contexto-mcp/ontologia

docker compose build contexto-mcp
MSYS_NO_PATHCONV=1 docker compose run --rm --no-deps \
  -v "$RAIZ/services/contexto-mcp/ontologia:$ONTOLOGIA" \
  contexto-mcp python -m contexto_mcp.layout
