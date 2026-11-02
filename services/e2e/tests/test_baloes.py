"""Os balões de fala do robô e o passo a passo: o mapa espera o apresentador mandar seguir."""

from conftest import WEB


def _iniciar_pelo_roteiro_no_passo_a_passo(pagina):
    pagina.goto(f"{WEB}/mapa", wait_until="networkidle")
    pagina.locator("label[for=passo-a-passo]").click()  # a fixture começa com ele desligado
    assert pagina.locator("#passo-a-passo").get_attribute("aria-checked") == "true"
    pagina.click("#viagem-modelo")
    pagina.get_by_role("option", name="Roteiro (ensaio sem LLM)").click()
    pagina.click("#iniciar-viagem")
    pagina.wait_for_function("document.querySelector('.mapa').dataset.execucao !== ''")


def test_o_balao_espera_o_apresentador_e_some_ao_seguir(pagina, mundo_limpo):
    _iniciar_pelo_roteiro_no_passo_a_passo(pagina)
    mapa = pagina.locator(".mapa")

    # O primeiro balão: uma tool, com a frase em pt-BR e a tool de verdade no detalhe.
    pagina.wait_for_function("document.querySelector('.mapa').dataset.aguardando === 'sim'", timeout=60_000)
    assert mapa.get_attribute("data-balao") == "tool"
    balao = pagina.locator(".balao")
    assert balao.locator(".balao__detalhe").inner_text().split(" · ")[0].count(".") == 1
    assert "Aguardando o apresentador" in pagina.locator(".mapa__estado").inner_text()

    # Ninguém mandou seguir: o mapa não anda.
    lugares = mapa.get_attribute("data-lugares-visitados")
    fila = mapa.get_attribute("data-fila")
    pagina.wait_for_timeout(3000)
    assert mapa.get_attribute("data-aguardando") == "sim"
    assert mapa.get_attribute("data-lugares-visitados") == lugares
    assert int(mapa.get_attribute("data-fila")) >= int(fila)

    # "Seguir" no balão: o balão some e a jornada continua.
    balao.get_by_role("button", name="Seguir").click()
    pagina.wait_for_function("document.querySelector('.mapa').dataset.aguardando === 'nao'")

    # Daí em diante, pelo teclado (Espaço), respondendo pela Ana quando ela é perguntada.
    seguidos = 1
    for _ in range(600):
        pagina.wait_for_timeout(300)
        opcoes = pagina.locator(".mapa__opcoes button:not([disabled])")
        if opcoes.count():
            opcoes.first.click()
        if mapa.get_attribute("data-aguardando") == "sim":
            pagina.evaluate("document.activeElement && document.activeElement.blur()")  # o foco sai dos botões
            pagina.keyboard.press("Space")
            pagina.wait_for_function("document.querySelector('.mapa').dataset.aguardando === 'nao'")
            seguidos += 1
        if mapa.get_attribute("data-fila") == "0" and pagina.locator("#iniciar-viagem").is_enabled():
            break

    assert seguidos >= 10, seguidos
    assert mapa.get_attribute("data-parada") == "parada-emissao"
    assert mapa.get_attribute("data-balao") == ""


def test_pular_para_o_fim_fecha_o_balao(pagina, mundo_limpo):
    _iniciar_pelo_roteiro_no_passo_a_passo(pagina)
    mapa = pagina.locator(".mapa")
    for _ in range(240):
        pagina.wait_for_timeout(500)
        opcoes = pagina.locator(".mapa__opcoes button:not([disabled])")
        if opcoes.count():
            opcoes.first.click()
        pular = pagina.get_by_role("button", name="Pular para o fim")
        if mapa.get_attribute("data-aguardando") == "sim" and pular.count():
            pular.click()
        if mapa.get_attribute("data-fila") == "0" and pagina.locator("#iniciar-viagem").is_enabled():
            break
    assert mapa.get_attribute("data-parada") == "parada-emissao"
    assert mapa.get_attribute("data-balao") == ""
