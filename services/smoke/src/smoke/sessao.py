"""Sessão para o smoke, o experimento e o CLI do agente passarem pelo web já logados.

Pede ao auth, pela rede interna do compose, uma sessão de serviço ("servico:smoke"). Essa rota não
passa pelo nginx: só quem está dentro da rede e conhece o AUTH_SEGREDO do .env consegue.
"""

import functools
import os

import httpx

AUTH = os.environ.get("AUTH_URL", "http://auth:8000")
COOKIE = "bussola_sessao"


@functools.cache
def valor() -> str:
    segredo = os.environ.get("AUTH_SEGREDO", "")
    if not segredo:
        raise RuntimeError("AUTH_SEGREDO vazio: defina-o no .env para pedir uma sessão ao auth.")
    resposta = httpx.post(
        f"{AUTH}/interno/sessao",
        json={"nome": "smoke"},
        headers={"Authorization": f"Bearer {segredo}"},
        timeout=10,
    )
    resposta.raise_for_status()
    return resposta.json()["valor"]


def cabecalho() -> dict[str, str]:
    """O cabeçalho Cookie da sessão, para cada chamada ao web."""
    return {"Cookie": f"{COOKIE}={valor()}"}
