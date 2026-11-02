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
