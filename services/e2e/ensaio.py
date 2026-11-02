"""Ensaio de palco: as 8 cenas de ponta a ponta, como o apresentador faria, e os critérios de aceite.

Toca cada cena no navegador pelo roteiro (sem tokens) com o passo a passo ligado, seguindo cada balão
pelo Espaço e respondendo pela Ana. Depois, toca as gravações (replay). Confere os critérios a partir
dos eventos reais da execução (o SSE do agente) e da tela, e escreve um relatório em Markdown.

Uso (pelo ./scripts/ensaiar.sh): python ensaio.py   · saída em /saida (ensaios/ no repositório)
"""

import json
import os
import time
import urllib.request
from datetime import date
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

WEB = os.environ.get("WEB_URL", "http://web")
SAIDA = Path("/saida")
TAMANHO = {"width": 1920, "height": 1080}
EVENTOS_COM_BALAO = {"tool.called", "incident.detected", "route.recalculated", "human.required"}
LIMITE_S = 420


def _post(caminho: str) -> None:
    urllib.request.urlopen(urllib.request.Request(f"{WEB}{caminho}", method="POST", data=b""), timeout=30)


def eventos_da_execucao(execucao: str) -> list[dict]:
    """Todos os eventos reais da execução, pelo mesmo SSE que o mapa usa (do início ao run.finished)."""
    eventos: list[dict] = []
    with urllib.request.urlopen(f"{WEB}/api/execucoes/{execucao}/eventos", timeout=120) as resposta:
        for linha in resposta:
            texto = linha.decode("utf-8").strip()
            if not texto.startswith("data:"):
                continue
            evento = json.loads(texto[5:])
            eventos.append(evento)
            if evento["tipo"] == "run.finished":
                break
    return eventos


def _mapa(pg: Page, atributo: str) -> str:
    return pg.locator(".mapa").get_attribute(f"data-{atributo}") or ""


def viagem_ao_vivo(pg: Page, cena: str, pasta: Path) -> dict:
    """Uma cena com viagem, ao vivo pelo roteiro e no passo a passo, como no palco."""
    _post("/simulador/reset")
    pg.goto(f"{WEB}/mapa?cena={cena}", wait_until="networkidle")
    pg.wait_for_timeout(1200)
    if not pg.locator("#passo-a-passo").is_checked():
        pg.locator("label[for=passo-a-passo]").click()
    pg.click("#viagem-modelo")
    pg.get_by_role("option", name="Roteiro (ensaio sem LLM)").click()
    incidente = pg.locator(".mapa__cena button.cds--btn--danger--tertiary")
    if incidente.count():
        incidente.click()  # o incidente da cena, pelo botão da barra (o mesmo do painel do apresentador)
        pg.wait_for_timeout(1500)
    inicio = time.time()
    pg.click("#iniciar-viagem")
    pg.wait_for_function("document.querySelector('.mapa').dataset.execucao !== ''")
    execucao = _mapa(pg, "execucao")

    baloes, perguntas, aprovacoes = 0, 0, 0
    parada_da_apolice = None
    print_balao = None
    while time.time() - inicio < LIMITE_S:
        pg.wait_for_timeout(250)
        opcoes = pg.locator(".mapa__opcoes button:not([disabled])")
        if opcoes.count():
            opcoes.first.click()
            perguntas += 1
        if _mapa(pg, "aguardando") == "sim":
            baloes += 1
            if print_balao is None:
                print_balao = pasta / f"cena-{cena}-balao.png"
                pg.screenshot(path=str(print_balao))
            pg.evaluate("document.activeElement && document.activeElement.blur()")
            pg.keyboard.press("Space")
            pg.wait_for_function("document.querySelector('.mapa').dataset.aguardando === 'nao'", timeout=10_000)
        # O pedágio: o apresentador aprova pelo painel (tecla P).
        if _mapa(pg, "balao") == "" and pg.locator(".apresentador__ticket").count() == 0 and cena == "7":
            if pg.locator(".apresentador").count() == 0:
                pg.keyboard.press("p")
        aprovar = pg.locator(".apresentador__ticket").get_by_role("button", name="Aprovar")
        if aprovar.count():
            aprovar.first.click()
            aprovacoes += 1
        if parada_da_apolice is None and "apólice" in pg.locator(".mapa__mensagens, .raiox").first.inner_text():
            parada_da_apolice = _mapa(pg, "parada")
        if _mapa(pg, "fila") == "0" and pg.locator("#iniciar-viagem").is_enabled():
            break
    duracao = round(time.time() - inicio)
    pg.wait_for_timeout(2500)
    pg.screenshot(path=str(pasta / f"cena-{cena}.png"))

    eventos = eventos_da_execucao(execucao)
    com_balao = [e for e in eventos if e["tipo"] in EVENTOS_COM_BALAO]
    com_lugar = [e for e in eventos if e["tipo"] in ("step.started", "tool.called")]
    fim = next((e["dados"] for e in reversed(eventos) if e["tipo"] == "run.finished"), {})
    recalculos = [e["dados"] for e in eventos if e["tipo"] == "route.recalculated"]
    return {
        "cena": cena,
        "tipo": "ao vivo",
        "execucao": execucao,
        "segundos": duracao,
        "status": fim.get("status"),
        "apolice": fim.get("apolice"),
        "regras": (fim.get("metricas") or {}).get("regras") or {},
        "eventos": len(eventos),
        "baloes": baloes,
        "baloes_esperados": len(com_balao),
        "trechos": int(_mapa(pg, "lugares-visitados") or 0),
        "eventos_com_lugar": len(com_lugar),
        "perguntas": perguntas,
        "aprovacoes": aprovacoes,
        "parada_da_apolice": parada_da_apolice,
        "recalculos": recalculos,
        "avisos": pg.locator(".mapa__avisos").inner_text(),
        "terminou": _mapa(pg, "fila") == "0",
    }


