"""Rede corporativa: um proxy que segura o SSE não pode travar a viagem.

Proxies e antivírus com inspeção de HTTPS costumam guardar a resposta inteira antes de entregá-la,
e um stream que só termina no fim da viagem nunca chega ao navegador. Aqui o Playwright faz o
papel desse proxy: a requisição do SSE fica pendurada, sem resposta. O mapa precisa perceber e
seguir pela consulta por lotes, com os mesmos eventos.
"""

import json
import urllib.request

from conftest import WEB, esperar_a_fila, viajar_pelo_roteiro

# Só o SSE: a consulta (…/eventos/lote) passa normalmente.
SSE_AO_VIVO = "**/api/execucoes/*/eventos"
SSE_DO_REPLAY = "**/api/gravacoes/*/eventos"


def _segurar(rota) -> None:
    """Como o proxy com buffer: recebe a requisição e não devolve nada."""


def _api(metodo: str, caminho: str, corpo: dict | None = None) -> dict:
    dados = json.dumps(corpo).encode() if corpo is not None else None
    pedido = urllib.request.Request(
        f"{WEB}{caminho}", data=dados, method=metodo, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(pedido, timeout=30) as resposta:
        return json.load(resposta)


def test_rede_normal_segue_pelo_sse(pagina, mundo_limpo):
    pagina.goto(f"{WEB}/mapa", wait_until="networkidle")
    viajar_pelo_roteiro(pagina)
    assert pagina.locator(".mapa").get_attribute("data-transporte") == "sse"
    assert not pagina.locator(".mapa__selo-consulta").is_visible()


def test_proxy_segurando_o_sse_a_viagem_segue_por_consulta(pagina, mundo_limpo):
    pagina.route(SSE_AO_VIVO, _segurar)
    pagina.goto(f"{WEB}/mapa", wait_until="networkidle")
    respostas = viajar_pelo_roteiro(pagina)
    esperar_a_fila(pagina)

    mapa = pagina.locator(".mapa")
    assert mapa.get_attribute("data-transporte") == "consulta"
    assert pagina.locator(".mapa__selo-consulta").inner_text() == "Eventos por consulta"
    assert respostas >= 1, "As perguntas à Ana também chegam pela consulta."
    assert "apólice" in pagina.locator(".mapa__mensagens").inner_text()

    # Nenhum evento repetido nem perdido: o mapa mostrou o que o barramento registrou.
    execucao = _api("GET", f"/api/execucoes/{mapa.get_attribute('data-execucao')}")
    assert execucao["apolice"]
    assert int(mapa.get_attribute("data-visitadas")) >= 9
    pagina.unroute_all(behavior="ignoreErrors")  # solta a requisição que o "proxy" segurava


def test_consulta_forcada_pela_url(pagina, mundo_limpo):
    # Sem segurar nada: com ?eventos=consulta o mapa nem tenta o SSE.
    pagina.goto(f"{WEB}/mapa?eventos=consulta", wait_until="networkidle")
    viajar_pelo_roteiro(pagina)
    assert pagina.locator(".mapa").get_attribute("data-transporte") == "consulta"


def test_replay_com_o_sse_seguro_toca_por_consulta(pagina, mundo_limpo):
    # A gravação versionada da cena 6 (a mesma que o site de bastidores abre).
    pagina.route(SSE_DO_REPLAY, _segurar)
    pagina.goto(f"{WEB}/mapa?gravacao=cena-6&cena=6", wait_until="load")
    pagina.wait_for_function(
        "document.querySelector('.mapa').dataset.execucao === 'gravacao:cena-6'", timeout=30000
    )
    pagina.wait_for_function("document.querySelector('.mapa').dataset.transporte === 'consulta'", timeout=15000)
    pular = pagina.get_by_role("button", name="Pular para o fim")
    pular.wait_for(timeout=30000)
    pular.click()
    pagina.wait_for_function(
        "document.querySelector('.linha-do-tempo__narracao').innerText.startsWith('Chegada')", timeout=90000
    )
    assert pagina.locator(".mapa__selo-replay").is_visible()
    assert pagina.locator(".mapa__selo-consulta").is_visible()
    pagina.unroute_all(behavior="ignoreErrors")
