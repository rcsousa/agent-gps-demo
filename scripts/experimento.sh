#!/usr/bin/env sh
# Experimento com o modelo real: sem_skill x com_skill em cada incidente.
# Gasta tokens de verdade (o modelo do .env). Os eventos ficam em experimentos/<data>/.
# Exemplos:
#   ./scripts/experimento.sh rodar                         # os 5 incidentes, nos dois modos
#   ./scripts/experimento.sh rodar vistoria-zona-sul       # só um incidente
#   ./scripts/experimento.sh analisar 2026-11-01           # regras cumpridas, por modo
set -e

cd "$(dirname "$0")/.."
mkdir -p experimentos
# No Git Bash (Windows), o caminho do volume precisa ir no formato do Windows e sem conversão automática.
ORIGEM="$(pwd -W 2>/dev/null || pwd)/experimentos"
MSYS_NO_PATHCONV=1 docker compose --profile test run --rm --no-deps --build -T -v "$ORIGEM:/saida" smoke python -m smoke.experimento "$@"
