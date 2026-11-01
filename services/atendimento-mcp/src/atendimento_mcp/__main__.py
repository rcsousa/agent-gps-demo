from atendimento_mcp.servidor import Config, criar_servidor
from bussola_comum.mcp_servidor import executar

executar(criar_servidor, Config())
