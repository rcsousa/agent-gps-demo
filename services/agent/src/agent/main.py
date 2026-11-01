"""API do agente.

Regra de arquitetura: o agente conhece apenas o mcp-gateway (GATEWAY_URL)
e o barramento de eventos (BUS_URL). Nenhum servidor de domínio aparece aqui.
"""

import logging
from typing import Literal

import httpx
from fastapi import FastAPI

from bussola_comum.barramento import checar_barramento
from bussola_comum.config import ConfigBase
from bussola_comum.saude import Checagem, rota_saude

log = logging.getLogger("agent")


class Config(ConfigBase):
    servico_nome: str = "agent"
    gateway_url: str = "http://mcp-gateway:8000"
    gateway_token: str = ""
    bus_url: str = "redis://bus:6379/0"
    llm_provider: Literal["anthropic", "azure_openai"] = "anthropic"
    anthropic_api_key: str = ""
    azure_openai_api_key: str = ""

    @property
    def llm_configurado(self) -> bool:
        chave = self.anthropic_api_key if self.llm_provider == "anthropic" else self.azure_openai_api_key
        return bool(chave)


def criar_app(config: Config | None = None, checagens: dict[str, Checagem] | None = None) -> FastAPI:
    config = config or Config()
    if checagens is None:
        checagens = {"bus": checar_barramento(config.bus_url)}
    if not config.llm_configurado:
        log.warning("Chave do provedor de LLM (%s) ausente. Ok na Fase 1.", config.llm_provider)

    app = FastAPI(title="agent")
    app.add_api_route("/saude", rota_saude(config.servico_nome, checagens), methods=["GET"])

    @app.get("/api/status")
    async def status() -> dict:
        """Estado da plataforma visto pelo agente: só pelo gateway."""
        gateway, servicos, ferramentas = "fora", [], 0
        try:
            async with httpx.AsyncClient(timeout=4) as cliente:
                resposta = await cliente.get(
                    f"{config.gateway_url}/saude/servicos",
                    headers={"Authorization": f"Bearer {config.gateway_token}"},
                )
            if resposta.status_code == 200:
                corpo = resposta.json()
                gateway, servicos, ferramentas = "ok", corpo["servicos"], corpo.get("ferramentas", 0)
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
        }

    return app
