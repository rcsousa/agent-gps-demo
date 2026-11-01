"""Catálogo de incidentes (incidentes.yaml) e a aplicação dos efeitos no mundo."""

from datetime import date, timedelta
from functools import cache
from pathlib import Path
from typing import Any, Literal, Protocol

import yaml
from pydantic import BaseModel

ARQUIVO = Path(__file__).resolve().parents[2] / "incidentes.yaml"


class Efeito(BaseModel):
    entidade: str
    estado: dict[str, Any] = {}
    atributos: dict[str, Any] = {}
    proveniencia: dict[str, Any] = {}
    relacoes_adicionar: list[tuple[str, str, str]] = []


class Incidente(BaseModel):
    id: str
    nome: str
    metafora: str
    reacao_esperada: str
    efeitos: list[Efeito]


@cache
def catalogo() -> dict[str, Incidente]:
    dados = yaml.safe_load(ARQUIVO.read_text(encoding="utf-8"))
    return {i["id"]: Incidente(**i) for i in dados["incidentes"]}


def _datas(valor: Any, hoje: date) -> Any:
    """Troca $hoje, $ontem e $daqui_um_ano pela data real do momento da aplicação."""
    trocas = {
        "$hoje": hoje.isoformat(),
        "$ontem": (hoje - timedelta(days=1)).isoformat(),
        "$daqui_um_ano": (hoje + timedelta(days=365)).isoformat(),
    }
    if isinstance(valor, str):
        return trocas.get(valor, valor)
    if isinstance(valor, date):
        return valor.isoformat()
    if isinstance(valor, dict):
        return {k: _datas(v, hoje) for k, v in valor.items()}
    if isinstance(valor, list):
        return [_datas(v, hoje) for v in valor]
    return valor


def efeitos_concretos(incidente: Incidente, hoje: date | None = None) -> list[dict[str, Any]]:
    return [_datas(e.model_dump(), hoje or date.today()) for e in incidente.efeitos]


class Grafo(Protocol):
    """Rotas internas do contexto-mcp. O simulador nunca toca no Neo4j direto."""

    async def aplicar(self, efeitos: list[dict[str, Any]]) -> None: ...
    async def reset(self) -> None: ...


Acao = Literal["aplicado", "removido", "reset", "aprovacao", "renovacao", "tool"]
