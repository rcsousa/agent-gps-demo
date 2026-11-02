#!/usr/bin/env sh
# Ensaio de palco: sobe a demo do zero (mede o tempo), toca as 8 cenas no navegador pelo roteiro,
# com o passo a passo ligado, e os replays; confere os critérios de aceite e escreve o relatório em
# ensaios/<data>.md (com as capturas em ensaios/<data>/). Não gasta tokens.
# Uso: ./scripts/ensaiar.sh            # com a subida a frio (docker compose down/up)
#      ./scripts/ensaiar.sh --quente   # com a demo já no ar
set -e

cd "$(dirname "$0")/.."
mkdir -p ensaios
SUBIDA=""
if [ "$1" != "--quente" ]; then
  docker compose down
  INICIO=$(date +%s)
  docker compose up -d
  # Espera todos os serviços que ficam no ar estarem saudáveis (o seed termina e sai).
  until [ -z "$(docker compose ps --format '{{.Service}} {{.Health}}' | grep -v ' healthy$')" ]; do
    [ $(( $(date +%s) - INICIO )) -gt 600 ] && { echo "a demo não ficou saudável em 10 min"; docker compose ps; exit 1; }
    sleep 2
  done
  SUBIDA=$(( $(date +%s) - INICIO ))
  echo "subida a frio: ${SUBIDA} s"
fi
DESTINO="$(pwd -W 2>/dev/null || pwd)/ensaios"
MSYS_NO_PATHCONV=1 docker compose --profile test run --rm --no-deps --build -T -e SUBIDA_S="$SUBIDA" \
  -v "$DESTINO:/saida" e2e python ensaio.py
