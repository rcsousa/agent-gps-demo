"""Modo Mapa: a cidade do grafo, o zoom semântico e a viagem dirigida pelos eventos."""

import re

from conftest import WEB, simulador, viajar_pelo_roteiro


def _centro(pagina):
    caixa = pagina.locator(".mapa__area").bounding_box()
    return caixa["x"] + caixa["width"] / 2, caixa["y"] + caixa["height"] / 2


def test_cidade_e_rotas_do_grafo(pagina, mundo_limpo):
    pagina.goto(f"{WEB}/mapa", wait_until="networkidle")
    pagina.wait_for_selector(".mapa__tela canvas")
    rotas = pagina.locator(".mapa__rota")
    assert rotas.count() == 3
    textos = " ".join(rotas.all_inner_texts())
    for nome in ("Rota rápida", "Rota econômica", "Rota assistida"):
        assert nome in textos
    # De longe, só bairros e avenidas: nenhum nome de nó.
    assert pagina.locator(".mapa").get_attribute("data-nomes") == "0"


def test_zoom_semantico_e_clique_no_no_com_proveniencia(pagina, mundo_limpo):
    # ?parada=6 voa até a cotação, perto o bastante para os nomes aparecerem.
    pagina.goto(f"{WEB}/mapa?parada=6", wait_until="networkidle")
    pagina.wait_for_function("Number(document.querySelector('.mapa').dataset.nomes) > 0")
    x, y = _centro(pagina)
    pagina.mouse.click(x, y)
    painel = pagina.locator("aside.painel")
    painel.wait_for()
    assert painel.locator(".painel__titulo").inner_text() == "Cotação"
    painel.get_by_role("heading", name="Proveniência").wait_for()
    assert "Desenho da jornada" in painel.inner_text()


def test_viagem_com_skill_pelo_roteiro(pagina, mundo_limpo):
    pagina.goto(f"{WEB}/mapa", wait_until="networkidle")
    respostas = viajar_pelo_roteiro(pagina)
    assert respostas >= 1, "A Ana precisa ter respondido pelo painel de conversa."

    mapa = pagina.locator(".mapa")
    assert int(mapa.get_attribute("data-visitadas")) >= 9  # o robô passou pelas 9 paradas
    assert mapa.get_attribute("data-parada") == "parada-emissao"
    avisos = pagina.locator(".mapa__avisos").inner_text()
    assert re.search(r"apólice [A-Z]{3}-[0-9A-F]{8} emitida", avisos)
    assert "contratacao-seguro-residencial" in pagina.locator(".mapa__navegador").inner_text()


def test_ancora_fora_interdita_o_trecho_e_a_viagem_desvia(pagina, mundo_limpo):
    simulador("/incidentes/cotacao-ancora-fora/aplicar")
    pagina.goto(f"{WEB}/mapa", wait_until="networkidle")
    pagina.wait_for_selector(".mapa__rota")
    interditadas = pagina.locator(".mapa__rota", has_text="Interditada")
    assert interditadas.count() >= 1

    viajar_pelo_roteiro(pagina)
    avisos = pagina.locator(".mapa__avisos").inner_text()
    assert "Rua interditada" in avisos
    assert "Âncora" in avisos
    # A apólice sai por outra seguradora.
    assert re.search(r"apólice (FAR|HOR)-", avisos)
