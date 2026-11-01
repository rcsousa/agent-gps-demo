"""A ordem também é lei: o workflow da skill aplicado pelo gateway, por execução."""

import hashlib
from typing import Any

import pytest
from fakeredis import FakeAsyncRedis
from mcp.client.client import Client
from mcp.server.extension import Extension, MethodBinding, ResourceBinding
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.resources import TextResource

from bussola_comum.estado_vivo import EstadoVivo
from bussola_comum.skills import (
    CHAVE_EXECUCAO,
    CHAVE_SKILL_ATIVA,
    IDENTIFICADOR,
    ParamsListar,
    ParamsObter,
    ResultadoListar,
    ResultadoObter,
    ler_frontmatter,
)
from bussola_comum.workflow import WorkflowInvalido, carregar
from mcp_gateway.catalogo import Catalogo
from mcp_gateway.servidor_mcp import CHAVE_PROVENIENCIA, criar_servidor_mcp
from mcp_gateway.upstreams import Upstream

pytestmark = pytest.mark.anyio

SKILL = "skill://jornada/SKILL.md"
WORKFLOW = """
pre-requisitos:
  loja.cotar:
    - loja.verificar: { permitido: true }
  loja.pagar:
    - loja.aceitar
    - qualquer:
        - loja.proposta: { exige_aprovacao: false }
        - loja.aprovar
impedimentos:
  loja.pagar: [loja.agendar_vistoria]
"""
ARQUIVOS = {
    SKILL: "---\nname: jornada\ndescription: Jornada.\nallowed-tools: loja.verificar loja.cotar "
    "loja.proposta loja.aceitar loja.aprovar loja.pagar loja.agendar_vistoria\n---\n\n"
    "Veja skill://jornada/workflow.yaml.\n",
    "skill://jornada/workflow.yaml": WORKFLOW,
}


def _descritor(uri: str) -> dict[str, Any]:
    conteudo = ARQUIVOS[uri].encode()
    return {"uri": uri, "digest": "sha256:" + hashlib.sha256(conteudo).hexdigest(), "size": len(conteudo)}


class Skills(Extension):
    identifier = IDENTIFICADOR

    def _entrada(self) -> dict[str, Any]:
        return {
            "uri": SKILL,
            "frontmatter": ler_frontmatter(ARQUIVOS[SKILL]),
            "resources": [_descritor(u) for u in ARQUIVOS],
        }

    def methods(self):
        async def listar(ctx, params):
            return ResultadoListar(skills=[self._entrada()])

        async def obter(ctx, params):
            return ResultadoObter(skill=self._entrada())

        return [
            MethodBinding("skills/list", ParamsListar, listar),
            MethodBinding("skills/get", ParamsObter, obter),
        ]

    def resources(self):
        return [ResourceBinding(TextResource(uri=u, name=u, text=t)) for u, t in ARQUIVOS.items()]


def _loja() -> MCPServer:
    s = MCPServer(name="loja-mcp")

    @s.tool()
    def verificar(permitir: bool = True) -> dict[str, Any]:
        return {"permitido": permitir}

    @s.tool()
    def cotar() -> dict[str, Any]:
        return {"premio": 100}

    @s.tool()
    def proposta(alto: bool = False) -> dict[str, Any]:
        return {"exige_aprovacao": alto}

    @s.tool()
    def aceitar() -> dict[str, Any]:
        return {"aceita": True}

    @s.tool()
    def aprovar() -> dict[str, Any]:
        return {"status": "aprovada"}

    @s.tool()
    def pagar() -> dict[str, Any]:
        return {"pago": True}

    @s.tool()
    def agendar_vistoria() -> dict[str, Any]:
        return {"agendada": True}

    return s


SERVIDORES = {"skills-mcp": MCPServer(name="skills-mcp", extensions=[Skills()]), "loja-mcp": _loja()}
UPSTREAMS = [
    Upstream(nome="skills-mcp", prefixo="skills", url="http://skills-mcp:8000"),
    Upstream(nome="loja-mcp", prefixo="loja", url="http://loja-mcp:8000"),
]


