"""Contrato da rota /saude, igual em todos os serviços.

Resposta: {"servico", "status", "versao", "dependencias"}.
status é "ok" quando todas as dependências estão ok; caso contrário "fora",
com HTTP 503, para que o healthcheck do Docker reflita o estado real.
"""

from collections.abc import Awaitable, Callable

from starlette.requests import Request
from starlette.responses import JSONResponse

from bussola_comum import VERSAO

# Cada checagem devolve True (ok) ou False (fora) e não deve lançar exceção.
Checagem = Callable[[], Awaitable[bool]]


async def avaliar_saude(servico: str, checagens: dict[str, Checagem] | None = None) -> tuple[dict, int]:
    dependencias = {}
    for nome, checar in (checagens or {}).items():
        try:
            dependencias[nome] = "ok" if await checar() else "fora"
        except Exception:
            dependencias[nome] = "fora"
    saudavel = all(v == "ok" for v in dependencias.values())
    corpo = {
        "servico": servico,
        "status": "ok" if saudavel else "fora",
        "versao": VERSAO,
        "dependencias": dependencias,
    }
    return corpo, 200 if saudavel else 503


def rota_saude(servico: str, checagens: dict[str, Checagem] | None = None):
    """Endpoint Starlette/FastAPI para /saude."""

    async def saude(request: Request) -> JSONResponse:
        corpo, codigo = await avaliar_saude(servico, checagens)
        return JSONResponse(corpo, status_code=codigo)

    return saude
