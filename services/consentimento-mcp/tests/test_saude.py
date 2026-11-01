import asyncio

from mcp.client.client import Client
from starlette.testclient import TestClient

from bussola_comum.mcp_servidor import criar_app
from consentimento_mcp.servidor import NOME, criar_servidor


def test_saude_responde_ok():
    with TestClient(criar_app(criar_servidor())) as cliente:
        resposta = cliente.get("/saude")
    assert resposta.status_code == 200
    assert resposta.json()["servico"] == NOME
    assert resposta.json()["status"] == "ok"


def test_tool_ping_responde_pelo_protocolo_mcp():
    async def chamar():
        async with Client(criar_servidor()) as cliente:
            ferramentas = await cliente.list_tools()
            resultado = await cliente.call_tool("ping", {})
        return [f.name for f in ferramentas.tools], resultado

    nomes, resultado = asyncio.run(chamar())
    assert nomes == ["ping"]
    assert not resultado.is_error
    assert resultado.content[0].text == f"pong de {NOME}"
