"""O gateway como servidor MCP: um só endereço, todas as tools e resources.

Cada chamada é roteada ao servidor de origem, recebe proveniência em `_meta`
e vira um evento `tool.called` no barramento.
"""

import time
import uuid

from mcp import types
from mcp.server.lowlevel import Server

from bussola_comum import VERSAO
from bussola_comum.dominio import agora
from bussola_comum.estado_vivo import EstadoVivo
from mcp_gateway.catalogo import Catalogo
from mcp_gateway.eventos import Publicador

CHAVE_PROVENIENCIA = "bussola/proveniencia"


def _erro(texto: str, meta: dict) -> types.CallToolResult:
    return types.CallToolResult(
        content=[types.TextContent(type="text", text=texto)], is_error=True, _meta=meta
    )


def criar_servidor_mcp(catalogo: Catalogo, publicador: Publicador, estado: EstadoVivo) -> Server:
    async def listar_tools(ctx, params) -> types.ListToolsResult:
        return types.ListToolsResult(tools=[t.tool for _, t in sorted(catalogo.tools.items())])

    async def chamar_tool(ctx, params: types.CallToolRequestParams) -> types.CallToolResult:
        chamada_id = uuid.uuid4().hex[:12]
        inicio = time.perf_counter()
        roteada = catalogo.tools.get(params.name)
        proveniencia = {
            "chamada_id": chamada_id,
            "tool": params.name,
            "servidor": roteada.upstream.nome if roteada else None,
            "instante": agora(),
        }

        motivo = None
        if roteada is None:
            resultado = _erro(f"Tool desconhecida no gateway: '{params.name}'.", {})
        elif await estado.tool_fora(params.name):
            # O apresentador desligou a tool: a rua continua no mapa, interditada.
            motivo = "desligada"
            resultado = _erro(
                f"A tool {params.name} está fora do ar no momento: trecho interditado. Tente outra rota.", {}
            )
        else:
            try:
                async with catalogo.conectar(roteada.upstream) as cliente:
                    resultado = await cliente.call_tool(roteada.nome_original, params.arguments or {})
            except Exception:  # noqa: BLE001
                resultado = _erro(
                    f"O servidor {roteada.upstream.nome} não respondeu: "
                    "trecho interditado. Tente outra rota.",
                    {},
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
            raise ValueError(f"Resource desconhecido no gateway: '{uri}'.")
        async with catalogo.conectar(alvo[0]) as cliente:
            return await cliente.read_resource(uri)

    return Server(
        "mcp-gateway",
        version=VERSAO,
        description="Banco Bússola: ponto único de acesso às tools e resources da demo.",
        on_list_tools=listar_tools,
        on_call_tool=chamar_tool,
        on_list_resources=listar_resources,
        on_read_resource=ler_resource,
    )
