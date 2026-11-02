"""Motor de execução com gateway em memória, Redis falso e LLM roteirizado no teste."""

import asyncio
import hashlib
import json
from typing import Any

import pytest
from fakeredis import FakeAsyncRedis
from mcp.client.client import Client
from mcp.server.extension import Extension, MethodBinding, ResourceBinding
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.mcpserver.resources import TextResource
from mcp.server.mcpserver.server import Context

from agent import prompts
from agent.config import Config
from agent.execucao import Motor
from agent.llm.base import ChamadaTool, Passo, ResultadoTool, Uso
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

pytestmark = pytest.mark.anyio

SKILL = "skill://contratacao/SKILL.md"
SKILL_MD = (
    "---\nname: contratacao\ndescription: Contrata seguro.\n"
    "allowed-tools: cliente.obter_perfil seguradoras.cotar_seguro "
    "contexto.consultar_rota\n---\n\nSiga as paradas.\n"
)


class SkillsFalsas(Extension):
    identifier = IDENTIFICADOR

    def _entrada(self) -> dict[str, Any]:
        conteudo = SKILL_MD.encode()
        return {
            "uri": SKILL,
            "frontmatter": ler_frontmatter(SKILL_MD),
            "resources": [
                {
                    "uri": SKILL,
                    "digest": "sha256:" + hashlib.sha256(conteudo).hexdigest(),
                    "size": len(conteudo),
                }
            ],
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
        return [ResourceBinding(TextResource(uri=SKILL, name="contratacao", text=SKILL_MD))]


PERSONAS_LIDAS: list[tuple[str, dict]] = []


def _gateway(metas: list[dict]) -> MCPServer:
    """Imita o gateway: tools e prompts com nome qualificado e a extensão de skills."""
    s = MCPServer(name="mcp-gateway", extensions=[SkillsFalsas()])

    @s.prompt(name="canais.atendimento_agencia")
    def persona_agencia(cliente_id: str, ctx: Context) -> str:
        meta = ctx.request_context.meta
        PERSONAS_LIDAS.append(
            (cliente_id, dict(meta) if isinstance(meta, dict) else meta.model_dump(by_alias=True))
        )
        return f"PERSONA DA AGÊNCIA para {cliente_id}"

    def guardar(ctx: Context) -> None:
        meta = ctx.request_context.meta
        metas.append(dict(meta) if isinstance(meta, dict) else meta.model_dump(by_alias=True))

    @s.tool(name="cliente.obter_perfil")
    def obter_perfil(cliente_id: str, ctx: Context) -> dict[str, Any]:
        guardar(ctx)
        return {"nome": "Ana Ribeiro"}

    @s.tool(name="cliente.listar_transacoes")
    def listar_transacoes(cliente_id: str, ctx: Context) -> dict[str, Any]:
        guardar(ctx)
        return {"transacoes": []}

    @s.tool(name="seguradoras.cotar_seguro")
    def cotar(cliente_id: str, seguradora: str, ctx: Context) -> dict[str, Any]:
        guardar(ctx)
        if seguradora == "ancora":
            raise ToolError("A API de cotação da Âncora Seguros está fora do ar no momento.")
        return {"cotacao_id": "c-1", "premio_anual": 309.97}

    @s.tool(name="contexto.consultar_rota")
    def consultar_rota(ctx: Context, rota: str | None = None) -> dict[str, Any]:
        guardar(ctx)
        paradas = [
            {"ordem": i, "numero": i, "id": f"p{i}", "nome": f"Parada {i}", "bairro": "cliente"}
            for i in (1, 2)
        ]
        estimativa = {"tempo_texto": "~5 min", "risco": "baixo", "bloqueada": False}
        return {
            "rotas": [
                {
                    "id": rota or "rota-rapida",
                    "nome": "Rota rápida",
                    "paradas": paradas,
                    "estimativa": estimativa,
                    "alertas": [],
                }
            ]
        }

    return s


class SessaoFalsa:
    provedor, modelo = "falso", "falso-1"

    def __init__(self, passos: list[Passo]) -> None:
        self.passos = passos
        self.tools_vistas: list[list[str]] = []
        self.resultados: list[list[ResultadoTool]] = []

    async def passo(self, tools):
        self.tools_vistas.append([t.nome for t in tools])
        return self.passos.pop(0)

    def adicionar_resultados(self, resultados):
        self.resultados.append(resultados)


class PublicadorFalso:
    def __init__(self) -> None:
        self.eventos: list[tuple[str, dict]] = []

    async def publicar(self, tipo, dados):
        self.eventos.append((tipo, dados))
        return None


def _passo(*chamadas: tuple[str, dict]) -> Passo:
    return Passo(
        chamadas=[ChamadaTool(f"c{i}", n, a) for i, (n, a) in enumerate(chamadas)],
        uso=Uso(entrada=10, saida=5),
    )


def _motor(
    sessao: SessaoFalsa, metas: list[dict], sistemas: list[str] | None = None
) -> tuple[Motor, PublicadorFalso]:
    publicador = PublicadorFalso()
    servidor = _gateway(metas)

    def fabrica(provedor, modo, sistema, pedido, config, canal="app", modelo=""):
        if sistemas is not None:
            sistemas.append(sistema)
        return sessao

    motor = Motor(
        Config(max_passos=10),
        FakeAsyncRedis(decode_responses=True),
        publicador,
        lambda: Client(servidor),
        fabrica_sessao=fabrica,
    )
    return motor, publicador


def _tipos(publicador: PublicadorFalso) -> list[str]:
    return [t for t, _ in publicador.eventos]


async def test_com_skill_so_libera_as_tools_depois_de_carregar_e_envia_meta():
    sessao = SessaoFalsa(
        [
            _passo(("cliente.obter_perfil", {"cliente_id": "cliente-ana"})),  # cedo demais
            _passo(("agente.carregar_skill", {"uri": SKILL})),
            _passo(("navegacao.planejar_rota", {"rota": "rota-rapida", "motivo": "livre"})),
            _passo(
                ("navegacao.iniciar_parada", {"parada": 1}),
                ("cliente.obter_perfil", {"cliente_id": "cliente-ana"}),
            ),
            Passo(texto="Pronto, Ana.", fim=True),
        ]
    )
    metas: list[dict] = []
    motor, publicador = _motor(sessao, metas)
    execucao = await motor.iniciar("com_skill", "falso")
    await motor.aguardar(execucao.id)

    # A lista de tools é a mesma em todos os passos (mudar invalida o pensamento preservado).
    assert all(vistas == sessao.tools_vistas[0] for vistas in sessao.tools_vistas)
    assert "cliente.obter_perfil" in sessao.tools_vistas[0]
    assert "cliente.listar_transacoes" not in sessao.tools_vistas[0]  # nenhuma skill a permite
    # Antes da skill, o host recusa sem chegar ao gateway: só a chamada depois da skill chegou.
    cedo = sessao.resultados[0][0]
    assert cedo.erro and "carregue a skill antes" in cedo.texto
    assert len(metas) == 2  # consultar_rota (planejar) e obter_perfil, ambos depois da skill
    assert metas[-1][CHAVE_SKILL_ATIVA] == SKILL and metas[-1][CHAVE_EXECUCAO] == execucao.id
    tipos = _tipos(publicador)
    assert tipos[0] == "run.started" and tipos[-1] == "run.finished"
    assert {"skill.loaded", "route.planned", "step.started", "agent.message"} <= set(tipos)
    parada = next(d for t, d in publicador.eventos if t == "step.started")
    assert parada["nome"] == "Parada 1" and parada["execucao_id"] == execucao.id
    final = await motor.obter(execucao.id)
    assert final["status"] == "concluida" and final["metricas"]["tokens"]["entrada"] == 40
    # Um model.step por chamada ao modelo, com os tokens que somam o total do run.finished.
    passos = [d for t, d in publicador.eventos if t == "model.step"]
    assert [p["passo"] for p in passos] == [1, 2, 3, 4, 5]
    assert sum(p["tokens"]["entrada"] for p in passos) == 40
    assert passos[3]["tools_pedidas"] == ["navegacao.iniciar_parada", "cliente.obter_perfil"]


async def test_sem_skill_mede_tools_irrelevantes_e_nao_envia_skill():
    sessao = SessaoFalsa(
        [
            _passo(
                ("cliente.listar_transacoes", {"cliente_id": "cliente-ana"}),
                ("cliente.obter_perfil", {"cliente_id": "cliente-ana"}),
            ),
            Passo(texto="Feito.", fim=True),
        ]
    )
    metas: list[dict] = []
    motor, _ = _motor(sessao, metas)
    execucao = await motor.iniciar("sem_skill", "falso")
    await motor.aguardar(execucao.id)
    metricas = (await motor.obter(execucao.id))["metricas"]
    assert metricas["chamadas_tool"] == 2
    assert metricas["tools_irrelevantes"] == ["cliente.listar_transacoes"]
    assert all(CHAVE_SKILL_ATIVA not in m for m in metas)


async def test_sem_contexto_so_tem_a_conversa():
    sessao = SessaoFalsa([Passo(texto="Contratei um seguro inventado.", fim=True)])
    motor, _ = _motor(sessao, [])
    execucao = await motor.iniciar("sem_contexto", "falso")
    await motor.aguardar(execucao.id)
    assert sessao.tools_vistas[0] == ["conversa.perguntar_cliente"]
    assert (await motor.obter(execucao.id))["metricas"]["chamadas_tool"] == 0


async def test_pergunta_a_cliente_pausa_ate_o_apresentador_responder():
    sessao = SessaoFalsa(
        [
            _passo(
                ("conversa.perguntar_cliente", {"pergunta": "Aceita?", "opcoes": ["Aceito", "Não aceito"]})
            ),
            Passo(texto="Obrigado.", fim=True),
        ]
    )
    motor, publicador = _motor(sessao, [])
    execucao = await motor.iniciar("sem_contexto", "falso")
    for _ in range(50):
        await asyncio.sleep(0.02)
        if (await motor.obter(execucao.id))["status"] == "aguardando_cliente":
            break
    assert (await motor.obter(execucao.id))["pergunta"]["opcoes"] == ["Aceito", "Não aceito"]
    assert motor.responder(execucao.id, "Aceito")
    await motor.aguardar(execucao.id)
    assert sessao.resultados[0][0].texto == "Aceito"
    assert [t for t in _tipos(publicador) if t.startswith("client.")] == ["client.asked", "client.answered"]
    assert not motor.responder(execucao.id, "de novo")


async def test_incidente_detectado_na_falha_da_tool():
    sessao = SessaoFalsa(
        [
            _passo(("seguradoras.cotar_seguro", {"cliente_id": "cliente-ana", "seguradora": "ancora"})),
            Passo(texto="Vou tentar outra.", fim=True),
        ]
    )
    motor, publicador = _motor(sessao, [])
    execucao = await motor.iniciar("sem_skill", "falso")
    await motor.aguardar(execucao.id)
    [incidente] = [d for t, d in publicador.eventos if t == "incident.detected"]
    assert incidente["metafora"] == "Rua interditada"
    assert not incidente["descricao"].startswith("Error executing tool")
    assert sessao.resultados[0][0].erro


async def test_erro_do_provedor_encerra_com_status_erro():
    from agent.llm.base import ErroProvedor

    def fabrica(*a, **k):
        raise ErroProvedor("ANTHROPIC_API_KEY não configurada.")

    publicador = PublicadorFalso()
    motor = Motor(
        Config(), FakeAsyncRedis(decode_responses=True), publicador, lambda: Client(_gateway([])), fabrica
    )
    execucao = await motor.iniciar("com_skill")
    await motor.aguardar(execucao.id)
    final = await motor.obter(execucao.id)
    assert final["status"] == "erro" and "ANTHROPIC_API_KEY" in final["erro"]
    assert publicador.eventos[-1][0] == "run.finished"


def test_resultado_textual_em_json():
    from agent.execucao import _texto_do_resultado

    class R:
        structured_content = {"a": 1}
        content = []

    assert json.loads(_texto_do_resultado(R())) == {"a": 1}


# --- Persona do canal: prompts MCP pelo gateway --------------------------------------


def _eventos(publicador: PublicadorFalso, tipo: str) -> list[dict]:
    return [d for t, d in publicador.eventos if t == tipo]


async def test_persona_do_canal_vem_do_gateway_antes_das_instrucoes_do_host():
    PERSONAS_LIDAS.clear()
    sistemas: list[str] = []
    motor, publicador = _motor(SessaoFalsa([Passo(texto="Ok.", fim=True)]), [], sistemas)
    execucao = await motor.iniciar("com_skill", "falso", canal="agencia")
    await motor.aguardar(execucao.id)

    assert sistemas[0].startswith("PERSONA DA AGÊNCIA para cliente-ana")
    assert sistemas[0].index("PERSONA") < sistemas[0].index("conversa.perguntar_cliente")
    assert PERSONAS_LIDAS[0][1][CHAVE_EXECUCAO] == execucao.id
    [evento] = _eventos(publicador, "prompt.loaded")
    assert evento["nome"] == "canais.atendimento_agencia" and evento["origem"] == "gateway"
    assert _tipos(publicador)[:2] == ["run.started", "prompt.loaded"]
    assert _eventos(publicador, "run.started")[0]["canal"] == "agencia"
    assert await motor.canais() == ["agencia"]


async def test_sem_contexto_nao_consulta_a_persona_do_banco():
    PERSONAS_LIDAS.clear()
    sistemas: list[str] = []
    motor, publicador = _motor(SessaoFalsa([Passo(texto="Ok.", fim=True)]), [], sistemas)
    execucao = await motor.iniciar("sem_contexto", "falso", canal="agencia")
    await motor.aguardar(execucao.id)
    assert PERSONAS_LIDAS == []
    assert sistemas[0].startswith(prompts.PERSONA_EMBUTIDA)
    assert _eventos(publicador, "prompt.loaded")[0]["origem"] == "embutido"


async def test_persona_indisponivel_cai_na_embutida_com_aviso():
    sistemas: list[str] = []
    motor, publicador = _motor(SessaoFalsa([Passo(texto="Ok.", fim=True)]), [], sistemas)
    execucao = await motor.iniciar("sem_skill", "falso", canal="central")  # não existe no gateway falso
    await motor.aguardar(execucao.id)
    assert (await motor.obter(execucao.id))["status"] == "concluida"
    assert sistemas[0].startswith(prompts.PERSONA_EMBUTIDA)
    evento = _eventos(publicador, "prompt.loaded")[0]
    assert evento["origem"] == "embutido" and "indisponível" in evento["motivo"]


def test_roteiro_fala_com_quem_esta_do_outro_lado():
    from agent.llm.roteiro import SessaoRoteiro

    assert SessaoRoteiro("com_skill", canal="agencia")._fala("imovel").startswith("Confirme com a Ana")
    assert SessaoRoteiro("com_skill", canal="central")._fala("imovel").startswith("Pergunte à Ana")
    assert SessaoRoteiro("com_skill", canal="loja")._fala("imovel").startswith("Para confirmar")


def test_bloqueio_por_ordem_e_contramao():
    from agent.incidentes import detectar

    meta = {"bussola/proveniencia": {"motivo": "fora_de_ordem"}}
    texto = "Contramão: seguradoras.cotar_seguro exige antes: risco.consultar_elegibilidade."
    [achado] = detectar("seguradoras.cotar_seguro", {}, texto, True, meta)
    assert achado["metafora"] == "Contramão" and "exige antes" in achado["descricao"]