class PublicadorFalso:
    async def publicar(self, tipo: str, dados: dict) -> None:
        return None


@pytest.fixture
async def gateway():
    catalogo = Catalogo(UPSTREAMS, lambda u: Client(SERVIDORES[u.nome]))
    await catalogo.atualizar()
    servidor = criar_servidor_mcp(
        catalogo, PublicadorFalso(), EstadoVivo(FakeAsyncRedis(decode_responses=True))
    )
    return catalogo, servidor


async def _chamar(
    servidor, tool: str, execucao: str | None, argumentos: dict | None = None, skill: str | None = SKILL
):
    meta = {k: v for k, v in {CHAVE_SKILL_ATIVA: skill, CHAVE_EXECUCAO: execucao}.items() if v}
    async with Client(servidor) as c:
        resultado = await c.call_tool(tool, argumentos or {}, meta=meta or None)
    return resultado, resultado.meta[CHAVE_PROVENIENCIA].get("motivo")


async def test_gateway_le_o_workflow_da_skill_com_digest(gateway):
    catalogo, _ = gateway
    assert set(catalogo.workflows[SKILL].pre_requisitos) == {"loja.cotar", "loja.pagar"}


async def test_sem_execucao_a_ordem_nao_tem_como_ser_garantida(gateway):
    _, servidor = gateway
    resultado, motivo = await _chamar(servidor, "loja.verificar", None)
    assert resultado.is_error and motivo == "execucao_nao_identificada"


async def test_fora_de_ordem_bloqueia_e_diz_o_que_falta(gateway):
    _, servidor = gateway
    resultado, motivo = await _chamar(servidor, "loja.cotar", "e1")
    assert motivo == "fora_de_ordem"
    assert "loja.cotar exige antes: loja.verificar com permitido = true" in resultado.content[0].text


async def test_pre_requisito_olha_o_resultado(gateway):
    _, servidor = gateway
    await _chamar(servidor, "loja.verificar", "e2", {"permitir": False})
    _, motivo = await _chamar(servidor, "loja.cotar", "e2")
    assert motivo == "fora_de_ordem"  # verificou, mas não tinha permissão
    await _chamar(servidor, "loja.verificar", "e2", {"permitir": True})
    resultado, motivo = await _chamar(servidor, "loja.cotar", "e2")
    assert motivo is None and not resultado.is_error


async def test_fatos_sao_da_execucao(gateway):
    _, servidor = gateway
    await _chamar(servidor, "loja.verificar", "e3")
    _, motivo = await _chamar(servidor, "loja.cotar", "outra")
    assert motivo == "fora_de_ordem"


async def test_qualquer_alternativa_basta_e_impedimento_bloqueia(gateway):
    _, servidor = gateway
    await _chamar(servidor, "loja.aceitar", "e4")
    await _chamar(servidor, "loja.proposta", "e4", {"alto": True})
    _, motivo = await _chamar(servidor, "loja.pagar", "e4")
    assert motivo == "fora_de_ordem"  # acima da alçada e sem aprovação
    await _chamar(servidor, "loja.aprovar", "e4")
    _, motivo = await _chamar(servidor, "loja.pagar", "e4")
    assert motivo is None
    await _chamar(servidor, "loja.agendar_vistoria", "e4")
    resultado, motivo = await _chamar(servidor, "loja.pagar", "e4")
    assert motivo == "fora_de_ordem" and "depois de loja.agendar_vistoria" in resultado.content[0].text


async def test_sem_skill_a_ordem_nao_se_aplica(gateway):
    _, servidor = gateway
    resultado, motivo = await _chamar(servidor, "loja.pagar", "e5", skill=None)
    assert motivo is None and not resultado.is_error


def test_workflow_mal_formado_e_recusado():
    with pytest.raises(WorkflowInvalido):
        carregar("pre-requisitos:\n  loja.cotar:\n    - { a: 1, b: 2 }\n")
    with pytest.raises(WorkflowInvalido):
        carregar("passos: []\n")
