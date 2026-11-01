#!/usr/bin/env sh
# Fala com o simulador: o painel do apresentador, por linha de comando.
# Uso:
#   ./scripts/incidente.sh listar
#   ./scripts/incidente.sh aplicar cotacao-ancora-fora
#   ./scripts/incidente.sh remover cotacao-ancora-fora
#   ./scripts/incidente.sh reset
#   ./scripts/incidente.sh aprovacoes
#   ./scripts/incidente.sh aprovar <ticket>   |   recusar <ticket>
#   ./scripts/incidente.sh tools                 # tools fora do ar
#   ./scripts/incidente.sh desligar seguradoras.cotar_seguro
#   ./scripts/incidente.sh religar seguradoras.cotar_seguro
set -e

cd "$(dirname "$0")/.."
URL=http://localhost:8000

case "$1" in
  listar)     METODO=GET;  CAMINHO=/incidentes ;;
  aplicar)    METODO=POST; CAMINHO="/incidentes/$2/aplicar" ;;
  remover)    METODO=POST; CAMINHO="/incidentes/$2/remover" ;;
  reset)      METODO=POST; CAMINHO=/reset ;;
  aprovacoes) METODO=GET;  CAMINHO=/aprovacoes ;;
  aprovar)    METODO=POST; CAMINHO="/aprovacoes/$2/aprovar" ;;
  recusar)    METODO=POST; CAMINHO="/aprovacoes/$2/recusar" ;;
  tools)      METODO=GET;  CAMINHO=/tools ;;
  desligar)   METODO=POST; CAMINHO="/tools/$2/desligar" ;;
  religar)    METODO=POST; CAMINHO="/tools/$2/religar" ;;
  *) sed -n '2,13p' "$0"; exit 2 ;;
esac

docker compose exec -T simulator python -c "
import json, sys, urllib.request
pedido = urllib.request.Request('$URL$CAMINHO', method='$METODO')
try:
    with urllib.request.urlopen(pedido, timeout=60) as r:
        print(json.dumps(json.load(r), ensure_ascii=False, indent=2))
except urllib.error.HTTPError as erro:
    print(erro.read().decode(), file=sys.stderr); sys.exit(1)
"
