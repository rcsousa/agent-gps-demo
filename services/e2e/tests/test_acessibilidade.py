"""Acessibilidade (WCAG AA): o axe-core audita as telas da demo. Violações sérias e críticas falham."""

import pytest
from axe_playwright_python.sync_playwright import Axe
from conftest import WEB

AXE = Axe()
GRAVES = {"serious", "critical"}


def _violacoes(pagina) -> list[str]:
    resultado = AXE.run(pagina, options={"runOnly": {"type": "tag", "values": ["wcag2a", "wcag2aa", "wcag21aa"]}})
    return [
        f"{v['id']} ({v['impact']}): {v['help']} · {[n['target'] for n in v['nodes'][:3]]}"
        for v in resultado.response["violations"]
        if v["impact"] in GRAVES
    ]


@pytest.mark.parametrize(
    "caminho",
    ["/", "/mapa", "/mapa?visao=raio-x", "/status"],
)
def test_telas_sem_violacoes_graves(pagina, caminho):
    pagina.goto(f"{WEB}{caminho}", wait_until="networkidle")
    pagina.wait_for_timeout(2500)
    assert _violacoes(pagina) == []


def test_painel_do_apresentador_sem_violacoes_graves(pagina):
    pagina.goto(f"{WEB}/mapa?cena=6", wait_until="networkidle")
    pagina.keyboard.press("p")
    pagina.locator(".apresentador").wait_for()
    pagina.wait_for_timeout(1500)
    assert _violacoes(pagina) == []


def test_modo_telao_pela_tecla_t_e_os_atalhos_pela_tecla_interrogacao(pagina):
    pagina.goto(f"{WEB}/mapa", wait_until="networkidle")
    fonte = "getComputedStyle(document.documentElement).fontSize"
    assert pagina.evaluate(fonte) == "16px"
    pagina.keyboard.press("t")
    assert pagina.evaluate(fonte) == "20px"
    # Fica guardado: ao recarregar, o telão continua ligado.
    pagina.reload(wait_until="networkidle")
    assert pagina.evaluate(fonte) == "20px"
    pagina.keyboard.press("t")
    assert pagina.evaluate(fonte) == "16px"

    pagina.keyboard.press("?")
    atalhos = pagina.get_by_role("dialog", name="Atalhos de teclado")
    atalhos.wait_for()
    assert "modo telão" in atalhos.inner_text()
    pagina.keyboard.press("Escape")
    atalhos.wait_for(state="hidden")
