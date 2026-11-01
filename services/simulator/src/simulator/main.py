from fastapi import FastAPI

from bussola_comum.barramento import checar_barramento
from bussola_comum.config import ConfigBase
from bussola_comum.saude import Checagem, rota_saude


class Config(ConfigBase):
    servico_nome: str = "simulator"
    bus_url: str = "redis://bus:6379/0"


def criar_app(config: Config | None = None, checagens: dict[str, Checagem] | None = None) -> FastAPI:
    config = config or Config()
    if checagens is None:
        checagens = {"bus": checar_barramento(config.bus_url)}

    app = FastAPI(title="simulator")
    app.add_api_route("/saude", rota_saude(config.servico_nome, checagens), methods=["GET"])
    return app
