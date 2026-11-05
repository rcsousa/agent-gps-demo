"""Os anúncios do GPS no passo a passo: o mapa espera o apresentador mandar seguir."""

from conftest import WEB


def _seguiu(pagina, balao: str | None) -> None:
    """O balão foi embora: o mapa não espera mais, ou já espera em outro balão."""
    pagina.wait_for_function(
        "([n]) => { const m = document.querySelector('.mapa').dataset;"
        " return m.aguardando === 'nao' || m.balaoN !== n; }",
        arg=[balao],
    )


def _iniciar_pelo_roteiro_no_passo_a_passo(pagina):
    pagina.goto(f"{WEB}/mapa", wait_until="networkidle")
    pagina.click("#pausas")  # a fixture começa no contínuo
    pagina.get_by_role("option", name="Passo a passo").click()
    assert pagina.locator(".mapa").get_attribute("data-pausas") == "passo"
    pagina.click("#viagem-modelo")
    pagina.get_by_role("option", name="Roteiro (ensaio sem LLM)").click()
    pagina.click("#iniciar-viagem")
    pagina.wait_for_function("document.querySelector('.mapa').dataset.execucao !== ''")


def test_o_balao_espera_o_apresentador_e_some_ao_seguir(pagina, mundo_limpo):
    _iniciar_pelo_roteiro_no_passo_a_passo(pagina)
    mapa = pagina.locator(".mapa")

    # O primeiro balão: o GPS se apresenta, com o modelo de verdade no detalhe.
    pagina.wait_for_function("document.querySelector('.mapa').dataset.aguardando === 'sim'", timeout=60_000)
    assert mapa.get_attribute("data-balao") == "apresentacao"
    balao = pagina.locator(".balao")
    assert balao.locator(".balao__gps").inner_text().strip() == "GPS"
    assert "Sou o GPS do Banco Bússola" in balao.locator(".balao__texto").inner_text()
    assert "Aguardando o apresentador" in pagina.locator(".mapa__estado").inner_text()

    # Ninguém mandou seguir: o mapa não anda.
    lugares = mapa.get_attribute("data-lugares-visitados")
    fila = mapa.get_attribute("data-fila")
    pagina.wait_for_timeout(3000)
    assert mapa.get_attribute("data-aguardando") == "sim"
    assert mapa.get_attribute("data-lugares-visitados") == lugares
    assert int(mapa.get_attribute("data-fila")) >= int(fila)

    # "Seguir" no balão: o balão some e a jornada continua (o próximo balão, se vier logo, é outro).
    primeiro = mapa.get_attribute("data-balao-n")
    balao.get_by_role("button", name="Seguir").click()
    _seguiu(pagina, primeiro)

    # Daí em diante, pelo teclado (Espaço), respondendo pela Ana quando ela é perguntada.
    seguidos = 1
    for _ in range(1200):
        pagina.wait_for_timeout(300)
        opcoes = pagina.locator(".mapa__opcoes button:not([disabled])")
        if opcoes.count():
            opcoes.first.click()
        if mapa.get_attribute("data-aguardando") == "sim":
            atual = mapa.get_attribute("data-balao-n")
            pagina.evaluate("document.activeElement && document.activeElement.blur()")  # o foco sai dos botões
            pagina.keyboard.press("Space")
            _seguiu(pagina, atual)
            seguidos += 1
        if mapa.get_attribute("data-fila") == "0" and pagina.locator("#iniciar-viagem").is_enabled():
            break

    assert seguidos >= 25, seguidos  # apresentação, roteiro, rota, 9 paradas, cada sistema, a chegada
    assert mapa.get_attribute("data-parada") == "parada-emissao"


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


def test_no_bairro_de_produtos_o_robo_para_no_predio_do_produto(pagina, mundo_limpo):
    # Adequação, proposta e aceite levam o robô ao prédio do produto, e o balão cita o produto.
    _iniciar_pelo_roteiro_no_passo_a_passo(pagina)
    mapa = pagina.locator(".mapa")
    no_produto: list[tuple[str, str]] = []
    for _ in range(1200):
        pagina.wait_for_timeout(300)
        opcoes = pagina.locator(".mapa__opcoes button:not([disabled])")
        if opcoes.count():
            opcoes.first.click()
        if mapa.get_attribute("data-aguardando") == "sim":
            lugar = mapa.get_attribute("data-lugar")
            if lugar.startswith("produto-residencial-"):
                no_produto.append((lugar, pagina.locator(".balao").inner_text()))
            atual = mapa.get_attribute("data-balao-n")
            pagina.evaluate("document.activeElement && document.activeElement.blur()")
            pagina.keyboard.press("Space")
            _seguiu(pagina, atual)
        if mapa.get_attribute("data-fila") == "0" and pagina.locator("#iniciar-viagem").is_enabled():
            break

    textos = " | ".join(texto for _, texto in no_produto)
    assert len(no_produto) >= 3, textos  # adequação, proposta e aceite
    assert "Avaliando se o Residencial" in textos
    assert "Montando a proposta do Residencial" in textos
    assert "Registrando o aceite do Residencial" in textos
