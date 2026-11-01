from pathlib import Path

import yaml
from pydantic import BaseModel


class Upstream(BaseModel):
    nome: str
    prefixo: str
    url: str

    @property
    def url_mcp(self) -> str:
        return f"{self.url}/mcp"

    @property
    def url_saude(self) -> str:
        return f"{self.url}/saude"


def carregar_upstreams(caminho: Path) -> list[Upstream]:
    dados = yaml.safe_load(caminho.read_text(encoding="utf-8")) or {}
    return [Upstream(**s) for s in dados.get("servidores", [])]
