from mcp.server.mcpserver import MCPServer

from bussola_comum.config import ConfigBase
from bussola_comum.mcp_servidor import criar_servidor_mcp
from skills_mcp.catalogo import carregar_catalogo
from skills_mcp.extensao import ExtensaoSkills

NOME = "skills-mcp"


class Config(ConfigBase):
    servico_nome: str = NOME


def criar_servidor() -> MCPServer:
    return criar_servidor_mcp(
        NOME,
        "Catálogo de skills-workflow (extensão io.modelcontextprotocol/skills)",
        extensoes=[ExtensaoSkills(carregar_catalogo())],
    )
