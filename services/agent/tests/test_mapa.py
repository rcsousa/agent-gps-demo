"""API do mapa: cidade, rotas e entidade lidas do gateway (em memória)."""

import json

import pytest
from mcp.client.client import Client
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import BaseModel

from agent.mapa import EntidadeNaoEncontrada, Mapa

pytestmark = pytest.mark.anyio

CIDADE = {
    "mundo": {"largura": 1000, "altura": 700},
    "bairros": [{"id": "cliente", "nome": "Cliente", "cor": "#7b4fd6", "poligono": [[0, 0], [9, 0], [9, 9]]}],
    "nos": [{"id": "sistema-crm", "nome": "CRM", "x": 5, "y": 5, "bairro": "cliente", "status": "ok"}],
    "arestas": [],
}


# Como no contexto-mcp: respostas tipadas viram structured_content sem envelope.
class RespostaRota(BaseModel):
    rotas: list[dict]


class RespostaEntidade(BaseModel):
    entidade: dict
    relacoes: list[dict]


def _gateway() -> MCPServer:
    s = MCPServer(name="mcp-gateway")

    @s.resource("contexto://mapa")
    def mapa() -> str:
        return json.dumps(CIDADE)

    @s.tool(name="contexto.consultar_rota", description="[contexto] Rotas.")
    def consultar_rota() -> RespostaRota:
        return RespostaRota(
            rotas=[{"id": "rota-rapida", "paradas": [], "estimativa": {"bloqueada": False}, "alertas": []}]
        )

    @s.tool(name="contexto.consultar_entidade", description="[contexto] Entidade.")
    def consultar_entidade(id: str) -> RespostaEntidade:
        if id != "sistema-crm":
            raise ToolError(f"Entidade {id} não existe no grafo.")
        return RespostaEntidade(entidade={"id": id, "nome": "CRM"}, relacoes=[])

    return s


@pytest.fixture
def mapa() -> Mapa:
    servidor = _gateway()
    return Mapa(lambda: Client(servidor))


async def test_cidade_vem_do_recurso_do_grafo(mapa):
    cidade = await mapa.cidade()
    assert cidade["nos"][0]["id"] == "sistema-crm"
    assert cidade["mundo"] == {"largura": 1000, "altura": 700}


async def test_rotas_vem_da_tool_de_contexto(mapa):
    rotas = await mapa.rotas()
    assert [r["id"] for r in rotas["rotas"]] == ["rota-rapida"]


async def test_entidade_e_erro_sem_o_prefixo_do_sdk(mapa):
    assert (await mapa.entidade("sistema-crm"))["entidade"]["nome"] == "CRM"
    with pytest.raises(EntidadeNaoEncontrada) as erro:
        await mapa.entidade("nao-existe")
    assert str(erro.value) == "Entidade nao-existe não existe no grafo."
