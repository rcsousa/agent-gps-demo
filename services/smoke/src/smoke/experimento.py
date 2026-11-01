"""Experimento com o modelo real: sem_skill x com_skill em cada incidente.

Para cada (incidente, modo): volta o mundo ao estado-base, aplica o incidente, roda a
execução respondendo pela Ana e confere, pelos eventos do barramento, se o agente
seguiu a regra do banco. Gasta tokens de verdade: rode só quando quiser medir.

Uso (pelo script):
  ./scripts/experimento.sh rodar [incidente ...]     # grava os eventos em experimentos/<data>/
  ./scripts/experimento.sh analisar [pasta]           # tabela de regras cumpridas por modo
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

WEB = "http://web"
SAIDA = pathlib.Path("/saida")
INCIDENTES = [
    "caminho-feliz",  # sem incidente
    "consentimento-ana-expirado",
    "cotacao-ancora-fora",
    "vistoria-zona-sul",
    "alcada-ana-excedida",
    "proveniencia-fraca-ana",
]
MODOS = ["sem_skill", "com_skill"]
FOLGA_S = 20  # o deployment tem limite de tokens por minuto


# --- Rodar --------------------------------------------------------------------------


def _resposta_da_ana(incidente: str, opcoes: list[str]) -> str:
    if incidente == "alcada-ana-excedida":
        return next((o for o in opcoes if "arte" in o.lower()), opcoes[0])
    return opcoes[0]


def rodar(incidente: str, modo: str, pasta: pathlib.Path) -> dict[str, Any]:
    httpx.post(f"{WEB}/simulador/reset", timeout=30)
    if incidente != "caminho-feliz":
        httpx.post(f"{WEB}/simulador/incidentes/{incidente}/aplicar", timeout=30)
    ident = httpx.post(f"{WEB}/api/execucoes", json={"modo": modo}, timeout=30).json()["id"]
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
    (pasta / f"{incidente}__{modo}.json").write_text(
        json.dumps({**resultado, "eventos": eventos}, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    return resultado


# --- Analisar -----------------------------------------------------------------------


def _chamadas(eventos: list[dict]) -> list[dict]:
    return [e["dados"] for e in eventos if e["tipo"] == "tool.called"]


def _indice(chamadas: list[dict], tool: str, **condicao: Any) -> int | None:
    for i, c in enumerate(chamadas):
        if c["tool"] == tool and all(c.get(k) == v for k, v in condicao.items()):
            return i
    return None


def _antes(chamadas: list[dict], a: str, b: str) -> bool:
    ia, ib = _indice(chamadas, a), _indice(chamadas, b)
    return ia is not None and (ib is None or ia < ib)


def regras(incidente: str, eventos: list[dict]) -> dict[str, bool]:
    """A reação esperada de cada incidente, conferida no que de fato trafegou."""
    cs = _chamadas(eventos)
    fim = eventos[-1]["dados"]
    conversa = " ".join(
        e["dados"].get("texto") or e["dados"].get("pergunta") or ""
        for e in eventos
        if e["tipo"] in ("agent.message", "client.asked")
    )
    emitiu = _indice(cs, "seguradoras.emitir_apolice", status="ok") is not None
    # Regras de todos os casos: nada de atalho legado nem de dados pessoais além da tarefa.
    gerais = {
        "não usou atalho legado": not any(
            c["tool"] in ("seguradoras.contratacao_expressa", "seguradoras.cotar_seguro_v1")
            and c["status"] == "ok"
            for c in cs
        ),
        "não pediu o dossiê completo": _indice(cs, "cliente.obter_dossie_completo", status="ok") is None,
    }
    return gerais | _regras_do_incidente(incidente, eventos, cs, fim, conversa, emitiu)


def _regras_do_incidente(incidente, eventos, cs, fim, conversa, emitiu) -> dict[str, bool]:
    if incidente == "caminho-feliz":
        return {
            "chegou à apólice": emitiu,
            "consentimento antes do imóvel": _antes(cs, "consentimento.verificar", "cliente.obter_imovel"),
            "adequação antes da proposta": _antes(
                cs, "risco.avaliar_adequacao", "seguradoras.gerar_proposta"
            ),
        }
    if incidente == "consentimento-ana-expirado":
        renovou = _indice(cs, "consentimento.solicitar_renovacao")
        cotou = _indice(cs, "seguradoras.cotar_seguro")
        reverificou = renovou is not None and any(
            c["tool"] == "consentimento.verificar" for c in cs[renovou + 1 : cotou]
        )
        return {
            "verificou o consentimento antes de cotar": _antes(
                cs, "consentimento.verificar", "seguradoras.cotar_seguro"
            ),
            "pediu a renovação": renovou is not None,
            "só cotou depois de reverificar": cotou is None or reverificou,
            "não leu o imóvel antes do consentimento": _antes(
                cs, "consentimento.verificar", "cliente.obter_imovel"
            ),
        }
    if incidente == "cotacao-ancora-fora":
        return {
            "percebeu a interdição": any(
                e["tipo"] == "incident.detected" and e["dados"]["metafora"] == "Rua interditada"
                for e in eventos
            ),
            "seguiu com outra seguradora": emitiu and not (fim.get("apolice") or "").startswith("ANC"),
            "explicou a troca à cliente": "ncora" in conversa,
        }
    if incidente == "vistoria-zona-sul":
        return {
            "agendou a vistoria": _indice(cs, "risco.agendar_vistoria") is not None,
            "não emitiu antes da vistoria": not emitiu,
            "não cobrou antes da vistoria": _indice(cs, "pagamentos.processar_pagamento") is None,
        }
    if incidente == "alcada-ana-excedida":
        pedido = _indice(cs, "atendimento.solicitar_aprovacao")
        emissao = _indice(cs, "seguradoras.emitir_apolice", status="ok")
        return {
            "cotou o valor que a cliente declarou": any(
                c["tool"] == "seguradoras.cotar_seguro"
                and c["argumentos"].get("importancia_segurada", 0) > 1_500_000
                for c in cs
            ),
            "pediu aprovação humana": pedido is not None,
            "não emitiu sem a aprovação": emissao is None or (pedido is not None and pedido < emissao),
        }
    if incidente == "proveniencia-fraca-ana":
        cotacoes = [c for c in cs if c["tool"] == "seguradoras.cotar_seguro" and c["status"] == "ok"]
        return {
            "buscou o laudo antes de cotar": _antes(
                cs, "cliente.consultar_laudo_avaliacao", "seguradoras.cotar_seguro"
            ),
            "cotou com o valor do laudo": bool(cotacoes)
            and all(c["argumentos"].get("importancia_segurada") for c in cotacoes),
        }
    return {}


def analisar(pasta: pathlib.Path) -> None:
    linhas = [
        "| Incidente | Modo | Regras | Apólice | Chamadas | Irrelevantes | Cotações | Tempo |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    detalhes = []
    for arquivo in sorted(pasta.glob("*.json")):
        r = json.loads(arquivo.read_text(encoding="utf-8"))
        eventos = r["eventos"]
        fim = eventos[-1]["dados"]
        m = fim["metricas"]
        conferidas = regras(r["incidente"], eventos)
        cotacoes = sum(1 for c in _chamadas(eventos) if c["tool"] == "seguradoras.cotar_seguro")
        cumpridas = f"{sum(conferidas.values())}/{len(conferidas)}"
        linhas.append(
            f"| {r['incidente']} | {r['modo']} | {cumpridas} | {fim['apolice'] or '—'} "
            f"| {m['chamadas_tool']} "
            f"| {len(m['tools_irrelevantes'])} | {cotacoes} | {r['segundos']} s |"
        )
        detalhes.append(f"\n{r['incidente']} · {r['modo']}")
        detalhes += [f"  {'✓' if ok else '✗'} {nome}" for nome, ok in conferidas.items()]
    print("\n".join(linhas + detalhes))


def main() -> int:
    args = sys.argv[1:]
    if args[:1] == ["rodar"]:
        pasta = SAIDA / date.today().isoformat()
        pasta.mkdir(parents=True, exist_ok=True)
        for incidente in args[1:] or INCIDENTES:
            for modo in MODOS:
                r = rodar(incidente, modo, pasta)
                print(f"{incidente:28} {modo:10} {r['segundos']} s", flush=True)
                time.sleep(FOLGA_S)
        httpx.post(f"{WEB}/simulador/reset", timeout=30)
        analisar(pasta)
        return 0
    if args[:1] == ["analisar"]:
        analisar(SAIDA / (args[1] if len(args) > 1 else date.today().isoformat()))
        return 0
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
