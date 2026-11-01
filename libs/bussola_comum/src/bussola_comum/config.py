"""Configuração base lida de variáveis de ambiente."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class ConfigBase(BaseSettings):
    """Campos comuns a todos os serviços. Cada serviço estende esta classe."""

    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    servico_nome: str = "servico"
    log_level: str = "INFO"
    porta: int = 8000
