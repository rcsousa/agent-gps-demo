"""Gateway e skills: agregação SEP-2640 e governança por skill ativa."""

import hashlib
from typing import Any

import pytest
from fakeredis import FakeAsyncRedis
from mcp.client.client import Client
from mcp.server.extension import Extension, MethodBinding, ResourceBinding
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.resources import TextResource
from mcp.shared.exceptions import MCPError

from bussola_comum.estado_vivo import EstadoVivo
from bussola_comum.skills import (
    CHAVE_EXECUCAO,
    CHAVE_SKILL_ATIVA,
    IDENTIFICADOR,
    ParamsListar,
    ParamsObter,
    ResultadoListar,
    ResultadoObter,
    ler_arquivo,
    ler_frontmatter,
    listar_skills,
    obter_skill,
)
from mcp_gateway.catalogo import Catalogo
from mcp_gateway.servidor_mcp import CHAVE_PROVENIENCIA, criar_servidor_mcp
from mcp_gateway.upstreams import Upstream

pytestmark = pytest.mark.anyio

PRINCIPAL = "skill://principal/SKILL.md"
APOIO = "skill://apoio/SKILL.md"
SKILL_MD = {
    PRINCIPAL: "---\nname: principal\ndescription: Rota principal.\nallowed-tools: cliente.obter_perfil\n"
    "metadata:\n  usa-skills: apoio\n---\n\nUse cliente.obter_perfil.\n",
    APOIO: "---\nname: apoio\ndescription: Trecho de apoio.\n"
    "allowed-tools: cliente.verificar\n---\n\nApoio.\n",
}


class SkillsFalsas(Extension):
    identifier = IDENTIFICADOR

    @staticmethod
    def _entrada(uri: str) -> dict[str, Any]:
        conteudo = SKILL_MD[uri].encode()
        return {
            "uri": uri,
            "frontmatter": ler_frontmatter(SKILL_MD[uri]),
            "resources": [
                {
                    "uri": uri,
                    "digest": "sha256:" + hashlib.sha256(conteudo).hexdigest(),
                    "size": len(conteudo),
                }
            ],
        }

    def methods(self):
        async def listar(ctx, params):
            return ResultadoListar(skills=[self._entrada(u) for u in SKILL_MD])

        async def obter(ctx, params):
            if params.uri not in SKILL_MD:
                raise MCPError(code=-32602, message="desconhecida")
            return ResultadoObter(skill=self._entrada(params.uri))

        return [
            MethodBinding("skills/list", ParamsListar, listar),
            MethodBinding("skills/get", ParamsObter, obter),
        ]

    def resources(self):
        return [ResourceBinding(TextResource(uri=u, name=u, text=t)) for u, t in SKILL_MD.items()]


def _skills_mcp() -> MCPServer:
    return MCPServer(name="skills-mcp", extensions=[SkillsFalsas()])


def _cliente_mcp() -> MCPServer:
    s = MCPServer(name="cliente-mcp")

    @s.tool()
    def obter_perfil() -> dict[str, Any]:
        return {"nome": "Ana Ribeiro"}

    @s.tool()
    def verificar() -> dict[str, Any]:
        return {"ok": True}

    @s.tool()
    def estornar() -> dict[str, Any]:
        return {"estornado": True}

    return s


SERVIDORES = {"skills-mcp": _skills_mcp(), "cliente-mcp": _cliente_mcp()}
UPSTREAMS = [
    Upstream(nome="skills-mcp", prefixo="skills", url="http://skills-mcp:8000"),
    Upstream(nome="cliente-mcp", prefixo="cliente", url="http://cliente-mcp:8000"),
]


class PublicadorFalso:
    def __init__(self) -> None:
        self.eventos: list[tuple[str, dict]] = []

    async def publicar(self, tipo: str, dados: dict) -> None:
        self.eventos.append((tipo, dados))


@pytest.fixture
async def gateway():
    catalogo = Catalogo(UPSTREAMS, lambda u: Client(SERVIDORES[u.nome]))
    await catalogo.atualizar()
    publicador = PublicadorFalso()
    estado = EstadoVivo(FakeAsyncRedis(decode_responses=True))
    return catalogo, publicador, criar_servidor_mcp(catalogo, publicador, estado)


