"""API do simulador. Fica fora do gateway: o agente não a conhece."""

import asyncio
import contextlib
import logging

from fastapi import FastAPI, HTTPException

from bussola_comum.barramento import checar_barramento
from bussola_comum.config import ConfigBase
from bussola_comum.estado_vivo import EstadoVivo
from bussola_comum.saude import Checagem, rota_saude
from simulator.mundo import GrafoHttp, Mundo

log = logging.getLogger("simulator")


class Config(ConfigBase):
    servico_nome: str = "simulator"
    bus_url: str = "redis://bus:6379/0"
    contexto_url: str = "http://contexto-mcp:8000"
    simulador_token: str = ""


def criar_app(
    config: Config | None = None,
    checagens: dict[str, Checagem] | None = None,
    mundo: Mundo | None = None,
    passar_o_tempo: bool = True,
) -> FastAPI:
    config = config or Config()
    if checagens is None:
        checagens = {"bus": checar_barramento(config.bus_url)}
    mundo = mundo or Mundo(
        EstadoVivo.de_url(config.bus_url), GrafoHttp(config.contexto_url, config.simulador_token)
    )

    @contextlib.asynccontextmanager
    async def ciclo_de_vida(app: FastAPI):
        # O seed acabou de recarregar o grafo; o barramento também volta ao estado-base.
        await mundo.reset(grafo=False)
        tarefa = asyncio.create_task(_relogio(mundo)) if passar_o_tempo else None
        yield
        if tarefa:
            tarefa.cancel()

    app = FastAPI(title="simulator", lifespan=ciclo_de_vida)
    app.add_api_route("/saude", rota_saude(config.servico_nome, checagens), methods=["GET"])

    @app.get("/incidentes")
    async def listar() -> list[dict]:
        return await mundo.listar()

    @app.post("/incidentes/{incidente_id}/aplicar")
    async def aplicar(incidente_id: str) -> dict:
        try:
            return await mundo.aplicar(incidente_id)
        except KeyError as erro:
            raise HTTPException(404, f"Incidente desconhecido: {incidente_id}") from erro

    @app.post("/incidentes/{incidente_id}/remover")
    async def remover(incidente_id: str) -> dict:
        try:
            return await mundo.remover(incidente_id)
        except KeyError as erro:
            raise HTTPException(404, f"Incidente desconhecido: {incidente_id}") from erro

    @app.post("/reset")
    async def reset() -> dict:
        await mundo.reset()
        return {"status": "estado-base"}

    @app.get("/aprovacoes")
    async def aprovacoes() -> list[dict]:
        return await mundo.aprovacoes()

    @app.post("/aprovacoes/{ticket_id}/{decisao}")
    async def decidir(ticket_id: str, decisao: str) -> dict:
        if decisao not in ("aprovar", "recusar"):
            raise HTTPException(400, "Use aprovar ou recusar.")
        try:
            return await mundo.decidir(ticket_id, aprovar=decisao == "aprovar")
        except KeyError as erro:
            raise HTTPException(404, f"Ticket desconhecido: {ticket_id}") from erro

    return app


async def _relogio(mundo: Mundo) -> None:
    while True:
        try:
            await mundo.tique()
        except Exception:  # noqa: BLE001
            log.exception("Falha no relógio do simulador")
        await asyncio.sleep(1)
