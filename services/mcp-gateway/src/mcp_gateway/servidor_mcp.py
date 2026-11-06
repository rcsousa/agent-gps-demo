"""O gateway como servidor MCP: um só endereço, todas as tools, prompts, resources e skills.

Cada chamada é roteada ao servidor de origem, recebe proveniência em `_meta`
e vira um evento `tool.called` no barramento. Com uma skill ativa
(`_meta["bussola/skill"]`), só passam as tools que ela permite, e na ordem
que o workflow dela exige (pré-requisitos por execução).
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
ERRO_INTERNO = -32603
LIMITE_DO_RESULTADO = 2000  # caracteres do resultado de uma tool no evento tool.called


def _erro(texto: str) -> types.CallToolResult:
    return types.CallToolResult(content=[types.TextContent(type="text", text=texto)], is_error=True)


def _meta_de(params: types.RequestParams, chave: str) -> str | None:
    meta: Any = params.meta or {}
    if not isinstance(meta, dict):
        meta = meta.model_dump(by_alias=True)
    return meta.get(chave)


def criar_servidor_mcp(catalogo: Catalogo, publicador: Publicador, estado: EstadoVivo) -> Server:
    async def listar_tools(ctx, params) -> types.ListToolsResult:
        tools = [t.tool for _, t in sorted(catalogo.tools.items())]
        if params is not None and (execucao := _meta_de(params, CHAVE_EXECUCAO)):
            await publicador.publicar("tools.listed", {"execucao_id": execucao, "quantidade": len(tools)})
        return types.ListToolsResult(tools=tools)

    # --8<-- [start:governanca]
    async def governanca(nome: str, skill: str | None, execucao: str | None) -> tuple[str | None, str | None]:
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
        workflow = catalogo.workflows.get(skill)
        if workflow is None:
            return None, None
        if not execucao:
            # A ordem só existe dentro de uma execução: sem ela, não há como saber o que já aconteceu.
            return "execucao_nao_identificada", (
                f'A skill {skill} tem ordem garantida: informe a execução em _meta["{CHAVE_EXECUCAO}"].'
            )
        if falta := workflow.faltando(nome, await estado.fatos(execucao)):
            return "fora_de_ordem", f"Contramão: {falta}. Faça isso antes e tente de novo."
        return None, None

    # --8<-- [end:governanca]

    # --8<-- [start:chamada]
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
        execucao = proveniencia["execucao_id"]
        if roteada is None:
            resultado = _erro(f"Tool desconhecida no gateway: '{params.name}'.")
        else:
            motivo, mensagem = await governanca(params.name, skill, execucao)
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
        if execucao and not resultado.is_error:
            # O que deu certo vira fato da execução: é o que os pré-requisitos do workflow consultam.
            conteudo = resultado.structured_content
            await estado.registrar_fato(
                execucao, params.name, conteudo if isinstance(conteudo, dict) else None
            )
        texto = getattr(resultado.content[0], "text", "") if resultado.content else ""
        await publicador.publicar(
            "tool.called",
            {
                **proveniencia,
                "argumentos": params.arguments or {},
                "erro": texto if resultado.is_error else None,
                # O Raio-X mostra o que voltou (resumido): nada é escondido do público técnico.
                "resultado": None if resultado.is_error else texto[:LIMITE_DO_RESULTADO],
            },
        )
        return resultado

    # --8<-- [end:chamada]

    async def listar_prompts(ctx, params) -> types.ListPromptsResult:
        return types.ListPromptsResult(prompts=[p.prompt for _, p in sorted(catalogo.prompts.items())])

    async def obter_prompt(ctx, params: types.GetPromptRequestParams) -> types.GetPromptResult:
        """Roteia o prompt ao servidor de origem, com proveniência e o evento prompt.read."""
        inicio = time.perf_counter()
        roteado = catalogo.prompts.get(params.name)
        if roteado is None:
            raise MCPError(
                code=PARAMETROS_INVALIDOS, message=f"Prompt desconhecido no gateway: '{params.name}'."
            )
        proveniencia = {
            "chamada_id": uuid.uuid4().hex[:12],
            "prompt": params.name,
            "servidor": roteado.upstream.nome,
            "execucao_id": _meta_de(params, CHAVE_EXECUCAO),
            "instante": agora(),
        }
        erro = None
        try:
            async with catalogo.conectar(roteado.upstream) as cliente:
                resultado = await cliente.get_prompt(roteado.nome_original, params.arguments or {})
        except Exception:  # noqa: BLE001
            erro = f"O servidor {roteado.upstream.nome} não respondeu: trecho interditado."
        proveniencia |= {
            "duracao_ms": round((time.perf_counter() - inicio) * 1000),
            "status": "erro" if erro else "ok",
        }
        await publicador.publicar(
            "prompt.read", {**proveniencia, "argumentos": params.arguments or {}, "erro": erro}
        )
        if erro:
            raise MCPError(code=ERRO_INTERNO, message=erro)
        resultado.meta = {**(resultado.meta or {}), CHAVE_PROVENIENCIA: proveniencia}
        return resultado

    async def listar_resources(ctx, params) -> types.ListResourcesResult:
        return types.ListResourcesResult(resources=[r for _, (_, r) in sorted(catalogo.resources.items())])

    async def ler_resource(ctx, params: types.ReadResourceRequestParams) -> types.ReadResourceResult:
        uri = str(params.uri)
        alvo = catalogo.resources.get(uri)
        if alvo is None and uri.startswith("fonte://"):
            # Código-fonte para o dashboard: template de cada servidor, fora do catálogo do agente.
            upstream = catalogo.upstream(uri.removeprefix("fonte://").split("/", 1)[0])
            alvo = (upstream, None) if upstream else None
        if alvo is None:
            raise MCPError(code=PARAMETROS_INVALIDOS, message=f"Resource desconhecido no gateway: '{uri}'.")
        inicio = time.perf_counter()
        async with catalogo.conectar(alvo[0]) as cliente:
            resultado = await cliente.read_resource(uri)
        if uri.startswith("skill://"):
            await publicador.publicar(
                "resource.read",
                {
                    "uri": uri,
                    "servidor": alvo[0].nome,
                    "execucao_id": _meta_de(params, CHAVE_EXECUCAO),
                    "skill": _meta_de(params, CHAVE_SKILL_ATIVA),
                    "duracao_ms": round((time.perf_counter() - inicio) * 1000),
                    "tamanho": sum(len(getattr(c, "text", "") or "") for c in resultado.contents),
                },
            )
        return resultado

    # --8<-- [start:skills]
    # --- Extensão io.modelcontextprotocol/skills (SEP-2640) --------------------------
    # As entradas saem como vieram dos servidores: os digests valem ponta a ponta.

    async def listar_skills(ctx, params: ParamsListar) -> ResultadoListar:
        entradas = [entrada for _, (_, entrada) in sorted(catalogo.skills.items())]
        await publicador.publicar(
            "skills.listed",
            {"skills": [e["uri"] for e in entradas], "execucao_id": _meta_de(params, CHAVE_EXECUCAO)},
        )
        return ResultadoListar(skills=entradas)

    async def obter_skill(ctx, params: ParamsObter) -> ResultadoObter:
        alvo = catalogo.skills.get(params.uri)
        if alvo is None:
            raise MCPError(code=PARAMETROS_INVALIDOS, message=f"Skill desconhecida: {params.uri}")
        await publicador.publicar(
            "skill.read", {"uri": params.uri, "execucao_id": _meta_de(params, CHAVE_EXECUCAO)}
        )
        return ResultadoObter(skill=alvo[1])

    servidor = Server(
        "mcp-gateway",
        version=VERSAO,
        description="Banco Bússola: ponto único de acesso às tools, prompts, resources e skills da demo.",
        on_list_tools=listar_tools,
        on_call_tool=chamar_tool,
        on_list_prompts=listar_prompts,
        on_get_prompt=obter_prompt,
        on_list_resources=listar_resources,
        on_read_resource=ler_resource,
    )
    servidor.add_request_handler("skills/list", ParamsListar, listar_skills)
    servidor.add_request_handler("skills/get", ParamsObter, obter_skill)
    servidor.extensions[IDENTIFICADOR] = {}
    # --8<-- [end:skills]
    return servidor
