"""O gateway como servidor MCP: um só endereço, todas as tools, resources e skills.

Cada chamada é roteada ao servidor de origem, recebe proveniência em `_meta`
e vira um evento `tool.called` no barramento. Com uma skill ativa
(`_meta["bussola/skill"]`), só passam as tools que ela permite.
"""

import time
import uuid
from typing import Any

from mcp import types
from mcp.server.lowlevel import Server
from mcp.shared.exceptions import MCPError

from bussola_comum import VERSAO
from bussola_comum.dominio import agora
from bussola_comum.estado_vivo import EstadoVivo
from bussola_comum.eventos import Publicador
from bussola_comum.skills import (
    CHAVE_EXECUCAO,
    CHAVE_SKILL_ATIVA,
    IDENTIFICADOR,
    ParamsListar,
    ParamsObter,
    ResultadoListar,
    ResultadoObter,
)
from mcp_gateway.catalogo import Catalogo

CHAVE_PROVENIENCIA = "bussola/proveniencia"
PARAMETROS_INVALIDOS = -32602


def _erro(texto: str) -> types.CallToolResult:
    return types.CallToolResult(content=[types.TextContent(type="text", text=texto)], is_error=True)


def _meta_de(params: types.CallToolRequestParams, chave: str) -> str | None:
    meta: Any = params.meta or {}
    if not isinstance(meta, dict):
        meta = meta.model_dump(by_alias=True)
    return meta.get(chave)


def criar_servidor_mcp(catalogo: Catalogo, publicador: Publicador, estado: EstadoVivo) -> Server:
    async def listar_tools(ctx, params) -> types.ListToolsResult:
        return types.ListToolsResult(tools=[t.tool for _, t in sorted(catalogo.tools.items())])

    async def governanca(nome: str, skill: str | None) -> tuple[str | None, str | None]:
        """(motivo, mensagem) de bloqueio, ou (None, None) se a chamada pode seguir."""
        if await estado.tool_fora(nome):
            # O apresentador desligou a tool: a rua continua no mapa, interditada.
            return (
                "desligada",
                f"A tool {nome} está fora do ar no momento: trecho interditado. Tente outra rota.",
            )
        if skill is None:
            return None, None  # Sem skill declarada, o gateway não restringe (cenas 2 e 3).
        permitidas = catalogo.tools_da_skill(skill)
        if permitidas is None:
            return "skill_desconhecida", f"Skill desconhecida no gateway: {skill}."
        if nome not in permitidas:
            return "fora_da_skill", (
                f"Contramão: a skill {skill} não permite a tool {nome}. "
                f"Permitidas: {', '.join(sorted(permitidas))}."
            )
        return None, None

    async def chamar_tool(ctx, params: types.CallToolRequestParams) -> types.CallToolResult:
        inicio = time.perf_counter()
        roteada = catalogo.tools.get(params.name)
        skill = _meta_de(params, CHAVE_SKILL_ATIVA)
        proveniencia = {
            "chamada_id": uuid.uuid4().hex[:12],
            "tool": params.name,
            "servidor": roteada.upstream.nome if roteada else None,
            "skill": skill,
            "execucao_id": _meta_de(params, CHAVE_EXECUCAO),
            "instante": agora(),
        }

        motivo = None
        if roteada is None:
            resultado = _erro(f"Tool desconhecida no gateway: '{params.name}'.")
        else:
            motivo, mensagem = await governanca(params.name, skill)
            if motivo:
                resultado = _erro(mensagem)
            else:
                try:
                    async with catalogo.conectar(roteada.upstream) as cliente:
                        resultado = await cliente.call_tool(roteada.nome_original, params.arguments or {})
                except Exception:  # noqa: BLE001
                    resultado = _erro(
                        f"O servidor {roteada.upstream.nome} não respondeu: "
                        "trecho interditado. Tente outra rota."
                    )

        proveniencia |= {
            "duracao_ms": round((time.perf_counter() - inicio) * 1000),
            "status": "erro" if resultado.is_error else "ok",
            **({"motivo": motivo} if motivo else {}),
        }
        resultado.meta = {**(resultado.meta or {}), CHAVE_PROVENIENCIA: proveniencia}
        await publicador.publicar(
            "tool.called",
            {
                **proveniencia,
                "argumentos": params.arguments or {},
                "erro": resultado.content[0].text if resultado.is_error and resultado.content else None,
            },
        )
        return resultado

    async def listar_resources(ctx, params) -> types.ListResourcesResult:
        return types.ListResourcesResult(resources=[r for _, (_, r) in sorted(catalogo.resources.items())])

    async def ler_resource(ctx, params: types.ReadResourceRequestParams) -> types.ReadResourceResult:
        uri = str(params.uri)
        alvo = catalogo.resources.get(uri)
        if alvo is None:
            raise MCPError(code=PARAMETROS_INVALIDOS, message=f"Resource desconhecido no gateway: '{uri}'.")
        async with catalogo.conectar(alvo[0]) as cliente:
            resultado = await cliente.read_resource(uri)
        if uri.startswith("skill://"):
            await publicador.publicar("resource.read", {"uri": uri, "servidor": alvo[0].nome})
        return resultado

    # --- Extensão io.modelcontextprotocol/skills (SEP-2640) --------------------------
    # As entradas saem como vieram dos servidores: os digests valem ponta a ponta.

    async def listar_skills(ctx, params: ParamsListar) -> ResultadoListar:
        entradas = [entrada for _, (_, entrada) in sorted(catalogo.skills.items())]
        await publicador.publicar("skills.listed", {"skills": [e["uri"] for e in entradas]})
        return ResultadoListar(skills=entradas)

    async def obter_skill(ctx, params: ParamsObter) -> ResultadoObter:
        alvo = catalogo.skills.get(params.uri)
        if alvo is None:
            raise MCPError(code=PARAMETROS_INVALIDOS, message=f"Skill desconhecida: {params.uri}")
        return ResultadoObter(skill=alvo[1])

    servidor = Server(
        "mcp-gateway",
        version=VERSAO,
        description="Banco Bússola: ponto único de acesso às tools, resources e skills da demo.",
        on_list_tools=listar_tools,
        on_call_tool=chamar_tool,
        on_list_resources=listar_resources,
        on_read_resource=ler_resource,
    )
    servidor.add_request_handler("skills/list", ParamsListar, listar_skills)
    servidor.add_request_handler("skills/get", ParamsObter, obter_skill)
    servidor.extensions[IDENTIFICADOR] = {}
    return servidor
