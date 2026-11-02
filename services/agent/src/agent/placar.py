"""O placar da cena 8: regras do banco cumpridas, tempo e custo, por modo e modelo.

Duas fontes, lado a lado:
- a sessão: as execuções recentes da demo, com as regras conferidas no fim de cada uma
  (`run.finished.metricas.regras`);
- a referência: o experimento versionado com os modelos reais (Opus × Haiku, sem e com skill).
"""

import json
import pathlib
from typing import Any

REFERENCIA = pathlib.Path(__file__).parent / "dados" / "placar-referencia.json"
TERMINADAS = ("concluida", "interrompida", "erro")


def referencia() -> dict[str, Any]:
    return json.loads(REFERENCIA.read_text(encoding="utf-8"))


def _resumo(execucao: dict[str, Any]) -> dict[str, Any]:
    metricas = execucao["metricas"]
    regras = metricas.get("regras") or {}
    return {
        "id": execucao["id"],
        "modo": execucao["modo"],
        "modelo": execucao.get("modelo") or execucao.get("provedor"),
        "provedor": execucao.get("provedor"),
        "caso": metricas.get("caso", "caminho-feliz"),
        "criada_em": execucao.get("criada_em"),
        "status": execucao["status"],
        "apolice": execucao.get("apolice"),
        "cumpridas": regras.get("cumpridas", 0),
        "total": regras.get("total", 0),
        "regras": regras.get("regras", {}),
        "segundos": metricas.get("duracao_s", 0),
        "custo_usd": (metricas.get("custo_usd") or {}).get("total"),
        "bloqueios": metricas.get("bloqueios", 0),
        "tools_irrelevantes": len(metricas.get("tools_irrelevantes", [])),
    }


def sessao(execucoes: list[dict[str, Any]]) -> dict[str, Any]:
    """As execuções terminadas (mais recentes primeiro) e o agregado por modo × modelo."""
    resumos = [
        _resumo(e) for e in execucoes if e["status"] in TERMINADAS and (e["metricas"].get("regras") or {})
    ]
    grupos: dict[tuple[str, str], dict[str, Any]] = {}
    for r in resumos:
        g = grupos.setdefault(
            (r["modo"], r["modelo"]),
            {
                "modo": r["modo"],
                "modelo": r["modelo"],
                "execucoes": 0,
                "cumpridas": 0,
                "total": 0,
                "perfeitas": 0,
                "segundos": 0.0,
                "custo_usd": 0.0,
                "com_custo": 0,
            },
        )
        g["execucoes"] += 1
        g["cumpridas"] += r["cumpridas"]
        g["total"] += r["total"]
        g["perfeitas"] += r["cumpridas"] == r["total"]
        g["segundos"] += r["segundos"]
        if r["custo_usd"] is not None:
            g["custo_usd"] += r["custo_usd"]
            g["com_custo"] += 1
    agregado = [
        {
            "modo": g["modo"],
            "modelo": g["modelo"],
            "execucoes": g["execucoes"],
            "cumpridas": g["cumpridas"],
            "total": g["total"],
            "perfeitas": g["perfeitas"],
            "segundos_medio": round(g["segundos"] / g["execucoes"], 1),
            "custo_medio_usd": round(g["custo_usd"] / g["com_custo"], 4) if g["com_custo"] else None,
        }
        for g in grupos.values()
    ]
    return {"execucoes": resumos, "agregado": agregado}


def montar(execucoes: list[dict[str, Any]]) -> dict[str, Any]:
    return {"sessao": sessao(execucoes), "referencia": referencia()}
