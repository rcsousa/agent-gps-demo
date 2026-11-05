"""Sessão num cookie assinado (HMAC-SHA256), sem estado no servidor.

Token: <usuario em base64url>.<expira em epoch>.<nonce>.<assinatura>. Quem não tem o
AUTH_SEGREDO não consegue forjar nem estender uma sessão. Trocar o segredo derruba todas.
"""

import base64
import hashlib
import hmac
import secrets
import time

NOME_DO_COOKIE = "bussola_sessao"


def _b64(dados: bytes) -> str:
    return base64.urlsafe_b64encode(dados).decode().rstrip("=")


def _de_b64(texto: str) -> bytes:
    return base64.urlsafe_b64decode(texto + "=" * (-len(texto) % 4))


def _assinar(segredo: str, corpo: str) -> str:
    return _b64(hmac.new(segredo.encode(), corpo.encode(), hashlib.sha256).digest())


def emitir(segredo: str, usuario: str, duracao_s: int, agora: float | None = None) -> str:
    expira = int((agora if agora is not None else time.time()) + duracao_s)
    corpo = f"{_b64(usuario.encode())}.{expira}.{secrets.token_urlsafe(8)}"
    return f"{corpo}.{_assinar(segredo, corpo)}"


def validar(segredo: str, token: str | None, agora: float | None = None) -> str | None:
    """O usuário da sessão, ou None se o token for inválido, adulterado ou vencido."""
    if not token:
        return None
    try:
        usuario_b64, expira, nonce, assinatura = token.split(".")
        corpo = f"{usuario_b64}.{expira}.{nonce}"
        if not hmac.compare_digest(assinatura, _assinar(segredo, corpo)):
            return None
        if int(expira) < (agora if agora is not None else time.time()):
            return None
        return _de_b64(usuario_b64).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return None
