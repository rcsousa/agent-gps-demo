"""Base dos servidores MCP de domínio (cliente, consentimento, risco...)."""

import uuid
from datetime import UTC, datetime

from mcp.server.mcpserver import MCPServer

from bussola_comum.barramento import checar_barramento
from bussola_comum.config import ConfigBase
from bussola_comum.estado_vivo import EstadoVivo
from bussola_comum.mcp_servidor import criar_servidor_mcp
from bussola_comum.saude import Checagem


class ConfigDominio(ConfigBase):
    bus_url: str = "redis://bus:6379/0"


def preparar_dominio(
    nome: str,
    descricao: str,
    config: ConfigDominio,
    estado: EstadoVivo | None = None,
    checagens: dict[str, Checagem] | None = None,
) -> tuple[MCPServer, EstadoVivo]:
    """Servidor MCP com /saude (incluindo o barramento) e o acesso ao estado vivo."""
    if checagens is None:
        checagens = {"bus": checar_barramento(config.bus_url)}
    return criar_servidor_mcp(nome, descricao, checagens), estado or EstadoVivo.de_url(config.bus_url)


def agora() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def novo_id(prefixo: str) -> str:
    return f"{prefixo}-{uuid.uuid4().hex[:8]}"


def reais(valor: float, centavos: bool = True) -> str:
    """Valor em reais no formato brasileiro: reais(1234.5) -> 'R$ 1.234,50'."""
    texto = f"{valor:,.2f}" if centavos else f"{valor:,.0f}"
    return "R$ " + texto.replace(",", "_").replace(".", ",").replace("_", ".")
