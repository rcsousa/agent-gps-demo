"""Fábrica dos servidores MCP de domínio.

Todos usam o SDK oficial (MCPServer), transporte streamable HTTP em /mcp,
e expõem /saude para o healthcheck.
"""

from collections.abc import Callable, Sequence

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
    return mcp


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
