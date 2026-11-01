from bussola_comum.config import ConfigBase

NOME = "contexto-mcp"


class Config(ConfigBase):
    servico_nome: str = NOME
    neo4j_uri: str = "bolt://graph:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = ""
    # Token das rotas internas usadas pelo simulador. Vazio desliga as rotas.
    simulador_token: str = ""
