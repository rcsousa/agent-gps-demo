from typing import Literal

from bussola_comum.config import ConfigBase


class Config(ConfigBase):
    """O agente conhece apenas o mcp-gateway (GATEWAY_URL) e o barramento (BUS_URL)."""

    servico_nome: str = "agent"
    gateway_url: str = "http://mcp-gateway:8000"
    gateway_token: str = ""
    bus_url: str = "redis://bus:6379/0"
    # Gravações das cenas para o replay offline (pasta versionada, montada como volume).
    gravacoes_dir: str = "/gravacoes"

    llm_provider: Literal["anthropic", "azure_openai"] = "anthropic"
    # Onde o Claude roda: na API da Anthropic ("api") ou no Microsoft Foundry, na Azure ("foundry").
    anthropic_plataforma: Literal["api", "foundry"] = "api"
    anthropic_api_key: str = ""
    anthropic_foundry_base_url: str = ""
    anthropic_foundry_api_key: str = ""
    # Na API, o id do modelo; no Foundry, o nome do deployment.
    anthropic_model: str = "claude-haiku-5-5"
    # Outros modelos (deployments) que uma execução pode pedir, separados por vírgula.
    anthropic_modelos: str = ""
    anthropic_effort: Literal["low", "medium", "high", "xhigh", "max"] = "medium"
    # Fallback do lado do servidor quando o modelo recusa: ligado por padrão.
    anthropic_fallbacks: bool = True
    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_deployment: str = ""
    azure_openai_api_version: str = ""

    # Preço por token, em US$, de cada modelo: {"modelo": {"entrada": ..., "saida": ...}}.
    llm_precos: dict[str, dict[str, float]] = {}
    # Cache de prompt: leitura a uma fração do preço de entrada; escrita com acréscimo.
    cache_leitura_fator: float = 0.1
    cache_escrita_fator: float = 1.25

    max_passos: int = 40

    @property
    def modelos_anthropic(self) -> list[str]:
        """O modelo padrão primeiro, depois os outros permitidos, sem repetir."""
        outros = [m.strip() for m in self.anthropic_modelos.split(",") if m.strip()]
        return list(dict.fromkeys([self.anthropic_model, *outros]))

    @property
    def llm_configurado(self) -> bool:
        if self.llm_provider == "anthropic" and self.anthropic_plataforma == "foundry":
            return bool(self.anthropic_foundry_base_url and self.anthropic_foundry_api_key)
        if self.llm_provider == "anthropic":
            return bool(self.anthropic_api_key)
        return bool(self.azure_openai_api_key and self.azure_openai_endpoint and self.azure_openai_deployment)
