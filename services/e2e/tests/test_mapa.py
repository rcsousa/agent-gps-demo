"""Modo Mapa: a cidade em grade (uma construção por lugar do grafo) e o robô andando pelas ruas."""

import re

from conftest import WEB, esperar_a_fila, simulador, viajar_pelo_roteiro

BAIRROS = ("cliente", "regulatorio", "produtos", "risco", "parceiros", "canais")


def test_cidade_com_bairros_e_sem_rotas(pagina, mundo_limpo):
    pagina.goto(f"{WEB}/mapa", wait_until="networkidle")
    pagina.wait_for_selector(".mapa__tela canvas")
    pagina.wait_for_selector('[data-rotulo="bairro-risco"]')
    assert pagina.locator('[data-rotulo^="bairro-"]').count() == len(BAIRROS)
    # De longe: sem nomes de construções, sem faróis (o mundo está limpo) e sem o cartão das 3 rotas.
    assert pagina.locator(".mapa").get_attribute("data-nomes") == "nao"
    assert pagina.locator('[data-rotulo^="construcao-"]').count() == 0
    assert pagina.locator('[data-rotulo^="incidente-"]').count() == 0
    assert pagina.locator(".mapa__rota").count() == 0
    assert pagina.locator(".linha-do-tempo__parada").count() == 9


def test_de_perto_aparecem_os_nomes_e_o_clique_mostra_a_proveniencia(pagina, mundo_limpo):
    pagina.goto(f"{WEB}/mapa", wait_until="networkidle")
    pagina.locator('[data-rotulo="bairro-parceiros"]').click()
    pagina.wait_for_function("document.querySelector('.mapa').dataset.nomes === 'sim'")
    construcoes = pagina.locator('[data-rotulo^="construcao-"]')
    construcoes.first.wait_for()
    assert construcoes.count() >= 5

    nome = construcoes.first.inner_text().strip()
    construcoes.first.click()
    painel = pagina.locator("aside.painel")
    painel.get_by_role("heading", name="Proveniência").wait_for()
    assert painel.locator(".painel__titulo").inner_text().strip() == nome


def test_parada_da_abertura_aproxima_a_camera(pagina, mundo_limpo):
    pagina.goto(f"{WEB}/mapa?parada=6", wait_until="networkidle")
    pagina.wait_for_function("document.querySelector('.mapa').dataset.nomes === 'sim'")


def test_o_robo_anda_por_cada_lugar_que_o_agente_usa(pagina, mundo_limpo):
    pagina.goto(f"{WEB}/mapa", wait_until="networkidle")
    respostas = viajar_pelo_roteiro(pagina)
    assert respostas >= 1, "A Ana precisa ter respondido pelo painel de conversa."
    esperar_a_fila(pagina, limite_s=180)

    mapa = pagina.locator(".mapa")
    # Cada trecho é um evento real: as placas das paradas e os prédios dos sistemas chamados.
    assert int(mapa.get_attribute("data-lugares-visitados")) >= 10
    assert int(mapa.get_attribute("data-visitadas")) >= 9
    assert mapa.get_attribute("data-parada") == "parada-emissao"
    assert pagina.locator(".linha-do-tempo__parada--pendente").count() == 0
    assert "Chegada" in pagina.locator(".linha-do-tempo__narracao").inner_text()
    assert re.search(r"apólice [A-Z]{3}-[0-9A-F]{8} emitida", pagina.locator(".mapa__avisos").inner_text())


def test_ancora_fora_acende_o_farol_e_a_viagem_desvia(pagina, mundo_limpo):
    simulador("/incidentes/cotacao-ancora-fora/aplicar")
    pagina.goto(f"{WEB}/mapa", wait_until="networkidle")
    # O trânsito aparece antes da viagem: o farol no prédio da API da Âncora.
    pagina.wait_for_selector('[data-rotulo="incidente-api-cotacao-ancora"]')

    viajar_pelo_roteiro(pagina)
    pular = pagina.get_by_role("button", name="Pular para o fim")
    if pular.count():
        pular.click()
    esperar_a_fila(pagina)
    avisos = pagina.locator(".mapa__avisos").inner_text()
    assert "Rua interditada" in avisos and "Âncora" in avisos
    assert re.search(r"apólice (FAR|HOR)-", avisos)
