"""Fase 7: Modo Raio-X, placar, painel do apresentador e replay offline. Tudo pelo roteiro."""

import json
import re
import urllib.request

from conftest import WEB, esperar_a_fila, simulador, viajar_pelo_roteiro


def _api(metodo: str, caminho: str, corpo: dict | None = None) -> dict:
    dados = json.dumps(corpo).encode() if corpo is not None else None
    pedido = urllib.request.Request(
        f"{WEB}{caminho}", data=dados, method=metodo, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(pedido, timeout=30) as resposta:
        return json.load(resposta)


def test_raio_x_mantem_a_viagem_e_mostra_o_protocolo(pagina, mundo_limpo):
    pagina.goto(f"{WEB}/mapa", wait_until="networkidle")
    viajar_pelo_roteiro(pagina)
    execucao = pagina.locator(".mapa").get_attribute("data-execucao")

    pagina.get_by_role("tab", name="Raio-X").click()
    pagina.wait_for_url(re.compile(r"visao=raio-x"))
    assert pagina.locator(".mapa").get_attribute("data-execucao") == execucao  # a mesma viagem
    esperar_a_fila(pagina)
    titulos = pagina.locator(".raiox__titulo").all_inner_texts()
    for esperado in ("tools/list", "skills/list", "resources/read", "tool: contexto.consultar_rota"):
        assert any(t.startswith(esperado) for t in titulos), esperado

    # Cada linha abre o evento cru do barramento.
    pagina.locator(".raiox__linha", has_text="skills/list").first.click()
    painel = pagina.locator("aside.painel")
    painel.wait_for()
    assert '"tipo": "skills.listed"' in painel.inner_text()
    pagina.keyboard.press("Escape")

    pagina.get_by_role("tab", name="Métricas").click()
    assert "Regras cumpridas" in pagina.locator(".raiox__numeros").inner_text()


def test_placar_compara_os_modos_da_sessao(pagina, mundo_limpo):
    pagina.goto(f"{WEB}/mapa", wait_until="networkidle")
    viajar_pelo_roteiro(pagina, modo="Sem skill")
    viajar_pelo_roteiro(pagina, modo="Com skill (GPS)")
    pagina.get_by_role("tab", name="Raio-X").click()
    pagina.get_by_role("tab", name="Placar").click()
    placar = pagina.get_by_test_id("placar")
    placar.locator(".placar__cartao").first.wait_for()
    cartoes = placar.locator(".placar__cartao").all_inner_texts()
    assert any("Sem skill" in c for c in cartoes) and any("Com skill" in c for c in cartoes)
    assert "Referência" in placar.inner_text() and "Haiku 5.5" in placar.inner_text()


def test_apresentador_muda_o_mundo_e_decide_o_pedagio(pagina, mundo_limpo):
    pagina.goto(f"{WEB}/mapa", wait_until="networkidle")
    pagina.keyboard.press("p")
    gaveta = pagina.locator(".apresentador")
    gaveta.wait_for()

    gaveta.get_by_role("button", name="Ao vivo: Pedágio").click()
    pagina.wait_for_url(re.compile(r"cena=7"))
    pagina.click("label[for=incidente-alcada-ana-excedida]")
    pagina.wait_for_function(
        "fetch('/simulador/incidentes').then(r => r.json())"
        ".then(l => l.find(i => i.id === 'alcada-ana-excedida').ativo)"
    )

    pagina.click("#viagem-modelo")
    pagina.get_by_role("option", name="Roteiro (ensaio sem LLM)").click()
    pagina.click("#iniciar-viagem")
    # Responde pela Ana até o pedágio aparecer na gaveta; aprova e segue até o fim da viagem.
    ticket = gaveta.locator(".apresentador__ticket")
    aprovou = False
    for _ in range(240):
        pagina.wait_for_timeout(500)
        if pagina.locator(".mapa__opcoes button:not([disabled])").count():
            pagina.locator(".mapa__opcoes button:not([disabled])").first.click()
        if not aprovou and ticket.count():
            ticket.get_by_role("button", name="Aprovar").click()
            aprovou = True
        if aprovou and pagina.locator("#iniciar-viagem").is_enabled():
            break
    assert aprovou, "O pedágio não apareceu na gaveta do apresentador."
    assert _api("GET", f"/api/execucoes/{pagina.locator('.mapa').get_attribute('data-execucao')}")["apolice"]


def test_replay_offline_de_uma_gravacao(pagina, mundo_limpo):
    pagina.goto(f"{WEB}/mapa", wait_until="networkidle")
    viajar_pelo_roteiro(pagina)
    execucao = pagina.locator(".mapa").get_attribute("data-execucao")
    _api("POST", "/api/gravacoes", {"execucao": execucao, "nome": "e2e-replay", "incidentes": []})
    try:
        pagina.goto(f"{WEB}/mapa?gravacao=e2e-replay", wait_until="load")
        pagina.wait_for_function("document.querySelector('.mapa').dataset.execucao === 'gravacao:e2e-replay'")
        assert pagina.locator(".mapa__selo-replay").inner_text().startswith("Replay")
        pular = pagina.get_by_role("button", name="Pular para o fim")
        pular.wait_for(timeout=15000)
        pular.click()
        pagina.wait_for_function(
            "document.querySelector('.linha-do-tempo__narracao').innerText.startsWith('Chegada')", timeout=90000
        )
        assert pagina.locator(".mapa__selo-replay").is_visible()  # o selo não sai nunca
    finally:
        _api("DELETE", "/api/gravacoes/e2e-replay")
        simulador("/reset")
