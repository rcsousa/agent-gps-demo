"""Gera a entrada de um usuário para o AUTH_USUARIOS do .env.

Uso (dentro do container, via ./scripts/criar-usuario.sh <nome>):
    python -m auth.criar_usuario <nome>          # pede a senha duas vezes, sem ecoar
    echo "senha" | python -m auth.criar_usuario <nome> --senha-stdin
"""

import getpass
import sys

from auth.main import NOME_VALIDO
from auth.senhas import gerar_hash

TAMANHO_MINIMO = 10


def main(argumentos: list[str]) -> int:
    if not argumentos or argumentos[0].startswith("-"):
        print(__doc__, file=sys.stderr)
        return 2
    nome = argumentos[0].strip().lower()
    if not NOME_VALIDO.match(nome):
        print("Nome inválido: use letras minúsculas, números, ponto, hífen ou sublinhado.", file=sys.stderr)
        return 2
    if "--senha-stdin" in argumentos:
        senha = sys.stdin.readline().rstrip("\n")
    else:
        senha = getpass.getpass(f"Senha para {nome}: ")
        if getpass.getpass("Repita a senha: ") != senha:
            print("As senhas não conferem.", file=sys.stderr)
            return 1
    if len(senha) < TAMANHO_MINIMO:
        print(f"Use uma senha com pelo menos {TAMANHO_MINIMO} caracteres.", file=sys.stderr)
        return 1
    print(f"{nome}={gerar_hash(senha)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
