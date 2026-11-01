"""Catálogo do dashboard: gateway em memória, saúde simulada e barramento falso."""

import hashlib
import json
from typing import Any

import pytest
from fakeredis import FakeAsyncRedis
from mcp.client.client import Client
from mcp.server.extension import Extension, MethodBinding, ResourceBinding
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.resources import TextResource

from agent.catalogo import Catalogo, NaoEncontrado
from bussola_comum.eventos import STREAM
from bussola_comum.skills import (
    IDENTIFICADOR,
    ParamsListar,
    ParamsObter,
    ResultadoListar,
    ResultadoObter,
    ler_frontmatter,
)

pytestmark = pytest.mark.anyio

PRINCIPAL = "skill://principal/SKILL.md"
APOIO = "skill://apoio/SKILL.md"
ARQUIVOS = {
    PRINCIPAL: (
        "---\nname: principal\ndescription: Rota principal.\nallowed-tools: cliente.obter_perfil\n"
        "metadata:\n  usa-skills: apoio\n---\n\n# Principal\n"
    ),
    APOIO: "---\nname: apoio\ndescription: Apoio.\nallowed-tools: seguradoras.cotar_seguro\n---\n\n# Apoio\n",
    "skill://principal/references/extra.md": "# Extra\n",
    "skill://principal/workflow.yaml": (
        "pre-requisitos:\n  seguradoras.cotar_seguro:\n    - cliente.obter_perfil\n"
        "impedimentos:\n  seguradoras.cotar_seguro: [pagamentos.estornar]\n"
    ),
}


def _descritor(uri: str) -> dict[str, Any]:
    conteudo = ARQUIVOS[uri].encode()
    return {"uri": uri, "digest": "sha256:" + hashlib.sha256(conteudo).hexdigest(), "size": len(conteudo)}


class Skills(Extension):
    identifier = IDENTIFICADOR

    def _entrada(self, uri: str) -> dict[str, Any]:
        arquivos = [u for u in ARQUIVOS if u.startswith(uri.removesuffix("SKILL.md"))]
        return {
            "uri": uri,
            "frontmatter": ler_frontmatter(ARQUIVOS[uri]),
            "resources": [_descritor(u) for u in arquivos],
        }

    def methods(self):
        async def listar(ctx, params):
            return ResultadoListar(skills=[self._entrada(PRINCIPAL), self._entrada(APOIO)])

        async def obter(ctx, params):
            return ResultadoObter(skill=self._entrada(params.uri))

        return [
            MethodBinding("skills/list", ParamsListar, listar),
            MethodBinding("skills/get", ParamsObter, obter),
        ]

    def resources(self):
        return [ResourceBinding(TextResource(uri=u, name=u, text=t)) for u, t in ARQUIVOS.items()]


def _gateway() -> MCPServer:
    s = MCPServer(name="mcp-gateway", extensions=[Skills()])

    @s.tool(name="cliente.obter_perfil", description="[cliente] Perfil da cliente.")
    def obter_perfil(cliente_id: str) -> dict:
        return {}

    @s.tool(name="seguradoras.cotar_seguro", description="[seguradoras] Cota.")
    def cotar(cliente_id: str) -> dict:
        return {}

    @s.tool(name="pagamentos.estornar", description="[pagamentos] Estorna.")
    def estornar(pagamento_id: str) -> dict:
        return {}

    @s.prompt(
        name="canais.atendimento_app",
        title="Atendimento no app",
        description="Persona no app. Canal: canal-app. Interlocutor: a própria cliente.",
    )
    def persona(cliente_id: str) -> str:
        return f"Você atende {cliente_id}."

    @s.resource("fonte://cliente-mcp/tool/obter_perfil")
    def fonte() -> str:
        return json.dumps({"tipo": "tool", "nome": "obter_perfil", "texto": "def obter_perfil(): ..."})

    return s


SAUDE = {
    "servicos": [
        {
            "nome": "cliente-mcp",
            "ferramentas": [
                {
                    "nome": "obter_perfil",
                    "qualificado": "cliente.obter_perfil",
                    "visivel": True,
                    "fora": True,
                },
                {"nome": "ping", "qualificado": None, "visivel": False, "fora": False},
            ],
            "prompts": [],
            "skills": [],
        },
        {"nome": "canais-mcp", "ferramentas": [], "prompts": ["canais.atendimento_app"], "skills": []},
        {"nome": "skills-mcp", "ferramentas": [], "prompts": [], "skills": [APOIO, PRINCIPAL]},
    ]
}


