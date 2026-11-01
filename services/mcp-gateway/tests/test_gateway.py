"""Gateway com upstreams em memória: nada de rede nos testes de unidade."""

import json
from pathlib import Path
from typing import Any

import pytest
from fakeredis import FakeAsyncRedis
from mcp.client.client import Client
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from starlette.testclient import TestClient

from bussola_comum.estado_vivo import EstadoVivo
from mcp_gateway.catalogo import Catalogo
from mcp_gateway.main import Config, criar_app
from mcp_gateway.servidor_mcp import CHAVE_PROVENIENCIA, criar_servidor_mcp
from mcp_gateway.upstreams import Upstream, carregar_upstreams

pytestmark = pytest.mark.anyio
TOKEN = "token-de-teste"


def _cliente_mcp() -> MCPServer:
    s = MCPServer(name="cliente-mcp")

    @s.tool(description="Perfil da cliente.")
    def obter_perfil(cliente_id: str) -> dict[str, Any]:
        if cliente_id != "cliente-ana":
            raise ToolError("Cliente não encontrado.")
        return {"nome": "Ana Ribeiro"}

    @s.tool()
    def ping() -> str:
        return "pong"

    return s


def _contexto_mcp() -> MCPServer:
    s = MCPServer(name="contexto-mcp")

    @s.tool()
    def consultar_rota() -> dict[str, Any]:
        return {"rotas": 3}

    @s.resource("contexto://mapa", mime_type="application/json")
    def mapa() -> str:
        return json.dumps({"nos": 178})

    return s


UPSTREAMS = [
    Upstream(nome="cliente-mcp", prefixo="cliente", url="http://cliente-mcp:8000"),
    Upstream(nome="contexto-mcp", prefixo="contexto", url="http://contexto-mcp:8000"),
    Upstream(nome="risco-mcp", prefixo="risco", url="http://risco-mcp:8000"),
]
SERVIDORES = {"cliente-mcp": _cliente_mcp(), "contexto-mcp": _contexto_mcp()}


def conectar(upstream: Upstream):
    if upstream.nome not in SERVIDORES:
        raise ConnectionError(f"{upstream.nome} fora do ar")
    return Client(SERVIDORES[upstream.nome])


class PublicadorFalso:
    def __init__(self) -> None:
        self.eventos: list[tuple[str, dict]] = []

    async def publicar(self, tipo: str, dados: dict) -> None:
        self.eventos.append((tipo, dados))


@pytest.fixture
async def gateway():
    catalogo = Catalogo(UPSTREAMS, conectar)
    await catalogo.atualizar()
    publicador = PublicadorFalso()
    estado = EstadoVivo(FakeAsyncRedis(decode_responses=True))
    return catalogo, publicador, criar_servidor_mcp(catalogo, publicador, estado), estado


async def test_nomes_qualificados_sem_ping(gateway):
    _, _, servidor, _ = gateway
    async with Client(servidor) as c:
        nomes = {t.name for t in (await c.list_tools()).tools}
    assert nomes == {"cliente.obter_perfil", "contexto.consultar_rota"}


async def test_chamada_roteada_com_proveniencia_e_evento(gateway):
    _, publicador, servidor, _ = gateway
    async with Client(servidor) as c:
        resultado = await c.call_tool("cliente.obter_perfil", {"cliente_id": "cliente-ana"})
    assert resultado.structured_content == {"nome": "Ana Ribeiro"}
    proveniencia = resultado.meta[CHAVE_PROVENIENCIA]
    assert proveniencia["servidor"] == "cliente-mcp" and proveniencia["status"] == "ok"
    [(tipo, dados)] = publicador.eventos
    assert tipo == "tool.called"
    assert dados["tool"] == "cliente.obter_perfil" and dados["argumentos"] == {"cliente_id": "cliente-ana"}


async def test_erro_do_upstream_passa_adiante_com_status_erro(gateway):
    _, publicador, servidor, _ = gateway
    async with Client(servidor) as c:
        resultado = await c.call_tool("cliente.obter_perfil", {"cliente_id": "cliente-x"})
    assert resultado.is_error
    assert resultado.meta[CHAVE_PROVENIENCIA]["status"] == "erro"
    assert "não encontrado" in publicador.eventos[0][1]["erro"]


async def test_tool_desconhecida(gateway):
    _, _, servidor, _ = gateway
    async with Client(servidor) as c:
        resultado = await c.call_tool("seguradoras.cotar_seguro", {})
    assert resultado.is_error and "desconhecida" in resultado.content[0].text


