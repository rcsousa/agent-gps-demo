#!/usr/bin/env sh
# Gera ou atualiza o uv.lock de cada serviço Python, dentro de um container.
# Uso:
#   ./scripts/travar-dependencias.sh                  # todos os serviços
#   ./scripts/travar-dependencias.sh agent            # só um serviço
#   ./scripts/travar-dependencias.sh --upgrade        # sobe as versões dentro das faixas do pyproject
#   ./scripts/travar-dependencias.sh --check          # só confere se os locks estão em dia
set -e

cd "$(dirname "$0")/.."

OPCOES=""
SERVICOS=""
for arg in "$@"; do
  case "$arg" in
    --*) OPCOES="$OPCOES $arg" ;;
    *) SERVICOS="$SERVICOS $arg" ;;
  esac
done

if [ -z "$SERVICOS" ]; then
  SERVICOS=$(for f in services/*/pyproject.toml; do basename "$(dirname "$f")"; done)
fi

# pwd -W dá o caminho Windows no Git Bash; em Linux/macOS cai no pwd normal.
RAIZ=$(pwd -W 2>/dev/null || pwd)

for s in $SERVICOS; do
  echo "== $s"
  MSYS_NO_PATHCONV=1 docker run --rm -v "$RAIZ:/src" -w "/src/services/$s" \
    -e UV_NO_CACHE=1 ghcr.io/astral-sh/uv:0.9-python3.12-trixie-slim uv lock $OPCOES
done
