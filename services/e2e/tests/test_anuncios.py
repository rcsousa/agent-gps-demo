"""O GPS anuncia a viagem como um navegador de trânsito, e os modos de pausa decidem quando o mapa espera.

Cada anúncio nasce de um evento real: a apresentação (run.started), o roteiro (skill.loaded), a rota
(route.planned), cada parada (step.started), os sistemas chamados, o recálculo, a pergunta à cliente
e a chegada (run.finished).
"""

from conftest import WEB, simulador


def _escolher_pausas(pagina, nome: str, valor: str) -> None:
    pagina.click("#pausas")
    pagina.get_by_role("option", name=nome).click()
    assert pagina.locator(".mapa").get_attribute("data-pausas") == valor


def _iniciar_pelo_roteiro(pagina) -> None:
    pagina.click("#viagem-modelo")
    pagina.get_by_role("option", name="Roteiro (ensaio sem LLM)").click()
    pagina.click("#iniciar-viagem")
    pagina.wait_for_function("document.querySelector('.mapa').dataset.execucao !== ''")


def _acompanhar(pagina, responder: bool = True, limite: int = 900) -> list[dict]:
    """Os anúncios na ordem em que apareceram (um por evento), respondendo pela Ana."""
    mapa = pagina.locator(".mapa")
    vistos: list[dict] = []
    ultimo = None
    for _ in range(limite):
        pagina.wait_for_timeout(150)
        n = mapa.get_attribute("data-balao-n")
        if n and n != ultimo:
            ultimo = n
            balao = pagina.locator(".balao")
            subtexto = balao.locator(".balao__subtexto")
            vistos.append(
                {
                    "tipo": mapa.get_attribute("data-balao"),
                    "texto": balao.locator(".balao__texto").inner_text(),
                    "subtexto": subtexto.inner_text() if subtexto.count() else "",
                    "aguardando": mapa.get_attribute("data-aguardando"),
                }
            )
        if responder:
            opcoes = pagina.locator(".mapa__opcoes button:not([disabled])")
            if opcoes.count():
                opcoes.first.click()
        if mapa.get_attribute("data-fila") == "0" and pagina.locator("#iniciar-viagem").is_enabled():
            break
    return vistos


def test_o_gps_se_apresenta_traca_a_rota_e_anuncia_cada_parada(pagina, mundo_limpo):
    pagina.goto(f"{WEB}/mapa", wait_until="networkidle")
    _iniciar_pelo_roteiro(pagina)
    vistos = _acompanhar(pagina)
    tipos = [v["tipo"] for v in vistos]

    # A apresentação vem primeiro, e a chegada por último.
    assert tipos[0] == "apresentacao", tipos
    assert "Sou o GPS do Banco Bússola" in vistos[0]["texto"]
    assert "Destino:" in vistos[0]["subtexto"]
    assert tipos[-1] == "chegada" and "Você chegou ao destino: apólice" in vistos[-1]["texto"]

    # O roteiro e a rota, com o motivo que o agente escreveu.
    roteiro = next(v for v in vistos if v["tipo"] == "roteiro")
    assert "Roteiro carregado: Contratação de seguro residencial" in roteiro["texto"]
    rota = next(v for v in vistos if v["tipo"] == "rota")
    assert "traçada: 9 paradas" in rota["texto"] and rota["subtexto"]

    # As 9 paradas anunciadas, na ordem, cada uma dizendo o que o GPS vai fazer e o que vem depois.
    paradas = [v for v in vistos if v["tipo"] == "parada"]
    assert [p["texto"].split(":")[0] for p in paradas] == [f"Parada {n} de 9" for n in range(1, 10)]
    assert paradas[0]["texto"] == "Parada 1 de 9: Entender a intenção."
    assert paradas[2]["subtexto"].startswith("Vou conferir se a cliente autorizou")
    assert paradas[2]["subtexto"].endswith("A seguir: Elegibilidade.")
    assert paradas[-1]["subtexto"].endswith("É a última parada.")

    # A pergunta à cliente também é anunciada; no contínuo, nada espera o apresentador.
    assert "pergunta" in tipos
    assert all(v["aguardando"] == "nao" for v in vistos)


