import asyncio

from mcp.client.client import Client
from starlette.testclient import TestClient

from bussola_comum.mcp_servidor import criar_app
from contexto_mcp.servidor import NOME, criar_servidor


async def _grafo_ok() -> bool:
    return True


async def _grafo_fora() -> bool:
    raise ConnectionError("sem grafo")


def test_saude_ok_quando_grafo_responde():
    with TestClient(criar_app(criar_servidor({"graph": _grafo_ok}))) as cliente:
        resposta = cliente.get("/saude")
    assert resposta.status_code == 200
    assert resposta.json()["dependencias"] == {"graph": "ok"}


def test_saude_fora_quando_grafo_nao_responde():
    with TestClient(criar_app(criar_servidor({"graph": _grafo_fora}))) as cliente:
        resposta = cliente.get("/saude")
    assert resposta.status_code == 503
    assert resposta.json()["status"] == "fora"
    assert resposta.json()["dependencias"] == {"graph": "fora"}


def test_tool_ping_responde_pelo_protocolo_mcp():
    async def chamar():
        async with Client(criar_servidor({"graph": _grafo_ok})) as cliente:
            return await cliente.call_tool("ping", {})

    resultado = asyncio.run(chamar())
    assert resultado.content[0].text == f"pong de {NOME}"