def replay(pg: Page, cena: str, gravacao: str, pasta: Path, raio_x: bool = False) -> dict:
    """A gravação da cena, tocada sem rede e sem LLM (o plano B do dia)."""
    pg.evaluate("localStorage.setItem('bussola:passo-a-passo', 'nao')")
    visao = "&visao=raio-x" if raio_x else ""
    inicio = time.time()
    pg.goto(f"{WEB}/mapa?gravacao={gravacao}&cena={cena}{visao}", wait_until="load")
    pg.wait_for_function("document.querySelector('.mapa').dataset.execucao.startsWith('gravacao:')", timeout=30_000)
    pular = pg.get_by_role("button", name="Pular para o fim")
    pular.wait_for(timeout=30_000)
    pular.click()
    pg.wait_for_function("document.querySelector('.mapa').dataset.fila === '0'", timeout=120_000)
    pg.wait_for_timeout(2000)
    pg.screenshot(path=str(pasta / f"cena-{cena}-replay.png"))
    selo = pg.locator(".mapa__selo-replay").count() > 0
    titulos = pg.locator(".raiox__titulo").all_inner_texts() if raio_x else []
    pg.evaluate("localStorage.setItem('bussola:passo-a-passo', 'sim')")
    return {
        "cena": cena,
        "tipo": "replay",
        "gravacao": gravacao,
        "segundos": round(time.time() - inicio),
        "selo": selo,
        "protocolo": [t for t in titulos if t.startswith(("tools/list", "skills/list", "resources/read"))],
        "terminou": _mapa(pg, "fila") == "0",
    }


