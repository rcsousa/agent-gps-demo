"""Fase 8: os bastidores ao lado da demo, os diagramas gerados e os vídeos das cenas."""

import re
import urllib.request

import pytest
from conftest import WEB


def test_bastidores_da_cena_abre_ao_lado_e_a_viagem_continua(pagina, mundo_limpo):
    pagina.goto(f"{WEB}/mapa?cena=6", wait_until="networkidle")
    pagina.click("#viagem-modelo")
    pagina.get_by_role("option", name="Roteiro (ensaio sem LLM)").click()
    pagina.click("#iniciar-viagem")
    pagina.wait_for_function("document.querySelector('.mapa').dataset.execucao !== ''")
    execucao = pagina.locator(".mapa").get_attribute("data-execucao")

    pagina.click("#bastidores-da-cena")
    quadro = pagina.locator(".bastidores__site")
    quadro.wait_for()
    assert quadro.get_attribute("src") == "/bastidores/04-bastidores-das-cenas/#cena-6"
    site = pagina.frame_locator(".bastidores__site")
    site.locator("#cena-6").wait_for()
    assert pagina.locator(".mapa").get_attribute("data-execucao") == execucao  # nada recarregou

    pagina.keyboard.press("Escape")
    quadro.wait_for(state="detached")
    assert pagina.locator(".mapa").get_attribute("data-execucao") == execucao


def test_tocar_esta_cena_a_partir_dos_bastidores(pagina, mundo_limpo):
    pagina.goto(f"{WEB}/mapa?cena=6", wait_until="networkidle")
    pagina.click("#bastidores-da-cena")
    site = pagina.frame_locator(".bastidores__site")
    site.locator('a[href="/mapa?gravacao=cena-6&cena=6"]').click()
    pagina.wait_for_url(re.compile(r"/mapa\?gravacao=cena-6"))
    pagina.wait_for_function(
        "document.querySelector('.mapa').dataset.execucao === 'gravacao:cena-6'", timeout=30000
    )


def test_area_de_bastidores_da_abertura_abre_o_painel(pagina):
    pagina.goto(f"{WEB}/", wait_until="networkidle")
    pagina.get_by_role("button", name=re.compile(r"^A skill é o GPS")).click()
    assert pagina.locator(".bastidores__site").get_attribute("src").startswith("/bastidores/03-skills-como-gps/")
    assert pagina.url.rstrip("/") == WEB  # continua na abertura


@pytest.mark.parametrize(
    "caminho",
    [
        "assets/diagramas/arquitetura.svg",
        "assets/diagramas/ontologia.svg",
        "assets/diagramas/rotas.svg",
        "assets/diagramas/skill-contratacao-seguro-residencial.svg",
        "assets/cenas/cena-6.webm",
        "assets/cenas/cena-6.png",
        "assets/cenas/cena-1.png",
    ],
)
def test_diagramas_e_videos_publicados(caminho):
    with urllib.request.urlopen(f"{WEB}/bastidores/{caminho}", timeout=10) as resposta:
        assert resposta.status == 200 and len(resposta.read()) > 1000