@pytest.fixture
def catalogo() -> Catalogo:
    servidor = _gateway()

    async def saude():
        return SAUDE

    return Catalogo(lambda: Client(servidor), FakeAsyncRedis(decode_responses=True), saude)


async def test_tools_cruzadas_com_as_skills_inclusive_por_reuso(catalogo):
    dados = await catalogo.montar()
    tools = {t["nome"]: t for t in dados["tools"]}
    perfil, cotar, estornar = (
        tools["cliente.obter_perfil"],
        tools["seguradoras.cotar_seguro"],
        tools["pagamentos.estornar"],
    )

    assert (
        perfil["servidor"] == "cliente-mcp" and perfil["fora"] and perfil["descricao"] == "Perfil da cliente."
    )
    assert perfil["esquema_entrada"]["required"] == ["cliente_id"]
    assert [(s["nome"], s["direta"]) for s in perfil["skills"]] == [("principal", True)]
    assert [(s["nome"], s["direta"]) for s in cotar["skills"]] == [("apoio", True), ("principal", False)]
    assert estornar["skills"] == []  # distração: nenhuma skill a permite


async def test_skills_e_prompts_do_catalogo(catalogo):
    dados = await catalogo.montar()
    principal = next(s for s in dados["skills"] if s["nome"] == "principal")
    assert principal["servidor"] == "skills-mcp" and principal["usa_skills"] == ["apoio"]
    assert principal["tools_com_reuso"] == ["cliente.obter_perfil", "seguradoras.cotar_seguro"]
    assert len(principal["arquivos"]) == 3
    assert principal["ordem"] == [
        {
            "tool": "seguradoras.cotar_seguro",
            "exige": ["cliente.obter_perfil"],
            "impedida_por": ["pagamentos.estornar"],
        }
    ]
    assert next(s for s in dados["skills"] if s["nome"] == "apoio")["ordem"] == []
    [prompt] = dados["prompts"]
    assert (prompt["canal"], prompt["interlocutor"], prompt["descricao"]) == (
        "canal-app",
        "a própria cliente",
        "Persona no app.",
    )
    assert prompt["servidor"] == "canais-mcp" and prompt["argumentos"][0]["nome"] == "cliente_id"


async def test_fonte_so_por_uri_fonte(catalogo):
    assert (await catalogo.fonte("fonte://cliente-mcp/tool/obter_perfil"))["nome"] == "obter_perfil"
    with pytest.raises(ValueError):
        await catalogo.fonte("skill://principal/SKILL.md")
    with pytest.raises(NaoEncontrado):
        await catalogo.fonte("fonte://cliente-mcp/tool/nada")


async def test_arquivo_de_skill_verificado(catalogo):
    arquivo = await catalogo.arquivo_de_skill("skill://principal/references/extra.md")
    assert arquivo["texto"] == "# Extra\n" and arquivo["verificado"]
    with pytest.raises(ValueError):
        await catalogo.arquivo_de_skill("fonte://x/tool/y")
    with pytest.raises(NaoEncontrado):
        await catalogo.arquivo_de_skill("skill://inexistente/SKILL.md")


async def test_previa_do_prompt_para_a_ana(catalogo):
    assert (await catalogo.previa_de_prompt("canais.atendimento_app"))["texto"] == "Você atende cliente-ana."
    with pytest.raises(NaoEncontrado):
        await catalogo.previa_de_prompt("canais.atendimento_loja")


async def test_chamadas_recentes_filtradas_por_item(catalogo):
    async def evento(tipo: str, **dados):
        await catalogo.redis.xadd(
            STREAM,
            {
                "tipo": tipo,
                "origem": "teste",
                "instante": "2026-11-01T10:00:00+00:00",
                "dados": json.dumps(dados),
            },
        )

    await evento("tool.called", tool="cliente.obter_perfil", status="ok", skill=PRINCIPAL, execucao_id="e1")
    await evento("tool.called", tool="pagamentos.estornar", status="erro", motivo="fora_da_skill")
    await evento("skill.loaded", uri=PRINCIPAL, execucao_id="e1")
    await evento("prompt.read", prompt="canais.atendimento_app", status="ok")

    perfil = await catalogo.chamadas(tool="cliente.obter_perfil")
    assert [(c["tool"], c["execucao_id"]) for c in perfil] == [("cliente.obter_perfil", "e1")]
    assert [c["tipo"] for c in await catalogo.chamadas(skill=PRINCIPAL)] == ["skill.loaded", "tool.called"]
    assert len(await catalogo.chamadas(prompt="canais.atendimento_app")) == 1
    assert (await catalogo.chamadas(tool="pagamentos.estornar"))[0]["motivo"] == "fora_da_skill"
