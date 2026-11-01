from bussola_comum.mcp_servidor import executar
from risco_mcp.servidor import Config, criar_servidor

executar(criar_servidor, Config())