async def _chamar(servidor, tool: str, skill: str | None):
    async with Client(servidor) as c:
        return await c.call_tool(tool, {}, meta={CHAVE_SKILL_ATIVA: skill} if skill else None)


async def test_gateway_agrega_e_anuncia_skills(gateway):
    catalogo, publicador, servidor = gateway
    assert set(catalogo.skills) == {PRINCIPAL, APOIO}
    async with Client(servidor) as c:
        assert IDENTIFICADOR in c.server_capabilities.extensions
        entradas = await listar_skills(c)
        entrada = await obter_skill(c, PRINCIPAL)
        texto = await ler_arquivo(c, PRINCIPAL, entrada)
        with pytest.raises(MCPError):
            await obter_skill(c, "skill://nada/SKILL.md")
    assert {e["uri"] for e in entradas} == {PRINCIPAL, APOIO}
    assert "Use cliente.obter_perfil" in texto
    tipos = [t for t, _ in publicador.eventos]
    assert "skills.listed" in tipos and "resource.read" in tipos


async def test_skill_permite_suas_tools_e_as_herdadas(gateway):
    _, _, servidor = gateway
    assert not (await _chamar(servidor, "cliente.obter_perfil", PRINCIPAL)).is_error
    assert not (await _chamar(servidor, "cliente.verificar", PRINCIPAL)).is_error  # via usa-skills


async def test_contramao_fora_da_skill(gateway):
    _, publicador, servidor = gateway
    resultado = await _chamar(servidor, "cliente.estornar", PRINCIPAL)
    assert resultado.is_error and "Contramão" in resultado.content[0].text
    proveniencia = resultado.meta[CHAVE_PROVENIENCIA]
    assert proveniencia["motivo"] == "fora_da_skill" and proveniencia["skill"] == PRINCIPAL
    assert publicador.eventos[-1][1]["motivo"] == "fora_da_skill"


async def test_skill_de_apoio_nao_herda_da_principal(gateway):
    _, _, servidor = gateway
    assert (await _chamar(servidor, "cliente.obter_perfil", APOIO)).is_error


async def test_sem_skill_nada_e_restrito(gateway):
    _, _, servidor = gateway
    assert not (await _chamar(servidor, "cliente.estornar", None)).is_error


async def test_skill_desconhecida_e_bloqueada(gateway):
    _, _, servidor = gateway
    resultado = await _chamar(servidor, "cliente.obter_perfil", "skill://nada/SKILL.md")
    assert resultado.is_error
    assert resultado.meta[CHAVE_PROVENIENCIA]["motivo"] == "skill_desconhecida"


async def test_execucao_vai_do_meta_para_a_proveniencia_e_o_evento(gateway):
    _, publicador, servidor = gateway
    async with Client(servidor) as c:
        resultado = await c.call_tool(
            "cliente.obter_perfil", {}, meta={CHAVE_SKILL_ATIVA: PRINCIPAL, CHAVE_EXECUCAO: "exec-123"}
        )
    assert resultado.meta[CHAVE_PROVENIENCIA]["execucao_id"] == "exec-123"
    assert publicador.eventos[-1][1]["execucao_id"] == "exec-123"


async def test_leituras_da_skill_carregam_a_execucao_para_o_raio_x(gateway):
    _, publicador, servidor = gateway
    meta = {CHAVE_EXECUCAO: "exec-9"}
    async with Client(servidor) as c:
        await c.list_tools(meta=meta)
        entradas = {e["uri"]: e for e in await listar_skills(c, meta)}
        await obter_skill(c, PRINCIPAL, meta)
        await ler_arquivo(c, PRINCIPAL, entradas[PRINCIPAL], {**meta, CHAVE_SKILL_ATIVA: PRINCIPAL})
        await c.call_tool("cliente.obter_perfil", {}, meta=meta)
    por_tipo = {tipo: dados for tipo, dados in publicador.eventos}
    for tipo in ("tools.listed", "skills.listed", "skill.read", "resource.read", "tool.called"):
        assert por_tipo[tipo]["execucao_id"] == "exec-9", tipo
    assert por_tipo["resource.read"]["skill"] == PRINCIPAL
    assert por_tipo["resource.read"]["duracao_ms"] >= 0
    assert "Ana Ribeiro" in por_tipo["tool.called"]["resultado"]
