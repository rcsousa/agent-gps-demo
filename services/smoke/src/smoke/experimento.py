"""Experimento com o modelo real: sem_skill x com_skill em cada incidente.

Para cada (incidente, modo): volta o mundo ao estado-base, aplica o incidente, roda a
execução respondendo pela Ana e confere, pelos eventos do barramento, se o agente
seguiu a regra do banco. Gasta tokens de verdade: rode só quando quiser medir.

Uso (pelo script):
  ./scripts/experimento.sh rodar [--modelo M] [--repeticoes N] [--a-partir-de K] [caso ...]
      # grava em experimentos/<data>-<modelo>/<caso>__<modo>__r<N>.json
  ./scripts/experimento.sh analisar <pasta>          # regras por caso e modo, somando as repetições
  ./scripts/experimento.sh comparar <pasta> ...      # modelo × skill: regras, pior execução e custo
A Ana responde a primeira opção sugerida, exceto na alçada, em que ela quer proteger
também a coleção de arte que declarou.
"""

import json
import pathlib
import sys
import time
from datetime import date
from typing import Any

import httpx

from bussola_comum.regras import CASOS, regras

WEB = "http://web"
SAIDA = pathlib.Path("/saida")
INCIDENTES = CASOS  # o caminho feliz (sem incidente) e os incidentes
MODOS = ["sem_skill", "com_skill"]
FOLGA_S = 20  # o deployment tem limite de tokens por minuto


# --- Rodar --------------------------------------------------------------------------


# Na alçada, a Ana quer proteger também a coleção de arte que declarou: escolhe a opção que a inclui
# (ou o especialista) e nunca a que a deixa de fora.
QUER_A_ARTE = ("arte", "coleção", "colecao", "1.800.000", "1,8 milh", "especialista")
DEIXA_A_ARTE = ("não tenho", "nao tenho", "só o apartamento", "só com o apartamento", "apenas o apartamento")


def _resposta_da_ana(incidente: str, opcoes: list[str]) -> str:
    if incidente == "alcada-ana-excedida":

        def quer(o: str) -> bool:
            texto = o.lower()
            return any(p in texto for p in QUER_A_ARTE) and not any(p in texto for p in DEIXA_A_ARTE)

        return next((o for o in opcoes if quer(o)), opcoes[0])
    return opcoes[0]


