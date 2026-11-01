from mcp.server.mcpserver import MCPServer

from bussola_comum.config import ConfigBase
from bussola_comum.mcp_servidor import criar_servidor_mcp

NOME = "atendimento-mcp"


class Config(ConfigBase):
    servico_nome: str = NOME


def criar_servidor() -> MCPServer:
    return criar_servidor_mcp(NOME, "Fila de especialistas humanos (o pedágio)")