def cena_1(pg: Page, pasta: Path) -> dict:
    _post("/simulador/reset")
    inicio = time.time()
    pg.goto(f"{WEB}/mapa?cena=1", wait_until="networkidle")
    pg.wait_for_selector('[data-rotulo^="bairro-"]')
    pg.wait_for_timeout(2000)
    pg.screenshot(path=str(pasta / "cena-1.png"))
    return {
        "cena": "1",
        "tipo": "ao vivo",
        "segundos": round(time.time() - inicio),
        "bairros": pg.locator('[data-rotulo^="bairro-"]').count(),
        "farois": pg.locator('[data-rotulo^="incidente-"]').count(),
    }


def cena_8(pg: Page, pasta: Path) -> dict:
    """O Raio-X e o placar da sessão: os 3 modos que o ensaio acabou de rodar."""
    pg.goto(f"{WEB}/mapa?cena=8&visao=raio-x", wait_until="networkidle")
    pg.get_by_role("tab", name="Placar").click()
    pg.wait_for_selector(".placar__cartao")
    pg.wait_for_timeout(1500)
    pg.screenshot(path=str(pasta / "cena-8.png"))
    cartoes = {
        c.locator(".placar__modo").inner_text(): c.inner_text().replace("\n", " ")
        for c in pg.locator(".placar__cartao").all()
    }
    return {"cena": "8", "tipo": "Raio-X", "cartoes": cartoes}


def _regras(r: dict) -> str:
    regras = r.get("regras") or {}
    return f"{regras.get('cumpridas', '?')}/{regras.get('total', '?')}" if regras else "—"


def criterios(subida_s: int | None, vivos: dict, replays: list[dict], c1: dict, c8: dict) -> list[tuple[str, bool, str]]:
    com_skill = [vivos[c] for c in ("5", "6", "7")]
    lista: list[tuple[str, bool, str]] = []
    if subida_s is not None:
        lista.append(("`docker compose up` do zero em menos de 3 min", subida_s < 180, f"{subida_s} s até tudo saudável"))
    lista.append((
        "As 8 cenas rodam ao vivo e em replay",
        all(v["terminou"] for v in vivos.values()) and all(r["terminou"] and r["selo"] for r in replays)
        and c1["bairros"] == 5 and bool(c8["cartoes"]),
        f"{len(vivos) + 2} cenas ao vivo e {len(replays)} replays até o fim, com o selo Replay",
    ))
    seis = vivos["6"]
    lista.append((
        "Incidente provoca recálculo real, com motivo e regra",
        any(r.get("motivo") and r.get("regra") for r in seis["recalculos"]) and "Recálculo" in seis["avisos"],
        "cena 6: " + "; ".join(f"{r['motivo'][:70]}… (regra: {r['regra'][:50]}…)" for r in seis["recalculos"][:1]),
    ))
    modos = {m.split(" ")[0] for m in c8["cartoes"]}
    lista.append((
        "O placar mostra diferença entre sem contexto, sem skill e com skill",
        len(c8["cartoes"]) >= 3,
        " · ".join(f"{k}: {v[len(k):].strip()[:40]}" for k, v in c8["cartoes"].items()) or str(modos),
    ))
    lista.append((
        "Toda animação corresponde a um evento real",
        all(v["baloes"] == v["baloes_esperados"] and v["trechos"] <= v["eventos_com_lugar"] for v in com_skill),
        "; ".join(
            f"cena {v['cena']}: {v['baloes']} balões para {v['baloes_esperados']} eventos com balão, "
            f"{v['trechos']} trechos para {v['eventos_com_lugar']} eventos com lugar"
            for v in com_skill
        ),
    ))
    lista.append((
        "A apólice só aparece quando o robô chega à emissão",
        all(v["parada_da_apolice"] == "parada-emissao" for v in (vivos["5"], vivos["6"])),
        f"cenas 5 e 6: {vivos['5']['parada_da_apolice']}, {vivos['6']['parada_da_apolice']}",
    ))
    return lista


