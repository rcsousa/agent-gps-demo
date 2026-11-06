"""Referência técnica: as páginas, os diagramas com zoom e a acessibilidade."""

import re

import pytest
from conftest import WEB
from test_acessibilidade import _violacoes

PAGINAS = {
    "referencia/": 0,
    "referencia/arquitetura/": 4,
    "referencia/grafo/": 4,
    "referencia/gateway-mcp/": 3,
    "referencia/skills-prompts-tools/": 0,
}


@pytest.mark.parametrize("pagina_da_referencia", PAGINAS)
def test_pagina_abre_com_os_diagramas_prontos_e_sem_violacoes_graves(pagina, pagina_da_referencia):
    pagina.goto(f"{WEB}/bastidores/{pagina_da_referencia}", wait_until="networkidle")
    figuras = pagina.locator("figure.diagrama")
    esperadas = PAGINAS[pagina_da_referencia]
    if esperadas:
        pagina.wait_for_function(
            "(n) => [...document.querySelectorAll('figure.diagrama')].filter(f => f.dataset.zoom === 'pronto').length >= n",
            arg=esperadas,
            timeout=15_000,
        )
    assert figuras.count() == esperadas
    assert _violacoes(pagina) == []


def test_zoom_arrasto_e_tela_cheia_no_t_box(pagina):
    pagina.goto(f"{WEB}/bastidores/referencia/grafo/", wait_until="networkidle")
    tbox = pagina.locator("figure.diagrama", has=pagina.locator('svg[aria-label^="T-Box: os tipos"]'))
    tbox.wait_for()
    pagina.wait_for_function("document.querySelectorAll('figure.diagrama[data-zoom=pronto]').length >= 4")
    tbox.scroll_into_view_if_needed()
    escala = float(tbox.get_attribute("data-escala"))

    tbox.get_by_role("button", name="Aproximar").click()
    tbox.get_by_role("button", name="Aproximar").click()
    assert float(tbox.get_attribute("data-escala")) > escala * 1.5

    # Teclado: 0 enquadra de novo.
    tbox.locator(".diagrama__palco").focus()
    pagina.keyboard.press("0")
    assert abs(float(tbox.get_attribute("data-escala")) - escala) < 0.05

    # Arrastar move o diagrama (o grupo de viewport do svg-pan-zoom muda de transformação).
    palco = tbox.locator(".diagrama__palco").bounding_box()
    viewport = tbox.locator("svg .svg-pan-zoom_viewport")
    antes = viewport.get_attribute("transform")
    pagina.mouse.move(palco["x"] + palco["width"] / 2, palco["y"] + palco["height"] / 2)
    pagina.mouse.down()
    pagina.mouse.move(palco["x"] + palco["width"] / 2 + 120, palco["y"] + palco["height"] / 2 + 60, steps=5)
    pagina.mouse.up()
    assert viewport.get_attribute("transform") != antes

    tbox.get_by_role("button", name="Tela cheia").click()
    pagina.wait_for_function("document.fullscreenElement && document.fullscreenElement.matches('figure.diagrama')")
    assert "diagrama--tela-cheia" in tbox.get_attribute("class")
    pagina.evaluate("document.exitFullscreen()")

    link = tbox.get_by_role("link", name="Abrir o SVG")
    assert link.get_attribute("href").endswith("assets/diagramas/tbox.svg")


def test_numeros_e_codigo_gerados_no_build(pagina):
    pagina.goto(f"{WEB}/bastidores/referencia/grafo/", wait_until="networkidle")
    texto = pagina.locator("article").inner_text()
    # Os números vêm do build (fragmentos gerados), e o Cypher, do código do contexto-mcp.
    assert re.search(r"\d+ entidades, \d+ relações", texto)
    assert "EXIGE|REQUER|SUJEITA_A|REGIDO_POR*1..2" in texto
    pagina.goto(f"{WEB}/bastidores/referencia/skills-prompts-tools/", wait_until="networkidle")
    assert re.search(r"O gateway expõe \d+ tools de \d+ servidores", pagina.locator("article").inner_text())
