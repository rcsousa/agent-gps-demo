"""Prompts agregados pelo gateway: nome qualificado, roteamento, proveniência e evento."""

from contextlib import asynccontextmanager

import pytest
from fakeredis import FakeAsyncRedis
from mcp.client.client import Client
from mcp.server.mcpserver import MCPServer
from mcp.shared.exceptions import MCPError

from bussola_comum.estado_vivo import EstadoVivo
from bussola_comum.mcp_servidor import criar_servidor_mcp as servidor_de_dominio
from bussola_comum.skills import CHAVE_EXECUCAO
from mcp_gateway.catalogo import Catalogo
from mcp_gateway.servidor_mcp import CHAVE_PROVENIENCIA, criar_servidor_mcp
from mcp_gateway.upstreams import Upstream

pytestmark = pytest.mark.anyio


def _canais() -> MCPServer:
    s = servidor_de_dominio("canais-mcp", "Canais", checagens={})

    @s.prompt(name="atendimento_app", description="Persona no app.")
    def atendimento_app(cliente_id: str) -> str:
        return f"Você atende {cliente_id} pelo app."

    return s


def _cliente() -> MCPServer:
    s = MCPServer(name="cliente-mcp")

    @s.tool()
    def obter_perfil() -> dict:
        return {"nome": "Ana"}

    return s


UPSTREAMS = [
    Upstream(nome="canais-mcp", prefixo="canais", url="http://canais-mcp:8000"),
    Upstream(nome="cliente-mcp", prefixo="cliente", url="http://cliente-mcp:8000"),
]


class PublicadorFalso:
    def __init__(self) -> None:
        self.eventos: list[tuple[str, dict]] = []

    async def publicar(self, tipo: str, dados: dict) -> None:
        self.eventos.append((tipo, dados))


@pytest.fixture
async def gateway():
    servidores = {"canais-mcp": _canais(), "cliente-mcp": _cliente()}
    fora: set[str] = set()

    @asynccontextmanager
    async def conectar(upstream: Upstream):
        if upstream.nome in fora:
            raise ConnectionError("fora do ar")
        async with Client(servidores[upstream.nome]) as cliente:
            yield cliente

    catalogo = Catalogo(UPSTREAMS, conectar)
    await catalogo.atualizar()
    publicador = PublicadorFalso()
    servidor = criar_servidor_mcp(catalogo, publicador, EstadoVivo(FakeAsyncRedis(decode_responses=True)))
    return catalogo, publicador, servidor, fora


async def test_prompts_agregados_com_nome_qualificado(gateway):
    catalogo, _, servidor, _ = gateway
    async with Client(servidor) as c:
        prompts = (await c.list_prompts()).prompts
    assert [p.name for p in prompts] == ["canais.atendimento_app"]
    assert prompts[0].arguments[0].name == "cliente_id"
    assert catalogo.prompts_de(UPSTREAMS[0]) == ["canais.atendimento_app"]
    assert catalogo.prompts_de(UPSTREAMS[1]) == []


async def test_get_roteia_com_proveniencia_e_evento(gateway):
    _, publicador, servidor, _ = gateway
    async with Client(servidor) as c:
        resultado = await c.get_prompt(
            "canais.atendimento_app", {"cliente_id": "cliente-ana"}, meta={CHAVE_EXECUCAO: "exec-9"}
        )
    assert resultado.messages[0].content.text == "Você atende cliente-ana pelo app."
    proveniencia = resultado.meta[CHAVE_PROVENIENCIA]
    assert proveniencia["servidor"] == "canais-mcp" and proveniencia["status"] == "ok"
    assert proveniencia["execucao_id"] == "exec-9"
    tipo, dados = publicador.eventos[-1]
    assert tipo == "prompt.read" and dados["prompt"] == "canais.atendimento_app"
    assert dados["argumentos"] == {"cliente_id": "cliente-ana"}


async def test_prompt_desconhecido_e_erro_claro(gateway):
    _, _, servidor, _ = gateway
    async with Client(servidor) as c:
        with pytest.raises(MCPError, match="Prompt desconhecido"):
            await c.get_prompt("canais.atendimento_loja", {})


async def test_servidor_fora_mantem_o_catalogo_e_interdita(gateway):
    catalogo, publicador, servidor, fora = gateway
    fora.add("canais-mcp")
    await catalogo.atualizar()
    assert "canais.atendimento_app" in catalogo.prompts  # a rua continua no mapa
    async with Client(servidor) as c:
        with pytest.raises(MCPError, match="trecho interditado"):
            await c.get_prompt("canais.atendimento_app", {"cliente_id": "cliente-ana"})
    assert publicador.eventos[-1][1]["status"] == "erro"


async def test_fonte_roteada_pelo_nome_do_servidor(gateway):
    import json

    _, _, servidor, _ = gateway
    async with Client(servidor) as c:
        fonte = json.loads(
            (await c.read_resource("fonte://canais-mcp/prompt/atendimento_app")).contents[0].text
        )
        listados = [str(r.uri) for r in (await c.list_resources()).resources]
        with pytest.raises(MCPError, match="Resource desconhecido"):
            await c.read_resource("fonte://servidor-x/tool/ping")
    assert "def atendimento_app(cliente_id: str)" in fonte["texto"]
    assert not any(u.startswith("fonte://") for u in listados)
