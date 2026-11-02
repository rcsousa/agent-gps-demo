"""Gravações para o replay offline: salvar, listar, carregar e o ritmo original com teto."""

import pytest

from agent.gravacoes import ESPERA_MAXIMA_S, GravacaoInvalida, Gravacoes, esperas

EXECUCAO = {
    "id": "e1",
    "modo": "com_skill",
    "canal": "app",
    "provedor": "anthropic",
    "modelo": "claude-haiku-5-5",
    "status": "concluida",
    "apolice": "FAR-1",
}


def _evento(tipo: str, instante: str) -> dict:
    return {"tipo": tipo, "origem": "agent", "instante": instante, "dados": {"execucao_id": "e1"}}


EVENTOS = [
    _evento("run.started", "2026-11-02T10:00:00+00:00"),
    _evento("step.started", "2026-11-02T10:00:01+00:00"),
    _evento("tool.called", "2026-11-02T10:00:30+00:00"),
    _evento("run.finished", "2026-11-02T10:00:31+00:00"),
]


def test_salva_lista_e_carrega(tmp_path):
    g = Gravacoes(tmp_path)
    cabecalho = g.salvar("cena-6", EXECUCAO, EVENTOS, cena="6", incidentes=["cotacao-ancora-fora"])
    assert cabecalho["eventos"] == 4 and cabecalho["modelo"] == "claude-haiku-5-5"
    assert [c["nome"] for c in g.listar()] == ["cena-6"]
    lido, eventos = g.carregar("cena-6")
    assert lido["incidentes"] == ["cotacao-ancora-fora"] and eventos == EVENTOS
    g.apagar("cena-6")
    assert g.listar() == []


def test_so_grava_execucao_terminada_e_nome_seguro(tmp_path):
    g = Gravacoes(tmp_path)
    with pytest.raises(GravacaoInvalida):
        g.salvar("cena-1", EXECUCAO, EVENTOS[:-1])
    with pytest.raises(GravacaoInvalida):
        g.salvar("../fora", EXECUCAO, EVENTOS)


def test_esperas_no_ritmo_original_com_teto():
    assert esperas(EVENTOS) == [0.0, 1.0, ESPERA_MAXIMA_S, 1.0]
