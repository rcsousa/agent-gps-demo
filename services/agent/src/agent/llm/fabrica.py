"""Escolhe o provedor de LLM pela configuração (LLM_PROVIDER) ou pelo pedido da execução."""

from agent.config import Config
from agent.llm.base import ErroProvedor, SessaoLLM
from agent.llm.provedor_anthropic import SessaoAnthropic
from agent.llm.provedor_azure import SessaoAzureOpenAI
from agent.llm.roteiro import SessaoRoteiro

PROVEDORES = ("anthropic", "azure_openai", "roteiro")


def modelo_de(provedor: str, config: Config, pedido: str = "") -> str:
    """O modelo que a execução vai usar, conhecido antes de abrir a sessão (para o run.started)."""
    return {
        "anthropic": pedido or config.anthropic_model,
        "azure_openai": config.azure_openai_deployment,
        "roteiro": SessaoRoteiro.modelo,
    }.get(provedor, provedor)


def criar_sessao(
    provedor: str, modo: str, sistema: str, pedido: str, config: Config, canal: str = "app", modelo: str = ""
) -> SessaoLLM:
    if provedor == "anthropic":
        return SessaoAnthropic(
            sistema,
            pedido,
            modelo=modelo or config.anthropic_model,
            esforco=config.anthropic_effort,
            fallbacks=config.anthropic_fallbacks,
            api_key=config.anthropic_api_key,
            plataforma=config.anthropic_plataforma,
            foundry_base_url=config.anthropic_foundry_base_url,
            foundry_api_key=config.anthropic_foundry_api_key,
        )
    if provedor == "azure_openai":
        return SessaoAzureOpenAI(
            sistema,
            pedido,
            endpoint=config.azure_openai_endpoint,
            api_key=config.azure_openai_api_key,
            deployment=config.azure_openai_deployment,
            api_version=config.azure_openai_api_version,
        )
    if provedor == "roteiro":
        return SessaoRoteiro(modo, canal=canal)
    raise ErroProvedor(f"Provedor desconhecido: {provedor}. Use um de: {', '.join(PROVEDORES)}.")
