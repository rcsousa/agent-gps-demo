"""Tela de abertura: o infográfico em deep zoom, com áreas clicáveis e atalhos."""

import re
import urllib.request

from conftest import WEB


def test_infografico_carrega_os_tiles_e_as_areas(pagina):
    tiles: list[str] = []
    pagina.on("response", lambda r: "/abertura/infografico_files/" in r.url and r.ok and tiles.append(r.url))
    pagina.goto(f"{WEB}/", wait_until="networkidle")
    pagina.wait_for_timeout(1500)
    assert tiles, "Nenhum tile do deep zoom foi carregado."

    areas = pagina.locator(".abertura__area")
    assert areas.count() >= 30
    rotulos = areas.evaluate_all("els => els.map(e => e.getAttribute('aria-label'))")
    assert all(r and r.strip() for r in rotulos), "Toda área precisa de rótulo acessível."


def test_area_mostra_a_dica_e_leva_ao_mapa_da_cena(pagina):
    pagina.goto(f"{WEB}/", wait_until="networkidle")
    area = pagina.get_by_role("button", name=re.compile(r"^1\. Sem mapa"))
    area.hover()
    assert "Cena 2" in pagina.locator(".abertura__dica").inner_text()
    area.click()
    pagina.wait_for_url(re.compile(r"/mapa\?cena=2"))
    assert pagina.locator("#viagem-modo").inner_text().strip().startswith("Sem contexto")


def test_enter_inicia_a_demo(pagina):
    pagina.goto(f"{WEB}/", wait_until="networkidle")
    pagina.keyboard.press("Enter")
    pagina.wait_for_url(re.compile(r"/mapa"))
    assert pagina.get_by_role("heading", name="Modo Mapa").is_visible()


def test_descritor_do_deep_zoom_gerado_no_build():
    with urllib.request.urlopen(f"{WEB}/abertura/infografico.dzi", timeout=10) as r:
        assert b'Width="2198"' in r.read()


def test_painel_apresenta_a_demo_e_o_impacto_medido(pagina):
    pagina.goto(f"{WEB}/", wait_until="networkidle")
    painel = pagina.get_by_role("complementary", name="Sobre a demo")
    assert painel.is_visible(), "O painel começa sempre aberto."
    texto = painel.inner_text()
    for trecho in ("Por que uma camada de contexto", "Impacto medido", "59% → 99%", "US$ 12", "Bloqueado"):
        assert trecho in texto
    # O infográfico fica à direita do painel.
    caixa_painel = painel.bounding_box()
    caixa_visor = pagina.locator(".abertura__visor").bounding_box()
    assert caixa_visor["x"] >= caixa_painel["x"] + caixa_painel["width"] - 1

    pagina.get_by_role("button", name="Como medimos").click()
    assert "/bastidores/01-o-problema/" in pagina.locator(".bastidores__site").get_attribute("src")


def test_painel_recolhe_pela_tecla_i_e_pelo_botao(pagina):
    pagina.goto(f"{WEB}/", wait_until="networkidle")
    painel = pagina.get_by_role("complementary", name="Sobre a demo")
    pagina.keyboard.press("i")
    painel.wait_for(state="detached")
    # Recolhido, o infográfico ocupa a largura toda e o "Iniciar demo" continua à mão.
    assert pagina.locator(".abertura__visor").bounding_box()["x"] < 1
    assert pagina.get_by_role("button", name="Iniciar demo").is_visible()
    pagina.get_by_role("button", name="Mostrar o painel (I)").click()
    painel.wait_for(state="visible")
