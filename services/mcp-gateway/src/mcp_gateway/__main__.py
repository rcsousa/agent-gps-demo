import uvicorn

from bussola_comum.logs import configurar_logs
from mcp_gateway.main import Config, criar_app

config = Config()
configurar_logs(config.servico_nome, config.log_level)
uvicorn.run(criar_app(config), host="0.0.0.0", port=config.porta, log_config=None)
