#!/usr/bin/env sh
# Cria um usuário da demo: pede a senha (sem ecoar) e imprime a entrada para o AUTH_USUARIOS do .env.
# Uso:
#   ./scripts/criar-usuario.sh ana                       # pede a senha duas vezes
#   echo "senha-longa" | ./scripts/criar-usuario.sh ana --senha-stdin
# Depois: cole a linha em AUTH_USUARIOS (vários usuários separados por vírgula)
# e rode docker compose up -d auth para valer.
set -e

cd "$(dirname "$0")/.."
docker compose run --rm --no-deps --build auth python -m auth.criar_usuario "$@"
