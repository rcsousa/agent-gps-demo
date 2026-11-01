from typing import Literal

from bussola_comum.config import ConfigBase


class Config(ConfigBase):
    """O agente conhece apenas o mcp-gateway (GATEWAY_URL) e o barramento (BUS_URL)."""

    servico_nome: str = "agent"
    gateway_url: str = "http://mcp-gateway:8000"
    gateway_token: str = ""
    bus_url: str = "redis://bus:6379/0"

    llm_provider: Literal["anthropic", "azure_openai"] = "anthropic"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-opus-5-5"
    anthropic_effort: Literal["low", "medium", "high", "xhigh", "max"] = "medium"
    # Fallback do lado do servidor quando o modelo recusa: ligado por padrão.
    anthropic_fallbacks: bool = True
    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_deployment: str = ""
    azure_openai_api_version: str = ""

    max_passos: int = 40

    @property
    def llm_configurado(self) -> bool:
        if self.llm_provider == "anthropic":
            return bool(self.anthropic_api_key)
        return bool(self.azure_openai_api_key and self.azure_openai_endpoint and self.azure_openai_deployment)
