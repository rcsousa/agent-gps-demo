#!/usr/bin/env sh
# Dirige o agente e acompanha a viagem ao vivo (eventos do barramento via SSE).
# Exemplos:
#   ./scripts/agente.sh executar --modo com_skill --provedor roteiro    # ensaio sem chave
#   ./scripts/agente.sh executar --modo sem_skill                       # provedor do .env
#   ./scripts/agente.sh executar --modo com_skill --canal agencia       # persona do canal (app, agencia, central)
#   ./scripts/agente.sh responder <id> --sugestao 1                     # o apresentador responde pela Ana
#   ./scripts/agente.sh responder <id> "Sim, é esse apartamento"
#   ./scripts/agente.sh estado <id>
# Modos: sem_contexto | sem_skill | com_skill. --auto responde com a primeira sugestão.
set -e

cd "$(dirname "$0")/.."
docker compose --profile test run --rm --no-deps --build -T smoke python -m smoke.agente "$@"
