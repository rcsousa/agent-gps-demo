"""Dados mestres do banco (dados/cadastro.yaml), vistos com o estado vivo aplicado.

Os sistemas de domínio leem daqui. Quando o simulador aplica um incidente sobre
uma entidade (por exemplo, `imovel-ana`), a visão "atual" já traz o efeito.
"""

from datetime import date
from functools import cache
from pathlib import Path
from typing import Any

import yaml
from mcp.server.mcpserver.exceptions import ToolError

from bussola_comum.estado_vivo import EstadoVivo, aplicar_efeito

ARQUIVO = Path(__file__).parent / "dados" / "cadastro.yaml"


def _texto(valor: Any) -> Any:
    """Datas do YAML viram texto ISO: as respostas das tools são JSON."""
    if isinstance(valor, date):
        return valor.isoformat()
    if isinstance(valor, dict):
        return {k: _texto(v) for k, v in valor.items()}
    if isinstance(valor, list):
        return [_texto(v) for v in valor]
    return valor


@cache
def dados() -> dict[str, dict[str, dict[str, Any]]]:
    return _texto(yaml.safe_load(ARQUIVO.read_text(encoding="utf-8")))


def registro(colecao: str, ident: str, rotulo: str) -> dict[str, Any]:
    item = dados()[colecao].get(ident)
    if item is None:
        raise ToolError(f"{rotulo} '{ident}' não encontrado.")
    return {"id": ident, **item}


async def atual(estado: EstadoVivo, colecao: str, ident: str, rotulo: str) -> dict[str, Any]:
    """Registro do cadastro com o efeito vivo (incidentes) aplicado."""
    return aplicar_efeito(registro(colecao, ident, rotulo), await estado.efeito(ident))


async def imovel_atual(estado: EstadoVivo, imovel_id: str) -> dict[str, Any]:
    imovel = await atual(estado, "imoveis", imovel_id, "Imóvel")
    imovel.setdefault("importancia_segurada", imovel["valor_estimado"])
    return imovel


def laudo(imovel_id: str) -> dict[str, Any] | None:
    """O laudo de avaliação da engenharia do banco: a fonte autoritativa do valor do imóvel."""
    item = dados()["laudos"].get(imovel_id)
    if item is None:
        return None
    return {
        "valor_avaliado": item["valor_avaliado"],
        "proveniencia": {
            "fonte": "Laudo de avaliação (Engenharia Bússola)",
            "data": item["data"],
            "responsavel": item["responsavel"],
            "confianca": "alta",
        },
    }


def imovel_do_cliente(cliente_id: str) -> str:
    return registro("clientes", cliente_id, "Cliente")["imovel"]