def rodar(
    incidente: str, modo: str, pasta: pathlib.Path, modelo: str | None, repeticao: int
) -> dict[str, Any]:
    httpx.post(f"{WEB}/simulador/reset", timeout=30)
    if incidente != "caminho-feliz":
        httpx.post(f"{WEB}/simulador/incidentes/{incidente}/aplicar", timeout=30)
    corpo = {"modo": modo, **({"modelo": modelo} if modelo else {})}
    resposta_inicio = httpx.post(f"{WEB}/api/execucoes", json=corpo, timeout=30)
    resposta_inicio.raise_for_status()
    ident = resposta_inicio.json()["id"]
    eventos: list[dict] = []
    inicio = time.time()
    with httpx.stream("GET", f"{WEB}/api/execucoes/{ident}/eventos", timeout=1800) as resposta:
        for linha in resposta.iter_lines():
            if not linha.startswith("data:"):
                continue
            evento = json.loads(linha[5:])
            eventos.append(evento)
            if evento["tipo"] == "client.asked":
                texto = _resposta_da_ana(incidente, evento["dados"].get("opcoes") or ["Sim"])
                httpx.post(f"{WEB}/api/execucoes/{ident}/resposta", json={"texto": texto}, timeout=30)
            if evento["tipo"] == "run.finished":
                break
    resultado = {"incidente": incidente, "modo": modo, "id": ident, "segundos": round(time.time() - inicio)}
    (pasta / f"{incidente}__{modo}__r{repeticao}.json").write_text(
        json.dumps({**resultado, "eventos": eventos}, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    return resultado


# --- Analisar -----------------------------------------------------------------------


def precos() -> dict[str, Any] | None:
    """Preços atuais do agente (US$ por milhão de tokens e fatores de cache). None se não houver."""
    try:
        dados = httpx.get(f"{WEB}/api/llm/modelo", timeout=10).json()
    except (httpx.HTTPError, ValueError):
        return None
    return {
        "modelos": {m["id"]: m["precos"] for m in dados["modelos"] if m["precos"]},
        "cache": dados["cache"],
    }


def custo_usd(modelo: str, tokens: dict[str, int], tabela: dict[str, Any] | None) -> dict[str, float] | None:
    """Mesma conta do agente (agent.custos), a partir dos tokens gravados: com e sem cache."""
    preco = (tabela or {}).get("modelos", {}).get(modelo)
    if not preco:
        return None
    entrada, saida = preco["entrada"] / 1_000_000, preco["saida"] / 1_000_000
    cache = tabela["cache"]
    total = (
        tokens.get("entrada", 0) * entrada
        + tokens.get("cache_leitura", 0) * entrada * cache["leitura"]
        + tokens.get("cache_escrita", 0) * entrada * cache["escrita"]
        + tokens.get("saida", 0) * saida
    )
    toda_a_entrada = sum(tokens.get(k, 0) for k in ("entrada", "cache_leitura", "cache_escrita"))
    return {"total": total, "sem_cache": toda_a_entrada * entrada + tokens.get("saida", 0) * saida}


def carregar(pasta: pathlib.Path, tabela: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Cada execução gravada, já conferida: caso, modo, modelo, regras e custo."""
    return [registro(json.loads(a.read_text(encoding="utf-8")), tabela) for a in sorted(pasta.glob("*.json"))]


def registro(r: dict[str, Any], tabela: dict[str, Any] | None = None) -> dict[str, Any]:
    eventos = r["eventos"]
    inicio = next((e["dados"] for e in eventos if e["tipo"] == "run.started"), {})
    fim = eventos[-1]["dados"]
    tokens = fim["metricas"]["tokens"]
    custo = custo_usd(inicio.get("modelo", "?"), tokens, tabela)
    return {
        "custo": custo["total"] if custo else 0.0,
        "custo_sem_cache": custo["sem_cache"] if custo else 0.0,
        "caso": r["incidente"],
        "modo": r["modo"],
        "modelo": inicio.get("modelo", "?"),
        "regras": regras(r["incidente"], eventos),
        "apolice": fim["apolice"],
        "chamadas": fim["metricas"]["chamadas_tool"],
        "segundos": r["segundos"],
        "entrada": tokens["entrada"] + tokens["cache_leitura"] + tokens["cache_escrita"],
        "saida": tokens["saida"],
    }


def _somar(grupo: dict[str, Any], r: dict[str, Any]) -> None:
    cumpridas, total = sum(r["regras"].values()), len(r["regras"])
    grupo["cumpridas"] += cumpridas
    grupo["total"] += total
    grupo["execucoes"] += 1
    grupo["perfeitas"] += cumpridas == total
    grupo["pior"] = min(grupo["pior"], cumpridas / total if total else 1.0)
    for chave in ("segundos", "entrada", "saida", "custo", "custo_sem_cache"):
        grupo[chave] += r[chave]
    for nome, ok in r["regras"].items():
        if not ok:
            grupo["falhas"][nome] = grupo["falhas"].get(nome, 0) + 1


def _vazio() -> dict[str, Any]:
    return {
        "cumpridas": 0,
        "total": 0,
        "execucoes": 0,
        "perfeitas": 0,
        "pior": 1.0,
        "segundos": 0,
        "entrada": 0,
        "saida": 0,
        "custo": 0.0,
        "custo_sem_cache": 0.0,
        "falhas": {},
    }


def agregar(registros: list[dict[str, Any]], por: tuple[str, ...]) -> dict[tuple, dict[str, Any]]:
    """Soma as repetições por chave (ex.: ("caso", "modo") ou ("modo",))."""
    grupos: dict[tuple, dict[str, Any]] = {}
    for r in registros:
        _somar(grupos.setdefault(tuple(r[k] for k in por), _vazio()), r)
    return grupos


def analisar(pasta: pathlib.Path) -> None:
    linhas = [
        "| Caso | Modo | Regras (somadas) | Execuções perfeitas | Pior execução | Tempo médio "
        "| Regras que falharam |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for (caso, modo), g in sorted(agregar(carregar(pasta), ("caso", "modo")).items()):
        falhas = "; ".join(f"{nome} ({n}x)" for nome, n in g["falhas"].items()) or "—"
        linhas.append(
            f"| {caso} | {modo} | {g['cumpridas']}/{g['total']} | {g['perfeitas']}/{g['execucoes']} "
            f"| {g['pior']:.0%} | {g['segundos'] / g['execucoes']:.0f} s | {falhas} |"
        )
    print("\n".join(linhas))


def _usd(valor: float, casas: int) -> str:
    """Dólares no formato brasileiro: US$ 1.234,5678."""
    texto = f"{valor:,.{casas}f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return f"US$ {texto}"


def comparar(pastas: list[pathlib.Path]) -> None:
    """Tabela modelo × skill: regras, execuções perfeitas, pior execução, tempo e custo (US$)."""
    tabela = precos()
    linhas = [
        "| Modelo | Modo | Regras cumpridas | Execuções perfeitas | Pior execução | Tempo médio "
        "| Custo por execução | 1.000 contratações | Custo por execução perfeita | Sem cache, por execução |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for pasta in pastas:
        registros = carregar(pasta, tabela)
        modelo = registros[0]["modelo"] if registros else pasta.name
        for (modo,), m in sorted(agregar(registros, ("modo",)).items()):
            n = m["execucoes"]
            por_perfeita = _usd(m["custo"] / m["perfeitas"], 4) if m["perfeitas"] else "nenhuma perfeita"
            linhas.append(
                f"| {modelo} | {modo} | {m['cumpridas']}/{m['total']} ({m['cumpridas'] / m['total']:.0%}) "
                f"| {m['perfeitas']}/{n} | {m['pior']:.0%} | {m['segundos'] / n:.0f} s "
                f"| {_usd(m['custo'] / n, 4)} | {_usd(1000 * m['custo'] / n, 2)} | {por_perfeita} "
                f"| {_usd(m['custo_sem_cache'] / n, 4)} |"
            )
    print("\n".join(linhas))


def _opcao(args: list[str], nome: str) -> str | None:
    if nome not in args:
        return None
    i = args.index(nome)
    valor = args[i + 1]
    del args[i : i + 2]
    return valor


def main() -> int:
    args = sys.argv[1:]
    if args[:1] == ["rodar"]:
        args = args[1:]
        modelo = _opcao(args, "--modelo")
        repeticoes = int(_opcao(args, "--repeticoes") or 1)
        primeira = int(_opcao(args, "--a-partir-de") or 1)
        pasta = SAIDA / f"{date.today().isoformat()}-{modelo or 'padrao'}"
        pasta.mkdir(parents=True, exist_ok=True)
        for repeticao in range(primeira, primeira + repeticoes):
            for incidente in args or INCIDENTES:
                for modo in MODOS:
                    r = rodar(incidente, modo, pasta, modelo, repeticao)
                    print(f"r{repeticao} {incidente:28} {modo:10} {r['segundos']} s", flush=True)
                    time.sleep(FOLGA_S)
        httpx.post(f"{WEB}/simulador/reset", timeout=30)
        analisar(pasta)
        return 0
    if args[:1] == ["analisar"] and len(args) > 1:
        analisar(SAIDA / args[1])
        return 0
    if args[:1] == ["comparar"] and len(args) > 1:
        comparar([SAIDA / a for a in args[1:]])
        return 0
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
