from mcp.server.mcpserver import MCPServer
from neo4j import AsyncGraphDatabase

from bussola_comum.config import ConfigBase
from bussola_comum.mcp_servidor import criar_servidor_mcp
from bussola_comum.saude import Checagem

NOME = "contexto-mcp"


class Config(ConfigBase):
    servico_nome: str = NOME
    neo4j_uri: str = "bolt://graph:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = ""


def checar_grafo(config: Config) -> Checagem:
    async def checar() -> bool:
        async with AsyncGraphDatabase.driver(
            config.neo4j_uri,
            auth=(config.neo4j_user, config.neo4j_password),
            connection_timeout=2,
        ) as driver:
            await driver.verify_connectivity()
        return True

    return checar


def criar_servidor(checagens: dict[str, Checagem] | None = None) -> MCPServer:
    if checagens is None:
        checagens = {"graph": checar_grafo(Config())}
    return criar_servidor_mcp(
        NOME,
        "Camada de contexto: ontologia, estado vivo, regras e proveniência",
        checagens,
    )
