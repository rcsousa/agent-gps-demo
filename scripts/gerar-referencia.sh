#!/usr/bin/env sh
# Regrava o catálogo do gateway (tools, prompts e skills) usado pela referência técnica dos bastidores.
# Rode com a demo no ar, sempre que uma tool, um prompt ou uma skill mudar: o smoke confere que o
# arquivo versionado (services/smoke/referencia/catalogo.json) é igual ao gateway vivo.
set -e

cd "$(dirname "$0")/.."
mkdir -p services/smoke/referencia
# No Git Bash (Windows), o caminho do volume precisa ir no formato do Windows e sem conversão automática.
ORIGEM="$(pwd -W 2>/dev/null || pwd)/services/smoke/referencia"
MSYS_NO_PATHCONV=1 docker compose --profile test run --rm --no-deps --build -T -v "$ORIGEM:/saida" \
  smoke python -m smoke.referencia /saida/catalogo.json
