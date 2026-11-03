"""A alternativa ao SSE: consulta por lotes, com os mesmos ids do stream e sem repetir eventos."""

import asyncio
import json

from agent.entrega import (
    CABECALHOS_SSE,
    PREENCHIMENTO,
    cursor_valido,
    lote_da_execucao,
    lote_da_gravacao,
)
from bussola_comum.eventos import STREAM


def _campos(tipo: str, execucao: str) -> dict[str, str]:
    return {
        "tipo": tipo,
        "origem": "agent",
        "instante": "2026-11-03T10:00:00+00:00",
        "dados": json.dumps({"execucao_id": execucao}),
    }


class RedisFalso:
    """Só o xread: devolve as entradas depois do cursor, como o Redis faz."""

    def __init__(self, entradas: list[tuple[str, dict[str, str]]]):
        self.entradas = entradas
        self.pedidos: list[tuple[str, int, int]] = []

    async def xread(self, streams: dict[str, str], block: int, count: int):
        cursor = streams[STREAM]
        self.pedidos.append((cursor, block, count))
        chave = tuple(int(p) for p in cursor.split("-"))
        depois = [(i, c) for i, c in self.entradas if tuple(int(p) for p in i.split("-")) > chave]
        return [[STREAM, depois[:count]]] if depois else []


ENTRADAS = [
    ("1-0", _campos("run.started", "e1")),
    ("2-0", _campos("tool.called", "outra")),
    ("3-0", _campos("step.started", "e1")),
    ("4-0", _campos("run.finished", "e1")),
    ("5-0", _campos("run.started", "e2")),
]


def _lote(redis, cursor="0-0", ident="e1"):
    return asyncio.run(lote_da_execucao(redis, ident, cursor, espera_ms=10))


def test_lote_filtra_a_execucao_e_para_no_fim():
    lote = _lote(RedisFalso(ENTRADAS))
    assert [e["id"] for e in lote["eventos"]] == ["1-0", "3-0", "4-0"]
    assert lote["eventos"][0]["evento"]["tipo"] == "run.started"
    assert lote["fim"] is True and lote["cursor"] == "4-0"


def test_continua_do_cursor_sem_repetir():
    redis = RedisFalso(ENTRADAS)
    lote = _lote(redis, cursor="1-0")
    assert [e["id"] for e in lote["eventos"]] == ["3-0", "4-0"]
    assert redis.pedidos[0][0] == "1-0"


def test_cursor_avanca_sobre_eventos_de_outras_execucoes():
    # Só o evento de outra execução chegou: o lote vem vazio, mas a próxima consulta não o relê.
    lote = _lote(RedisFalso(ENTRADAS[:2]), cursor="1-0")
    assert lote == {"eventos": [], "cursor": "2-0", "fim": False}


def test_sem_eventos_novos_devolve_o_mesmo_cursor():
    lote = _lote(RedisFalso(ENTRADAS), cursor="5-0")
    assert lote == {"eventos": [], "cursor": "5-0", "fim": False}


def test_cursor_valido_so_aceita_ids_do_stream():
    assert cursor_valido("1730620800000-0")
    assert not cursor_valido("$")
    assert not cursor_valido("1-0; FLUSHALL")


def test_gravacao_vem_inteira_com_as_pausas():
    eventos = [{"tipo": "run.started"}, {"tipo": "run.finished"}]
    lote = lote_da_gravacao(eventos, [0.0, 1.5])
    assert lote["fim"] is True
    assert [(e["id"], e["espera"], e["evento"]["tipo"]) for e in lote["eventos"]] == [
        ("0", 0.0, "run.started"),
        ("1", 1.5, "run.finished"),
    ]


def test_sse_pede_para_nao_guardar_nem_transformar():
    assert "no-transform" in CABECALHOS_SSE["Cache-Control"]
    assert CABECALHOS_SSE["X-Accel-Buffering"] == "no"
    # O preenchimento é um comentário: clientes SSE o ignoram, e ele não tem linha "data:".
    assert set(PREENCHIMENTO) == {"comment"} and len(PREENCHIMENTO["comment"]) >= 2048
