#!/usr/bin/env sh
# Capturas e vídeos de cada cena para os bastidores, a partir das gravações (replay): não gasta tokens.
# Precisa da demo no ar. Saída: services/docs/conteudo/assets/cenas/.
# Uso: ./scripts/capturar-cenas.sh [cena ...]          # padrão: todas
set -e

cd "$(dirname "$0")/.."
DESTINO="$(pwd -W 2>/dev/null || pwd)/services/docs/conteudo/assets/cenas"
mkdir -p services/docs/conteudo/assets/cenas
MSYS_NO_PATHCONV=1 docker compose --profile test run --rm --no-deps --build -T -v "$DESTINO:/saida"   e2e python capturas.py "$@"