async def test_upstream_que_cai_continua_no_mapa_como_interditado(gateway):
    catalogo, _, servidor, _ = gateway
    original = SERVIDORES.pop("cliente-mcp")
    try:
        await catalogo.atualizar()
        assert catalogo.disponiveis["cliente-mcp"] is False
        async with Client(servidor) as c:
            nomes = {t.name for t in (await c.list_tools()).tools}
            resultado = await c.call_tool("cliente.obter_perfil", {"cliente_id": "cliente-ana"})
    finally:
        SERVIDORES["cliente-mcp"] = original
    assert "cliente.obter_perfil" in nomes
    assert resultado.is_error and "interditado" in resultado.content[0].text


async def test_resource_roteado_pelo_uri(gateway):
    _, _, servidor, _ = gateway
    async with Client(servidor) as c:
        uris = [str(r.uri) for r in (await c.list_resources()).resources]
        mapa = await c.read_resource("contexto://mapa")
    assert uris == ["contexto://mapa"]
    assert json.loads(mapa.contents[0].text) == {"nos": 178}


def _app(tmp_path: Path):
    arquivo = tmp_path / "upstreams.yaml"
    arquivo.write_text("servidores:\n  - {nome: cliente-mcp, prefixo: cliente, url: 'http://127.0.0.1:9'}\n")

    async def ok() -> bool:
        return True

    config = Config(gateway_token=TOKEN, upstreams_arquivo=arquivo)
    estado = EstadoVivo(FakeAsyncRedis(decode_responses=True))
    return criar_app(
        config, checagens={"bus": ok}, conectar=conectar, publicador=PublicadorFalso(), estado=estado
    )


def test_saude_sem_token(tmp_path):
    with TestClient(_app(tmp_path)) as http:
        assert http.get("/saude").status_code == 200


def test_mcp_e_servicos_exigem_token(tmp_path):
    with TestClient(_app(tmp_path)) as http:
        assert http.post("/mcp", json={}).status_code == 401
        assert http.get("/saude/servicos").status_code == 401
        resposta = http.get("/saude/servicos", headers={"Authorization": f"Bearer {TOKEN}"})
    assert resposta.status_code == 200
    assert resposta.json()["ferramentas"] == 1
    assert resposta.json()["ferramentas_fora"] == 0
    nomes = {f["nome"] for f in resposta.json()["servicos"][0]["ferramentas"]}
    assert nomes == {"obter_perfil", "ping"}
    assert resposta.json()["servicos"][0]["status"] == "fora"


def test_config_versionada_lista_os_nove_servidores_mcp():
    nomes = [u.nome for u in carregar_upstreams(Config().upstreams_arquivo)]
    assert len(nomes) == 9 and "canais-mcp" in nomes


async def test_tool_desligada_pelo_simulador_falha_sem_chamar_o_servidor(gateway):
    _, publicador, servidor, estado = gateway
    await estado.desligar_tool("cliente.obter_perfil")
    async with Client(servidor) as c:
        nomes = {t.name for t in (await c.list_tools()).tools}
        resultado = await c.call_tool("cliente.obter_perfil", {"cliente_id": "cliente-ana"})
    assert "cliente.obter_perfil" in nomes  # continua visível para o agente
    assert resultado.is_error and "fora do ar" in resultado.content[0].text
    proveniencia = resultado.meta[CHAVE_PROVENIENCIA]
    assert proveniencia["status"] == "erro" and proveniencia["motivo"] == "desligada"
    assert publicador.eventos[0][1]["motivo"] == "desligada"

    await estado.religar_tool("cliente.obter_perfil")
    async with Client(servidor) as c:
        assert not (await c.call_tool("cliente.obter_perfil", {"cliente_id": "cliente-ana"})).is_error


async def test_lista_de_tools_por_servidor_com_ocultas(gateway):
    catalogo, _, _, _ = gateway
    [cliente] = [u for u in catalogo.upstreams if u.nome == "cliente-mcp"]
    itens = {i["nome"]: i for i in catalogo.ferramentas_de(cliente, fora={"cliente.obter_perfil"})}
    assert itens["ping"] == {"nome": "ping", "qualificado": None, "visivel": False, "fora": False}
    assert itens["obter_perfil"]["qualificado"] == "cliente.obter_perfil"
    assert itens["obter_perfil"]["fora"] is True
