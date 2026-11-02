"""A cidade em grade: cada lugar num lote do seu bairro, portas nas ruas e o layout em dia."""

import pytest

from contexto_mcp.layout import TIPOS_SEM_LOTE, carregar_layout, dentro, estilo, gerar_layout, serializar
from contexto_mcp.ontologia import PASTA_PADRAO, carregar_ontologia


@pytest.fixture(scope="module")
def ontologia():
    return carregar_ontologia()


@pytest.fixture(scope="module")
def layout():
    return carregar_layout()


def test_layout_cobre_exatamente_os_nos(ontologia, layout):
    assert set(layout["nos"]) == set(ontologia.entidades)


def test_cada_lugar_dentro_do_seu_bairro(ontologia, layout):
    for ident, ponto in layout["nos"].items():
        bairro = ontologia.entidades[ident].bairro
        assert dentro(tuple(ponto), layout["regioes"][bairro]), f"{ident} fora do bairro {bairro}"


def test_um_lugar_por_lote_e_nunca_na_agua(ontologia, layout):
    construcoes = [i for i, e in ontologia.entidades.items() if e.tipo not in TIPOS_SEM_LOTE]
    pontos = [tuple(layout["nos"][i]) for i in construcoes]
    assert len(set(pontos)) == len(pontos)
    agua = [q["retangulo"] for q in layout["quadras"] if q["agua"]]
    for i in construcoes:
        assert not any(dentro(tuple(layout["nos"][i]), r) for r in agua), f"{i} está no rio"


def test_portas_nas_ruas(ontologia, layout):
    """A porta de cada construção fica numa rua horizontal; as placas das paradas, numa esquina."""
    xs, ys = layout["cidade"]["xs"], layout["cidade"]["ys"]
    for ident, (x, y) in layout["portas"].items():
        assert y in ys, ident
        if ontologia.entidades[ident].tipo == "Parada":
            assert x in xs, ident


def test_bairros_ladrilham_a_cidade(ontologia, layout):
    cidade = layout["cidade"]
    por_quadra = {(q["coluna"], q["linha"]) for q in layout["quadras"]}
    assert len(por_quadra) == cidade["colunas"] * cidade["linhas"]
    contagem = {}
    for b in ontologia.bairros:
        c0, r0, c1, r1 = b.quadras
        for i in range(c0, c1):
            for j in range(r0, r1):
                contagem[(i, j)] = contagem.get((i, j), 0) + 1
    assert set(contagem) == por_quadra and set(contagem.values()) == {1}


def test_estilo_vem_do_bairro_e_do_tipo():
    assert estilo("cliente-ana", "Cliente", "cliente") == "casa"
    assert estilo("x", "ProdutoSeguro", "produtos") == "shopping"
    assert estilo("x", "Seguradora", "parceiros") == "torre"
    assert estilo("x", "RegraElegibilidade", "risco") == "fabrica"
    assert estilo("canal-app", "Canal", "canais") == "torre"
    assert estilo("x", "Rota", "canais") is None


def test_layout_versionado_esta_em_dia():
    """Se falhar: rode ./scripts/gerar-layout.sh e versione ontologia/layout.json."""
    gerado = serializar(gerar_layout(carregar_ontologia()))
    assert gerado == (PASTA_PADRAO / "layout.json").read_text(encoding="utf-8")
