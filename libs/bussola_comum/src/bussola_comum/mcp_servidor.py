"""Fábrica dos servidores MCP de domínio.

Todos usam o SDK oficial (MCPServer), transporte streamable HTTP em /mcp,
e expõem /saude para o healthcheck.
"""

import inspect
import json
import textwrap
from collections.abc import Callable, Sequence
from pathlib import Path

import uvicorn
from mcp.server.extension import Extension
from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette

from bussola_comum import VERSAO
from bussola_comum.config import ConfigBase
from bussola_comum.logs import configurar_logs
from bussola_comum.saude import Checagem, rota_saude


def criar_servidor_mcp(
    nome: str,
    descricao: str,
    checagens: dict[str, Checagem] | None = None,
    extensoes: Sequence[Extension] = (),
) -> MCPServer:
    """Servidor MCP com a tool `ping` e a rota /saude."""
    mcp = MCPServer(name=nome, description=descricao, version=VERSAO, extensions=list(extensoes))

    @mcp.tool(description="Confirma que o servidor responde. Esqueleto da Fase 1.")
    def ping() -> str:
        return f"pong de {nome}"

    mcp.custom_route("/saude", methods=["GET"])(rota_saude(nome, checagens))
    _servir_fonte(mcp, nome)
    return mcp


def _relativo(arquivo: str) -> str:
    """Caminho a partir da raiz do repositório (libs/... ou services/...)."""
    partes = Path(arquivo).parts
    inicio = next((i for i, p in enumerate(partes) if p in ("libs", "services")), 0)
    return "/".join(partes[inicio:])


def registrar_fonte(mcp: MCPServer, tipo: str, nome: str, texto: str, arquivo: str) -> None:
    """Fonte que não é uma função Python (ex.: o .md de um prompt de canal)."""
    mcp.fontes[(tipo, nome)] = {
        "arquivo": _relativo(arquivo),
        "linha": 1,
        "linguagem": "markdown",
        "texto": texto,
    }


def _servir_fonte(mcp: MCPServer, nome: str) -> None:
    """Template `fonte://<servidor>/{tipo}/{nome}`: o código de cada tool ou prompt, para o dashboard.

    É um template, não um resource listado: não entra no catálogo que o agente recebe,
    e o LLM nunca vê código.
    """
    mcp.fontes = {}

    @mcp.resource(
        f"fonte://{nome}/{{tipo}}/{{alvo}}",
        name="fonte",
        description="Código-fonte de uma tool ou prompt deste servidor (uso do dashboard).",
        mime_type="application/json",
    )
    def fonte(tipo: str, alvo: str) -> str:
        if (tipo, alvo) in mcp.fontes:
            return json.dumps({"tipo": tipo, "nome": alvo, **mcp.fontes[(tipo, alvo)]}, ensure_ascii=False)
        gerente = {"tool": mcp._tool_manager.get_tool, "prompt": mcp._prompt_manager.get_prompt}.get(tipo)
        item = gerente(alvo) if gerente else None
        if item is None:
            raise ValueError(f"{tipo} '{alvo}' não existe em {nome}.")
        linhas, linha = inspect.getsourcelines(item.fn)
        return json.dumps(
            {
                "tipo": tipo,
                "nome": alvo,
                "arquivo": _relativo(inspect.getsourcefile(item.fn) or ""),
                "linha": linha,
                "linguagem": "python",
                "texto": textwrap.dedent("".join(linhas)),
            },
            ensure_ascii=False,
        )


def criar_app(mcp: MCPServer) -> Starlette:
    """App ASGI do servidor. O session manager só inicia uma vez por app,
    então cada teste ou execução precisa de um app novo."""
    return mcp.streamable_http_app(
        stateless_http=True,
        json_response=True,
        # Rede interna do compose: os hosts são nomes de serviço, não localhost.
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
        host="0.0.0.0",
    )


def executar(fabrica: Callable[[], MCPServer], config: ConfigBase) -> None:
    configurar_logs(config.servico_nome, config.log_level)
    uvicorn.run(criar_app(fabrica()), host="0.0.0.0", port=config.porta, log_config=None)
