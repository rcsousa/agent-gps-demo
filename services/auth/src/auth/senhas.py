"""Senhas com scrypt (biblioteca padrão), num formato que cabe no .env sem escapar nada.

Formato: scrypt.<n>.<r>.<p>.<sal>.<hash>, com sal e hash em base64url sem "=". Sem "$" (que o
Compose interpretaria no .env), sem "," e sem "=" (que separam os usuários em AUTH_USUARIOS).
"""

import base64
import hashlib
import hmac
import secrets

N, R, P = 2**14, 8, 1
TAMANHO_DO_HASH = 32
_PREFIXO = "scrypt"


def _b64(dados: bytes) -> str:
    return base64.urlsafe_b64encode(dados).decode().rstrip("=")


def _de_b64(texto: str) -> bytes:
    return base64.urlsafe_b64decode(texto + "=" * (-len(texto) % 4))


def _derivar(senha: str, sal: bytes, n: int, r: int, p: int) -> bytes:
    return hashlib.scrypt(
        senha.encode("utf-8"), salt=sal, n=n, r=r, p=p, dklen=TAMANHO_DO_HASH, maxmem=128 * n * r * 2
    )


def gerar_hash(senha: str) -> str:
    sal = secrets.token_bytes(16)
    return ".".join([_PREFIXO, str(N), str(R), str(P), _b64(sal), _b64(_derivar(senha, sal, N, R, P))])


def conferir(senha: str, guardado: str) -> bool:
    """Compara em tempo constante. Um hash malformado nunca confere."""
    try:
        prefixo, n, r, p, sal, esperado = guardado.split(".")
        if prefixo != _PREFIXO:
            return False
        calculado = _derivar(senha, _de_b64(sal), int(n), int(r), int(p))
        return hmac.compare_digest(calculado, _de_b64(esperado))
    except (ValueError, TypeError):
        return False


# Para um usuário que não existe, gasta o mesmo tempo que uma senha errada:
# quem tenta não descobre, pelo tempo de resposta, quais nomes existem.
HASH_FICTICIO = gerar_hash(secrets.token_urlsafe(16))
