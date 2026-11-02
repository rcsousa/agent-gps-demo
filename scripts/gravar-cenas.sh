#!/usr/bin/env sh
# Grava as cenas da demo com o modelo real, para o replay offline. Gasta tokens de verdade
# (com o Haiku, cerca de US$ 0,06 as cinco cenas). As gravações vão para gravacoes/.
# Uso: ./scripts/gravar-cenas.sh [cena ...]          # padrão: 2 3 5 6 7
#      MODELO=claude-opus-5-5 ./scripts/gravar-cenas.sh 5
set -e

cd "$(dirname "$0")/.."
docker compose --profile test run --rm --no-deps --build -T -e MODELO="${MODELO:-claude-haiku-5-5}"   smoke python -m smoke.gravar_cenas "$@"
