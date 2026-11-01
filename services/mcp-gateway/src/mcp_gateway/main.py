"""App do gateway: MCP agregado em /mcp, saúde em /saude e /saude/servicos."""

import asyncio
import contextlib
import logging
import time
from pathlib import Path

import httpx
from mcp.server.transport_security import TransportSecuritySettings
from redis.asyncio import Redis
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.types import ASGIApp, Receive, Scope, Send

from bussola_comum.barramento import checar_barramento
from bussola_comum.config import ConfigBase
from bussola_comum.estado_vivo import EstadoVivo
from bussola_comum.eventos import Publicador, PublicadorRedis
from bussola_comum.saude import Checagem, rota_saude
from mcp_gateway.catalogo import Catalogo, Conector, conector_http
from mcp_gateway.servidor_mcp import criar_servidor_mcp
from mcp_gateway.upstreams import Upstream, carregar_upstreams

log = logging.getLogger("mcp-gateway")


class Config(ConfigBase):
    servico_nome: str = "mcp-gateway"
    gateway_token: str = ""
    bus_url: str = "redis://bus:6379/0"
    upstreams_arquivo: Path = Path(__file__).resolve().parents[2] / "config" / "upstreams.yaml"
    intervalo_catalogo_s: float = 30.0


class ExigeToken:
    """Só quem apresenta o token do gateway fala MCP com ele."""

    def __init__(self, app: ASGIApp, token: str, prefixos: tuple[str, ...]) -> None:
        self.app, self.token, self.prefixos = app, token, prefixos

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["path"].startswith(self.prefixos):
            cabecalho = dict(scope["headers"]).get(b"authorization", b"").decode()
            if not self.token or cabecalho != f"Bearer {self.token}":
                resposta = JSONResponse({"erro": "Token do gateway inválido ou ausente."}, status_code=401)
                await resposta(scope, receive, send)
                return
        await self.app(scope, receive, send)


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


def criar_app(
    config: Config | None = None,
    checagens: dict[str, Checagem] | None = None,
    conectar: Conector = conector_http,
    publicador: Publicador | None = None,
    estado: EstadoVivo | None = None,
) -> Starlette:
    config = config or Config()
    if checagens is None:
        checagens = {"bus": checar_barramento(config.bus_url)}
    catalogo = Catalogo(carregar_upstreams(config.upstreams_arquivo), conectar)
    publicador = publicador or PublicadorRedis(
        Redis.from_url(config.bus_url, decode_responses=True), "mcp-gateway"
    )
    estado = estado or EstadoVivo.de_url(config.bus_url)

    async def saude_servicos(request: Request) -> JSONResponse:
        async with httpx.AsyncClient(timeout=2) as cliente:
            servicos = await asyncio.gather(*(_saude_upstream(cliente, u) for u in catalogo.upstreams))
        fora = await estado.tools_fora()
        for servico, upstream in zip(servicos, catalogo.upstreams, strict=True):
            servico["ferramentas"] = catalogo.ferramentas_de(upstream, fora)
        return JSONResponse(
            {
                "servicos": list(servicos),
                "ferramentas": len(catalogo.tools),
                "ferramentas_fora": len(fora & set(catalogo.tools)),
                "skills": len(catalogo.skills),
            }
        )

    app = criar_servidor_mcp(catalogo, publicador, estado).streamable_http_app(
        stateless_http=True,
        json_response=True,
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
        host="0.0.0.0",
        custom_starlette_routes=[
            Route("/saude", rota_saude(config.servico_nome, checagens), methods=["GET"]),
            Route("/saude/servicos", saude_servicos, methods=["GET"]),
        ],
    )
    app.state.catalogo = catalogo

    original = app.router.lifespan_context

    async def manter_catalogo() -> None:
        while True:
            await catalogo.atualizar()
            # Enquanto algum servidor estiver fora, tenta de novo mais cedo.
            espera = config.intervalo_catalogo_s if all(catalogo.disponiveis.values()) else 2.0
            await asyncio.sleep(espera)

    @contextlib.asynccontextmanager
    async def ciclo_de_vida(app: Starlette):
        async with original(app):
            await catalogo.atualizar()
            log.info(
                "Catálogo carregado: %d tools, %d resources.", len(catalogo.tools), len(catalogo.resources)
            )
            tarefa = asyncio.create_task(manter_catalogo())
            try:
                yield
            finally:
                tarefa.cancel()

    app.router.lifespan_context = ciclo_de_vida
    app.add_middleware(ExigeToken, token=config.gateway_token, prefixos=("/mcp", "/saude/servicos"))
    return app
