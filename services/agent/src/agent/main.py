"""API do agente.

Regra de arquitetura: o agente conhece apenas o mcp-gateway (GATEWAY_URL)
e o barramento de eventos (BUS_URL). Nenhum servidor de domínio aparece aqui.
"""

import json
import logging
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from redis.asyncio import Redis
from sse_starlette.sse import EventSourceResponse

from agent.config import Config
from agent.execucao import MODOS, Motor
from agent.llm.fabrica import PROVEDORES
from bussola_comum.barramento import checar_barramento
from bussola_comum.cliente_mcp import conectar
from bussola_comum.eventos import STREAM, PublicadorRedis, decodificar
from bussola_comum.saude import Checagem, rota_saude

log = logging.getLogger("agent")


class PedidoExecucao(BaseModel):
    modo: str
    provedor: str | None = None
    pedido: str | None = None


class RespostaCliente(BaseModel):
    texto: str


def criar_app(
    config: Config | None = None,
    checagens: dict[str, Checagem] | None = None,
    motor: Motor | None = None,
    redis: Redis | None = None,
) -> FastAPI:
    config = config or Config()
    if checagens is None:
        checagens = {"bus": checar_barramento(config.bus_url)}
    if not config.llm_configurado:
        log.warning("Chave do provedor de LLM (%s) ausente: só o provedor roteiro roda.", config.llm_provider)
    redis = redis or Redis.from_url(config.bus_url, decode_responses=True)
    motor = motor or Motor(
        config,
        redis,
        PublicadorRedis(redis, "agent"),
        lambda: conectar(f"{config.gateway_url}/mcp", config.gateway_token),
    )

    app = FastAPI(title="agent")
    app.add_api_route("/saude", rota_saude(config.servico_nome, checagens), methods=["GET"])

    @app.get("/api/status")
    async def status() -> dict:
        """Estado da plataforma visto pelo agente: só pelo gateway."""
        gateway, servicos, ferramentas, ferramentas_fora, skills = "fora", [], 0, 0, 0
        try:
            async with httpx.AsyncClient(timeout=4) as cliente:
                resposta = await cliente.get(
                    f"{config.gateway_url}/saude/servicos",
                    headers={"Authorization": f"Bearer {config.gateway_token}"},
                )
            if resposta.status_code == 200:
                corpo = resposta.json()
                gateway, servicos = "ok", corpo["servicos"]
                ferramentas, ferramentas_fora = corpo.get("ferramentas", 0), corpo.get("ferramentas_fora", 0)
                skills = corpo.get("skills", 0)
        except httpx.HTTPError:
            pass

        try:
            barramento = "ok" if await checagens["bus"]() else "fora"
        except Exception:
            barramento = "fora"

        return {
            "gateway": gateway,
            "barramento": barramento,
            "llm": {"provedor": config.llm_provider, "configurado": config.llm_configurado},
            "servicos": servicos,
            "ferramentas": ferramentas,
            "ferramentas_fora": ferramentas_fora,
            "skills": skills,
        }

    # --- Execuções ------------------------------------------------------------------

    @app.post("/api/execucoes", status_code=201)
    async def iniciar(pedido: PedidoExecucao) -> dict:
        if pedido.modo not in MODOS:
            raise HTTPException(400, f"Modo desconhecido: {pedido.modo}. Use um de: {', '.join(MODOS)}.")
        if pedido.provedor and pedido.provedor not in PROVEDORES:
            raise HTTPException(
                400, f"Provedor desconhecido: {pedido.provedor}. Use um de: {', '.join(PROVEDORES)}."
            )
        execucao = await motor.iniciar(pedido.modo, pedido.provedor, pedido.pedido)
        return {"id": execucao.id, "modo": execucao.modo, "provedor": execucao.provedor}

    @app.get("/api/execucoes")
    async def listar() -> list[dict]:
        return await motor.listar()

    @app.get("/api/execucoes/{ident}")
    async def obter(ident: str) -> dict:
        execucao = await motor.obter(ident)
        if execucao is None:
            raise HTTPException(404, "Execução não encontrada.")
        return execucao

    @app.post("/api/execucoes/{ident}/resposta")
    async def responder(ident: str, resposta: RespostaCliente) -> dict:
        """O apresentador responde pela cliente."""
        if not motor.responder(ident, resposta.texto):
            raise HTTPException(409, "Não há pergunta pendente para esta execução.")
        return {"ok": True}

    @app.get("/api/execucoes/{ident}/eventos")
    async def eventos(ident: str) -> EventSourceResponse:
        """Eventos da execução desde o início, e depois ao vivo, até o run.finished."""
        execucao = await motor.obter(ident)
        if execucao is None:
            raise HTTPException(404, "Execução não encontrada.")

        async def fluxo() -> Any:
            cursor = execucao["cursor_eventos"]
            while True:
                # Bloqueio curto (menor que o timeout de leitura do Redis); volta vazia vira keep-alive.
                lotes = await redis.xread({STREAM: cursor}, block=2000, count=100)
                if not lotes:
                    yield {"comment": "aguardando"}
                    continue
                for cursor, campos in lotes[0][1]:
                    evento = decodificar(campos)
                    if evento["dados"].get("execucao_id") != ident:
                        continue
                    yield {
                        "event": evento["tipo"],
                        "id": cursor,
                        "data": json.dumps(evento, ensure_ascii=False),
                    }
                    if evento["tipo"] == "run.finished":
                        return

        return EventSourceResponse(fluxo())

    return app
