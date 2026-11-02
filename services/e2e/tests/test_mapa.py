"""Modo Mapa: a cidade em grade, o robô andando pelas ruas, a câmera de GPS e a conversa no ritmo do robô."""

import re

from conftest import WEB, esperar_a_fila, simulador, viajar_pelo_roteiro

BAIRROS = ("cliente", "governanca", "produtos", "parceiros", "pagamentos")


def test_cidade_com_os_bairros_do_infografico_e_sem_rotas(pagina, mundo_limpo):
    pagina.goto(f"{WEB}/mapa", wait_until="networkidle")
    pagina.wait_for_selector(".mapa__tela canvas")
    pagina.wait_for_selector('[data-rotulo="bairro-governanca"]')
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
    # A cidade é relida a cada 5 s: a câmera não pode voltar sozinha para a parada.
    pagina.get_by_role("button", name="Enquadrar a cidade").click()
    pagina.wait_for_function("document.querySelector('.mapa').dataset.nivel === '0.0'")
    pagina.wait_for_timeout(6000)
    assert pagina.locator(".mapa").get_attribute("data-nivel") == "0.0"


def test_o_robo_anda_por_cada_lugar_e_a_conversa_vem_no_ritmo_dele(pagina, mundo_limpo):
    pagina.goto(f"{WEB}/mapa", wait_until="networkidle")
    mapa = pagina.locator(".mapa")
    pagina.click("#viagem-modelo")
    pagina.get_by_role("option", name="Roteiro (ensaio sem LLM)").click()
    pagina.click("#iniciar-viagem")
    pagina.wait_for_function("document.querySelector('.mapa').dataset.execucao !== ''")

    # Cada pergunta à Ana só aparece quando o robô chega à parada que a gerou;
    # a mensagem da apólice, só quando ele chega à emissão.
    paradas_das_perguntas = []
    parada_da_apolice = None
    camera_durante = set()
    giros = set()
    for _ in range(360):
        pagina.wait_for_timeout(500)
        camera_durante.add(mapa.get_attribute("data-camera"))
        giros.add(int(mapa.get_attribute("data-giro")))
        botoes = pagina.locator(".mapa__opcoes button:not([disabled])")
        if botoes.count():
            paradas_das_perguntas.append(mapa.get_attribute("data-parada"))
            botoes.first.click()
        if parada_da_apolice is None and "apólice" in pagina.locator(".mapa__mensagens").inner_text():
            parada_da_apolice = mapa.get_attribute("data-parada")
        if mapa.get_attribute("data-fila") == "0" and pagina.locator("#iniciar-viagem").is_enabled():
            break

    assert paradas_das_perguntas[:1] == ["parada-intencao"], paradas_das_perguntas
    assert "parada-proposta" in paradas_das_perguntas, paradas_das_perguntas
    assert parada_da_apolice == "parada-emissao"
    # Durante a viagem, a câmera seguiu o robô e o mapa girou com ele (visão traseira);
    # ao fim, ela sobe para a cidade inteira, com o norte para cima, e fica livre.
    assert "seguindo" in camera_durante
    assert any(abs(g) >= 45 for g in giros), giros
    pagina.wait_for_function("document.querySelector('.mapa').dataset.camera === 'livre'")
    pagina.wait_for_function("document.querySelector('.mapa').dataset.nivel === '0.0'", timeout=10_000)
    pagina.wait_for_timeout(6000)
    assert mapa.get_attribute("data-nivel") == "0.0"
    assert mapa.get_attribute("data-giro") == "0"

    # Câmera livre: o apresentador gira o mapa, e a bússola volta o norte para cima.
    pagina.get_by_role("button", name="Girar o mapa para a direita").click()
    pagina.wait_for_function("document.querySelector('.mapa').dataset.giro === '15'")
    pagina.locator(".mapa__bussola").click()
    pagina.wait_for_function("document.querySelector('.mapa').dataset.giro === '0'")

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
