"""Modo Mapa em 3D: a cidade do grafo, os bairros que se abrem e a viagem dirigida pelos eventos."""

import re

from conftest import WEB, esperar_a_fila, simulador, viajar_pelo_roteiro

BAIRROS = ("cliente", "regulatorio", "produtos", "risco", "parceiros", "canais")


def test_cidade_e_rotas_do_grafo(pagina, mundo_limpo):
    pagina.goto(f"{WEB}/mapa", wait_until="networkidle")
    pagina.wait_for_selector(".mapa__tela canvas")
    rotas = pagina.locator(".mapa__rota")
    assert rotas.count() == 3
    textos = " ".join(rotas.all_inner_texts())
    for nome in ("Rota rápida", "Rota econômica", "Rota assistida"):
        assert nome in textos
    # Na cidade: os bairros com nome, nenhum sistema e nenhum farol (o mundo está limpo).
    pagina.wait_for_selector('[data-rotulo="bairro-risco"]')
    assert pagina.locator('[data-rotulo^="bairro-"]').count() == len(BAIRROS)
    assert pagina.locator('[data-rotulo^="sistema-"]').count() == 0
    assert pagina.locator('[data-rotulo^="incidente-"]').count() == 0
    assert pagina.locator(".mapa").get_attribute("data-bairro-aberto") == ""
    assert pagina.locator(".linha-do-tempo__parada").count() == 9


def test_bairro_abre_ao_clicar_e_mostra_os_sistemas(pagina, mundo_limpo):
    pagina.goto(f"{WEB}/mapa", wait_until="networkidle")
    pagina.locator('[data-rotulo="bairro-parceiros"]').click()
    pagina.wait_for_function("document.querySelector('.mapa').dataset.bairroAberto === 'parceiros'")
    sistemas = pagina.locator('[data-rotulo^="sistema-"]')
    sistemas.first.wait_for()
    assert sistemas.count() >= 3

    sistemas.first.click()
    painel = pagina.locator("aside.painel")
    painel.get_by_role("heading", name="Proveniência").wait_for()
    assert painel.locator(".painel__tipo").inner_text().strip()
    pagina.keyboard.press("Escape")
    painel.wait_for(state="detached")

    pagina.get_by_role("button", name=re.compile("Voltar à cidade")).click()
    pagina.wait_for_function("document.querySelector('.mapa').dataset.bairroAberto === ''")


def test_parada_da_abertura_abre_o_bairro(pagina, mundo_limpo):
    pagina.goto(f"{WEB}/mapa?parada=6", wait_until="networkidle")
    pagina.wait_for_function("document.querySelector('.mapa').dataset.bairroAberto === 'parceiros'")


def test_viagem_com_skill_pelo_roteiro(pagina, mundo_limpo):
    pagina.goto(f"{WEB}/mapa", wait_until="networkidle")
    respostas = viajar_pelo_roteiro(pagina)
    assert respostas >= 1, "A Ana precisa ter respondido pelo painel de conversa."
    # O diretor reproduz os eventos com tempo mínimo: o mapa termina depois do agente.
    esperar_a_fila(pagina)

    mapa = pagina.locator(".mapa")
    assert int(mapa.get_attribute("data-visitadas")) >= 9  # o robô passou pelas 9 paradas
    assert mapa.get_attribute("data-parada") == "parada-emissao"
    assert pagina.locator(".linha-do-tempo__parada--pendente").count() == 0
    assert "Chegada" in pagina.locator(".linha-do-tempo__narracao").inner_text()
    avisos = pagina.locator(".mapa__avisos").inner_text()
    assert re.search(r"apólice [A-Z]{3}-[0-9A-F]{8} emitida", avisos)
    assert "contratacao-seguro-residencial" in pagina.locator(".mapa__navegador").inner_text()


def test_ancora_fora_acende_o_farol_e_a_viagem_desvia(pagina, mundo_limpo):
    simulador("/incidentes/cotacao-ancora-fora/aplicar")
    pagina.goto(f"{WEB}/mapa", wait_until="networkidle")
    # O trânsito aparece antes da viagem: o farol do nó e as rotas interditadas.
    pagina.wait_for_selector('[data-rotulo="incidente-api-cotacao-ancora"]')
    assert pagina.locator(".mapa__rota", has_text="Interditada").count() >= 1

    viajar_pelo_roteiro(pagina)
    pular = pagina.get_by_role("button", name="Pular para o fim")
    if pular.count():
        pular.click()
    esperar_a_fila(pagina)
    avisos = pagina.locator(".mapa__avisos").inner_text()
    assert "Rua interditada" in avisos
    assert "Âncora" in avisos
    # A apólice sai por outra seguradora.
    assert re.search(r"apólice (FAR|HOR)-", avisos)
