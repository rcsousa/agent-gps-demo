"""O layout versionado cobre a ontologia, respeita os bairros e é determinístico."""

import math

import pytest

from contexto_mcp.layout import GRADE, carregar_layout, dentro, gerar_layout, serializar
from contexto_mcp.ontologia import PASTA_PADRAO, carregar_ontologia


@pytest.fixture(scope="module")
def ontologia():
    return carregar_ontologia()


@pytest.fixture(scope="module")
def layout():
    return carregar_layout()


def test_layout_cobre_exatamente_os_nos(ontologia, layout):
    assert set(layout["nos"]) == set(ontologia.entidades)


def test_cada_no_dentro_do_seu_bairro(ontologia, layout):
    for ident, ponto in layout["nos"].items():
        bairro = ontologia.bairro(ontologia.entidades[ident].bairro)
        assert dentro(tuple(ponto), bairro.poligono), f"{ident} fora do bairro {bairro.id}"


def test_distancia_minima_entre_nos(layout):
    pontos = list(layout["nos"].values())
    menor = min(math.dist(a, b) for i, a in enumerate(pontos) for b in pontos[i + 1 :])
    assert menor >= GRADE


def test_layout_versionado_esta_em_dia():
    """Se falhar: rode ./scripts/gerar-layout.sh e versione ontologia/layout.json."""
    gerado = serializar(gerar_layout(carregar_ontologia()))
    assert gerado == (PASTA_PADRAO / "layout.json").read_text(encoding="utf-8")


def test_avenidas_ligam_bairros_diferentes(layout):
    assert layout["avenidas"]
    assert all(a["de"] != a["para"] and a["relacoes"] > 0 for a in layout["avenidas"])