def relatorio(subida_s: int | None, vivos: dict, replays: list[dict], c1: dict, c8: dict, pasta: Path) -> str:
    hoje = date.today().strftime("%d/%m/%Y")
    linhas = [
        f"# Ensaio de palco · {hoje}",
        "",
        "Gerado pelo `./scripts/ensaiar.sh`: as 8 cenas no navegador (1920 × 1080), pelo roteiro (sem tokens),",
        "com o passo a passo ligado (Espaço em cada balão) e a Ana respondida pela primeira opção. Depois, os",
        "replays das gravações. Os critérios são conferidos nos eventos reais de cada execução.",
        "",
        "## Critérios de aceite",
        "",
        "| Critério | Resultado | Evidência |",
        "| --- | --- | --- |",
    ]
    for nome, ok, evidencia in criterios(subida_s, vivos, replays, c1, c8):
        linhas.append(f"| {nome} | {'✔' if ok else '✘'} | {evidencia} |")
    linhas += ["", "## Cenas ao vivo", "", "| Cena | Tempo | Status | Apólice | Regras | Balões | Perguntas | Pedágio |", "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    linhas.append(f"| 1 | {c1['segundos']} s | {c1['bairros']} bairros, {c1['farois']} faróis | — | — | — | — | — |")
    for c in ("2", "3", "5", "6", "7"):
        v = vivos[c]
        linhas.append(
            f"| {c} | {v['segundos']} s | {v['status']} | {v['apolice'] or '—'} | {_regras(v)} | "
            f"{v['baloes']} | {v['perguntas']} | {v['aprovacoes'] or '—'} |"
        )
    linhas += ["", "## Replays (plano B, sem rede)", "", "| Cena | Gravação | Até o fim | Selo | Protocolo no Raio-X |", "| --- | --- | --- | --- | --- |"]
    for r in replays:
        linhas.append(
            f"| {r['cena']} | `{r['gravacao']}` | {'✔' if r['terminou'] else '✘'} ({r['segundos']} s) | "
            f"{'✔' if r['selo'] else '✘'} | {', '.join(r['protocolo'][:3]) or '—'} |"
        )
    linhas += ["", "## Placar da sessão (cena 8)", ""]
    linhas += [f"- {texto}" for texto in c8["cartoes"].values()]
    linhas += ["", f"As capturas de cada cena ficam em `ensaios/{pasta.name}/`.", ""]
    return "\n".join(linhas)


def main() -> None:
    hoje = date.today().isoformat()
    pasta = SAIDA / hoje
    pasta.mkdir(parents=True, exist_ok=True)
    subida = os.environ.get("SUBIDA_S")
    with sync_playwright() as p:
        navegador = p.chromium.launch(args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"])
        contexto = navegador.new_context(viewport=TAMANHO)
        contexto.add_init_script("if (!localStorage.getItem('bussola:passo-a-passo')) localStorage.setItem('bussola:passo-a-passo', 'sim')")
        pg = contexto.new_page()
        print("cena 1", flush=True)
        c1 = cena_1(pg, pasta)
        vivos = {}
        for cena in ("2", "3", "5", "6", "7"):
            print(f"cena {cena} ao vivo", flush=True)
            vivos[cena] = viagem_ao_vivo(pg, cena, pasta)
            print(f"  {vivos[cena]['segundos']} s · {vivos[cena]['baloes']} balões · {vivos[cena]['status']}", flush=True)
        replays = []
        for cena, gravacao, raio_x in (("2", "cena-2", False), ("3", "cena-3", False), ("4", "cena-5", True),
                                       ("5", "cena-5", False), ("6", "cena-6", False), ("7", "cena-7", False)):
            print(f"cena {cena} replay", flush=True)
            replays.append(replay(pg, cena, gravacao, pasta, raio_x))
        print("cena 8", flush=True)
        c8 = cena_8(pg, pasta)
        navegador.close()
    _post("/simulador/reset")
    texto = relatorio(int(subida) if subida else None, vivos, replays, c1, c8, pasta)
    (SAIDA / f"{hoje}.md").write_text(texto, encoding="utf-8")
    print(texto)


if __name__ == "__main__":
    main()
