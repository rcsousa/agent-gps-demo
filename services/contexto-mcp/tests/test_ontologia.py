"""A ontologia versionada: válida, no tamanho certo e fiel à spec."""

import pytest

from contexto_mcp.ontologia import carregar_ontologia


@pytest.fixture(scope="module")
def ontologia():
    return carregar_ontologia()


def test_tamanho_dentro_da_faixa_da_spec(ontologia):
    assert 150 <= len(ontologia.entidades) <= 300


def test_todo_bairro_tem_entidades(ontologia):
    assert {e.bairro for e in ontologia.entidades.values()} == {b.id for b in ontologia.bairros}
    assert len(ontologia.bairros) == 6


def test_proveniencia_completa_em_nos_e_relacoes(ontologia):
    for item in [*ontologia.entidades.values(), *ontologia.relacoes]:
        p = item.proveniencia
        assert p.fonte and p.responsavel and p.data and p.confianca


def test_ana_como_descrita_na_spec(ontologia):
    ana = ontologia.entidades["cliente-ana"]
    assert ana.atributos["idade"] == 38
    assert ana.atributos["anos_de_relacionamento"] == 6
    assert ana.atributos["cidade"] == "São Paulo"
    vizinhos = {r.para for r in ontologia.relacoes if r.de == "cliente-ana"}
    assert "imovel-ana" in vizinhos
    assert ontologia.entidades["imovel-ana"].atributos["tipo_imovel"] == "apartamento"
    assert "contratado-ana-auto" in vizinhos


def test_sete_clientes_cenario_cobrindo_os_incidentes(ontologia):
    clientes = [e for e in ontologia.entidades.values() if e.tipo == "Cliente" and e.id != "cliente-ana"]
    assert len(clientes) == 7
    cenarios = {c.atributos["cenario"] for c in clientes}
    assert {
        "consentimento-expirado",
        "imovel-area-de-risco",
        "premio-acima-da-alcada",
        "proveniencia-fraca",
    } <= cenarios


def test_consentimento_expirado_do_bruno(ontologia):
    consentimento = ontologia.entidades["consentimento-bruno-oferta"]
    assert consentimento.estado.status == "fora"
    assert consentimento.estado.vigencia.fim.isoformat() < "2026-11-01"


def test_proveniencia_fraca_da_elisa(ontologia):
    assert ontologia.entidades["cliente-elisa"].proveniencia.confianca == "baixa"


def test_tres_seguradoras_da_identidade_visual(ontologia):
    nomes = {e.nome for e in ontologia.entidades.values() if e.tipo == "Seguradora"}
    assert nomes == {"Âncora Seguros", "Farol Seguros", "Horizonte Seguros"}


def _paradas_da_rota(ontologia, rota: str) -> list[str]:
    passos = [r for r in ontologia.relacoes if r.de == rota and r.tipo == "PASSA_POR"]
    return [r.para for r in sorted(passos, key=lambda r: r.atributos["ordem"])]


@pytest.mark.parametrize("rota", ["rota-rapida", "rota-economica", "rota-assistida"])
def test_rotas_cobrem_as_nove_paradas_em_ordem(ontologia, rota):
    numeros = [
        ontologia.entidades[p].atributos.get("numero")
        for p in _paradas_da_rota(ontologia, rota)
        if "numero" in ontologia.entidades[p].atributos
    ]
    assert numeros == list(range(1, 10))


def test_rota_assistida_passa_pelo_pedagio(ontologia):
    paradas = _paradas_da_rota(ontologia, "rota-assistida")
    assert paradas.index("parada-aprovacao-humana") < paradas.index("parada-emissao")
    fila = next(r.para for r in ontologia.relacoes if r.de == "parada-aprovacao-humana" and r.tipo == "EXIGE")
    assert any(r.tipo == "ATENDIDA_POR" and r.de == fila for r in ontologia.relacoes)
