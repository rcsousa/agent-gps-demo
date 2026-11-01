import asyncio
import time
from pathlib import Path
from typing import Annotated

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException
from mcp.client.client import Client

from bussola_comum.barramento import checar_barramento
from bussola_comum.config import ConfigBase
from bussola_comum.saude import Checagem, rota_saude
from mcp_gateway.upstreams import Upstream, carregar_upstreams


class Config(ConfigBase):
    servico_nome: str = "mcp-gateway"
    gateway_token: str = ""
    bus_url: str = "redis://bus:6379/0"
    upstreams_arquivo: Path = Path(__file__).resolve().parents[2] / "config" / "upstreams.yaml"


async def _saude_upstream(cliente: httpx.AsyncClient, upstream: Upstream) -> dict:
    inicio = time.perf_counter()
    try:
        resposta = await cliente.get(upstream.url_saude)
        status = "ok" if resposta.status_code == 200 else "fora"
    except httpx.HTTPError:
        status = "fora"
    return {
        "nome": upstream.nome,
        "prefixo": upstream.prefixo,
        "status": status,
        "latencia_ms": round((time.perf_counter() - inicio) * 1000),
    }


def criar_app(config: Config | None = None, checagens: dict[str, Checagem] | None = None) -> FastAPI:
    config = config or Config()
    upstreams = {u.nome: u for u in carregar_upstreams(config.upstreams_arquivo)}
    if checagens is None:
        checagens = {"bus": checar_barramento(config.bus_url)}

    app = FastAPI(title="mcp-gateway")
    app.add_api_route("/saude", rota_saude(config.servico_nome, checagens), methods=["GET"])

    def autenticar(authorization: Annotated[str | None, Header()] = None) -> None:
        if not config.gateway_token or authorization != f"Bearer {config.gateway_token}":
            raise HTTPException(status_code=401, detail="Token do gateway inválido ou ausente.")

    @app.get("/saude/servicos", dependencies=[Depends(autenticar)])
    async def saude_servicos() -> dict:
        async with httpx.AsyncClient(timeout=2) as cliente:
            servicos = await asyncio.gather(*(_saude_upstream(cliente, u) for u in upstreams.values()))
        return {"servicos": list(servicos)}

    @app.post("/ping/{nome}", dependencies=[Depends(autenticar)])
    async def ping(nome: str) -> dict:
        """Repassa a tool `ping` ao servidor indicado, pelo protocolo MCP.
        Esqueleto da Fase 1: a agregação de tools chega na Fase 3."""
        upstream = upstreams.get(nome)
        if upstream is None:
            raise HTTPException(status_code=404, detail=f"Servidor desconhecido: {nome}")
        try:
            async with Client(upstream.url_mcp, read_timeout_seconds=5) as cliente:
                resultado = await cliente.call_tool("ping", {})
        except Exception as erro:
            raise HTTPException(status_code=502, detail=f"{nome} não respondeu: {erro}") from erro
        return {"servidor": nome, "resposta": resultado.content[0].text}

    return app
