"""Navegador e utilidades dos testes e2e: tudo pela porta do web, como a plateia veria."""

import json
import os
import urllib.request

import pytest
from playwright.sync_api import Page, sync_playwright

WEB = os.environ.get("WEB_URL", "http://web")
# WebGL por software (o container não tem GPU).
ARGS = ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"]


def simulador(caminho: str) -> dict:
    """POST no simulador pelo proxy do web (o mesmo caminho do botão de cena)."""
    pedido = urllib.request.Request(f"{WEB}/simulador{caminho}", method="POST")
    with urllib.request.urlopen(pedido, timeout=60) as resposta:
        return json.load(resposta)


@pytest.fixture(scope="session")
def navegador():
    with sync_playwright() as p:
        b = p.chromium.launch(args=ARGS)
        yield b
        b.close()


@pytest.fixture
def pagina(navegador) -> Page:
    contexto = navegador.new_context(viewport={"width": 1600, "height": 1000})
    pg = contexto.new_page()
    erros: list[str] = []
    pg.on("pageerror", lambda e: erros.append(str(e)))
    pg.erros = erros  # type: ignore[attr-defined]
    yield pg
    contexto.close()
    assert not erros, f"Erros de JavaScript na página: {erros}"


@pytest.fixture
def mundo_limpo():
    simulador("/reset")
    yield
    simulador("/reset")


def viajar_pelo_roteiro(pg: Page, modo: str = "Com skill (GPS)", limite_s: int = 90) -> int:
    """Inicia uma viagem pelo roteiro na barra do mapa e responde pela Ana até o fim."""
    pg.click("#viagem-modo")
    pg.get_by_role("option", name=modo).click()
    pg.click("#viagem-modelo")
    pg.get_by_role("option", name="Roteiro (ensaio sem LLM)").click()
    pg.click("#iniciar-viagem")
    pg.wait_for_function("document.querySelector('.mapa').dataset.execucao !== ''")
    respostas = 0
    for _ in range(limite_s * 2):
        pg.wait_for_timeout(500)
        # Só os botões ligados: depois de responder, eles ficam desligados até a próxima pergunta.
        opcoes = pg.locator(".mapa__opcoes button:not([disabled])")
        if opcoes.count():
            opcoes.first.click()
            respostas += 1
            pg.wait_for_timeout(500)
        if pg.locator("#iniciar-viagem").is_enabled():
            return respostas
    raise AssertionError("A viagem não terminou no tempo limite.")


def esperar_a_fila(pg: Page, limite_s: int = 120) -> None:
    """Espera o diretor de animações mostrar todos os eventos da viagem."""
    pg.wait_for_function(
        "document.querySelector('.mapa').dataset.fila === '0'", timeout=limite_s * 1000
    )