def test_o_recalculo_explica_a_troca_e_a_nova_estimativa(pagina, mundo_limpo):
    simulador("/incidentes/cotacao-ancora-fora/aplicar")
    pagina.goto(f"{WEB}/mapa", wait_until="networkidle")
    _iniciar_pelo_roteiro(pagina)
    vistos = _acompanhar(pagina)

    incidente = next(v for v in vistos if v["tipo"] == "incidente")
    assert incidente["texto"] == "Atenção: rua interditada à frente."
    assert "Âncora" in incidente["subtexto"]
    recalculo = next(v for v in vistos if v["tipo"] == "recalculo")
    assert recalculo["texto"].startswith("Recalculando…")
    assert "Nova estimativa:" in recalculo["subtexto"]


def test_so_quando_precisa_para_na_pergunta_ate_a_resposta(pagina, mundo_limpo):
    pagina.goto(f"{WEB}/mapa", wait_until="networkidle")
    assert pagina.locator(".mapa").get_attribute("data-pausas") == "continuo"  # a fixture
    _escolher_pausas(pagina, "Só quando precisa de você", "input")
    _iniciar_pelo_roteiro(pagina)
    mapa = pagina.locator(".mapa")

    # Até a primeira pergunta, nada espera o apresentador: os anúncios correm no tempo de leitura.
    pagina.wait_for_function(
        "document.querySelector('.mapa').dataset.aguardandoResposta === 'sim'", timeout=120_000
    )
    assert mapa.get_attribute("data-balao") == "pergunta"
    assert "Preciso de uma resposta da cliente." in pagina.locator(".balao__texto").inner_text()
    assert "Aguardando a resposta da Ana" in pagina.locator(".mapa__estado").inner_text()
    assert pagina.locator(".balao").get_by_role("button", name="Seguir").count() == 0

    # Sem resposta, o mapa não sai dali.
    lugares = mapa.get_attribute("data-lugares-visitados")
    pagina.wait_for_timeout(4000)
    assert mapa.get_attribute("data-aguardando-resposta") == "sim"
    assert mapa.get_attribute("data-lugares-visitados") == lugares

    # Respondida, a viagem segue sozinha até a chegada, sem nenhuma parada para o apresentador.
    pagina.locator(".mapa__opcoes button:not([disabled])").first.click()
    pagina.wait_for_function("document.querySelector('.mapa').dataset.aguardandoResposta === 'nao'")
    vistos = _acompanhar(pagina)
    assert vistos and vistos[-1]["tipo"] == "chegada"
    assert all(v["aguardando"] == "nao" for v in vistos)


def test_so_quando_precisa_para_no_pedagio(pagina, mundo_limpo):
    simulador("/incidentes/alcada-ana-excedida/aplicar")
    pagina.goto(f"{WEB}/mapa", wait_until="networkidle")
    _escolher_pausas(pagina, "Só quando precisa de você", "input")
    _iniciar_pelo_roteiro(pagina)
    mapa = pagina.locator(".mapa")
    for _ in range(900):
        pagina.wait_for_timeout(150)
        opcoes = pagina.locator(".mapa__opcoes button:not([disabled])")
        if opcoes.count():
            opcoes.first.click()
        if mapa.get_attribute("data-aguardando") == "sim":
            break
    # A única parada para o apresentador é o pedágio.
    assert mapa.get_attribute("data-balao") == "pedagio"
    assert "Pedágio à frente" in pagina.locator(".balao__texto").inner_text()
    pagina.locator(".balao").get_by_role("button", name="Seguir").click()
    pagina.wait_for_function("document.querySelector('.mapa').dataset.aguardando === 'nao'")


def test_trocar_para_continuo_solta_o_balao_que_esperava(pagina, mundo_limpo):
    pagina.goto(f"{WEB}/mapa", wait_until="networkidle")
    _escolher_pausas(pagina, "Passo a passo", "passo")
    _iniciar_pelo_roteiro(pagina)
    pagina.wait_for_function("document.querySelector('.mapa').dataset.aguardando === 'sim'", timeout=60_000)
    _escolher_pausas(pagina, "Contínuo", "continuo")
    pagina.wait_for_function("document.querySelector('.mapa').dataset.aguardando === 'nao'")


def test_a_voz_e_opcional_e_desligada_por_padrao(pagina):
    pagina.goto(f"{WEB}/mapa", wait_until="networkidle")
    assert pagina.locator(".mapa").get_attribute("data-voz") == "nao"
    assert pagina.locator("#voz").get_attribute("aria-checked") == "false"
