"""Sessão para os testes, o ensaio e as capturas passarem pelo web como a plateia, já logados.

Pede ao auth, pela rede interna do compose, uma sessão de serviço ("servico:e2e"). Essa rota não
passa pelo nginx: só quem está dentro da rede e conhece o AUTH_SEGREDO do .env consegue.
"""

import functools
import json
import os
import urllib.request

AUTH = os.environ.get("AUTH_URL", "http://auth:8000")
COOKIE = "bussola_sessao"


@functools.cache
def valor() -> str:
    segredo = os.environ.get("AUTH_SEGREDO", "")
    if not segredo:
        raise RuntimeError(
            "AUTH_SEGREDO vazio: os testes precisam dele para pedir uma sessão ao auth. Defina-o no .env."
        )
    pedido = urllib.request.Request(
        f"{AUTH}/interno/sessao",
        data=json.dumps({"nome": "e2e"}).encode(),
        method="POST",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {segredo}"},
    )
    with urllib.request.urlopen(pedido, timeout=10) as resposta:
        return json.load(resposta)["valor"]


def instalar_no_urllib() -> None:
    """Todo urllib.request.urlopen deste processo passa a levar o cookie da sessão."""
    abridor = urllib.request.build_opener()
    abridor.addheaders = [("Cookie", f"{COOKIE}={valor()}")]
    urllib.request.install_opener(abridor)


def cookies(web: str) -> list[dict]:
    """O cookie da sessão no formato do Playwright (context.add_cookies)."""
    return [{"name": COOKIE, "value": valor(), "url": web}]
