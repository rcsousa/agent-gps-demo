"""Capturas e vídeos de cada cena para os bastidores, tocando as gravações reais (replay, sem tokens).

Uso: ./scripts/capturar-cenas.sh [cena ...]      # padrão: todas
Saída: services/docs/conteudo/assets/cenas/cena-<n>.webm (vídeo curto, em loop) e cena-<n>.png (capa).

O roteiro de cada clipe fica aqui, legível: o que tocar, em que visão e qual momento vira a capa.
"""

import json
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

import sessao

WEB = "http://web"
SAIDA = Path("/saida")
TAMANHO = {"width": 1280, "height": 800}
DURACAO_DO_CLIPE_S = 22
ARGS = ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"]

# cena → (gravação, visão, o que esperar para a capa)
VIDEOS = {
    "2": ("cena-2", "mapa", "fim"),
    "3": ("cena-3", "mapa", "fim"),
    "5": ("cena-5", "mapa", "parada-cotacao"),
    "6": ("cena-6", "mapa", "incidente"),
    "7": ("cena-7", "mapa", "pedagio"),
}
# Capturas paradas: a cidade (1), o protocolo no Raio-X (4) e o placar (8).
CAPTURAS = ("1", "4", "8")


# Os vídeos e capturas correm sozinhos: sem esperar o apresentador nos balões.
PASSO_A_PASSO_DESLIGADO = "localStorage.setItem('bussola:passo-a-passo', 'nao')"

def simulador(caminho: str) -> None:
    urllib.request.urlopen(urllib.request.Request(f"{WEB}/simulador{caminho}", method="POST"), timeout=60).read()


def _momento(pg: Page, alvo: str) -> bool:
    mapa = pg.locator(".mapa")
    if alvo == "fim":
        return pg.locator(".mapa").get_attribute("data-fila") == "0" and bool(
            pg.evaluate("document.querySelector('.linha-do-tempo__narracao')?.innerText.startsWith('Chegada') || "
                        "document.querySelector('.linha-do-tempo__narracao')?.innerText.startsWith('Viagem')")
        )
    if alvo == "incidente":
        return pg.locator(".linha-do-tempo__parada--incidente").count() > 0
    if alvo == "pedagio":
        return pg.locator('[data-rotulo="pedagio"]').count() > 0
    return mapa.get_attribute("data-parada") == alvo


def video(navegador, cena: str) -> None:
    gravacao, visao, alvo = VIDEOS[cena]
    pasta = Path(tempfile.mkdtemp())
    contexto = navegador.new_context(viewport=TAMANHO, record_video_dir=str(pasta), record_video_size=TAMANHO)
    contexto.add_cookies(sessao.cookies(WEB))
    contexto.add_init_script(PASSO_A_PASSO_DESLIGADO)
    pg = contexto.new_page()
    url = f"{WEB}/mapa?gravacao={gravacao}&cena={cena}" + ("&visao=raio-x" if visao == "raio-x" else "")
    pg.goto(url, wait_until="load")
    pg.wait_for_function("document.querySelector('.mapa').dataset.execucao.startsWith('gravacao:')", timeout=30000)
    capa = False
    for _ in range(400):  # até ~200 s: o replay toca no ritmo original, com o diretor de animações
        pg.wait_for_timeout(500)
        if not capa and _momento(pg, alvo):
            pg.wait_for_timeout(1200)
            pg.screenshot(path=str(SAIDA / f"cena-{cena}.png"))
            capa = True
        if pg.locator(".mapa").get_attribute("data-fila") == "0" and pg.evaluate(
            "document.querySelector('.linha-do-tempo__narracao')?.innerText.startsWith('Chegada') || "
            "document.querySelector('.linha-do-tempo__narracao')?.innerText.startsWith('Viagem')"
        ):
            pg.wait_for_timeout(2500)
            break
    if not capa:
        pg.screenshot(path=str(SAIDA / f"cena-{cena}.png"))
    bruto = Path(pg.video.path())
    contexto.close()
    _comprimir(bruto, SAIDA / f"cena-{cena}.webm")
    shutil.rmtree(pasta, ignore_errors=True)


def _duracao(arquivo: Path) -> float:
    saida = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(arquivo)],
        capture_output=True, check=True, text=True,
    ).stdout
    return float(json.loads(saida)["format"]["duration"])


def _comprimir(bruto: Path, destino: Path) -> None:
    """Acelera a viagem inteira para caber em ~22 s e comprime em VP9, sem som."""
    fator = max(_duracao(bruto) / DURACAO_DO_CLIPE_S, 1.0)
    subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error", "-i", str(bruto),
            "-vf", f"setpts=PTS/{fator:.3f},fps=24,scale=1280:-2",
            "-an", "-c:v", "libvpx-vp9", "-b:v", "0", "-crf", "40", "-row-mt", "1", "-deadline", "good",
            str(destino),
        ],
        check=True,
    )
    print(f"  {destino.name}: {destino.stat().st_size / 1e6:.1f} MB (acelerado {fator:.1f}×)", flush=True)


def captura(navegador, cena: str) -> None:
    pg = navegador.new_page(viewport=TAMANHO)
    pg.add_init_script(PASSO_A_PASSO_DESLIGADO)
    if cena == "1":
        pg.goto(f"{WEB}/mapa?cena=1", wait_until="networkidle")
        pg.wait_for_timeout(3000)
    else:
        pg.goto(f"{WEB}/mapa?gravacao=cena-5&cena={cena}&visao=raio-x", wait_until="load")
        pg.wait_for_function(
            "[...document.querySelectorAll('.raiox__titulo')].some(e => e.innerText.startsWith('rota planejada'))",
            timeout=120000,
        )
        if cena == "8":
            pg.get_by_role("button", name="Pular para o fim").click()
            pg.wait_for_function("document.querySelector('.mapa').dataset.fila === '0'", timeout=60000)
            pg.get_by_role("tab", name="Placar").click()
            pg.wait_for_timeout(2000)
        else:
            pg.wait_for_timeout(1500)
    pg.screenshot(path=str(SAIDA / f"cena-{cena}.png"))
    pg.close()


def main() -> None:
    sessao.instalar_no_urllib()  # as chamadas ao web levam o cookie da sessão
    cenas = sys.argv[1:] or [*CAPTURAS, *VIDEOS]
    SAIDA.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        navegador = p.chromium.launch(args=ARGS)
        for cena in sorted(cenas):
            print(f"cena {cena}", flush=True)
            simulador("/reset")
            video(navegador, cena) if cena in VIDEOS else captura(navegador, cena)
        navegador.close()
    simulador("/reset")


if __name__ == "__main__":
    main()
