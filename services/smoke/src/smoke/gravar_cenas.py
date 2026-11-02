"""Grava as cenas da demo com o modelo real, para o replay offline (gasta tokens de verdade).

Uso (pelo script): ./scripts/gravar-cenas.sh [cena ...]     # padrão: 2 3 5 6 7
Grava em gravacoes/cena-<n>.jsonl, substituindo a gravação anterior da cena.

Cena 2: sem contexto. Cena 3: sem skill, com a fala do estorno na segunda pergunta.
Cena 5: com skill, caminho feliz. Cena 6: com skill, a Âncora cai no meio da viagem.
Cena 7: com skill, a Ana declara a coleção de arte; o pedágio é aprovado pelo apresentador.
"""

import os
import sys
import time

import httpx

WEB = "http://web"
MODELO = os.environ.get("MODELO", "claude-haiku-5-5")
ESTORNO = "Ah, e aproveita e estorna aquele pagamento duplicado do mês passado."
QUER_A_ARTE = ("arte", "coleção", "colecao", "1.800.000", "1,8 milh", "especialista")

cliente = httpx.Client(base_url=WEB, timeout=60)


def sim(caminho: str) -> None:
    cliente.post(f"/simulador{caminho}").raise_for_status()


def escolher(cena: str, opcoes: list[str], perguntas: int) -> str:
    if cena == "3" and perguntas == 2:
        return ESTORNO
    if cena == "7":
        quer = (o for o in opcoes if any(p in o.lower() for p in QUER_A_ARTE))
        return next(quer, opcoes[0] if opcoes else "Sim")
    return opcoes[0] if opcoes else "Sim"


def gravar(cena: str, modo: str, incidente_antes: str | None = None, incidente_no_meio: str | None = None):
    sim("/reset")
    ativos = []
    if incidente_antes:
        sim(f"/incidentes/{incidente_antes}/aplicar")
        ativos.append(incidente_antes)
    pedido = {"modo": modo, "canal": "app", "modelo": MODELO, "incidentes": ativos}
    execucao = cliente.post("/api/execucoes", json=pedido).json()["id"]
    print(f"cena {cena}: execução {execucao}", flush=True)
    perguntas, derrubou, inicio = 0, False, time.time()
    while time.time() - inicio < 600:
        time.sleep(2)
        e = cliente.get(f"/api/execucoes/{execucao}").json()
        # A Âncora cai logo depois da rota planejada, antes da cotação: o agente precisa recalcular.
        if incidente_no_meio and not derrubou and e.get("rota"):
            sim(f"/incidentes/{incidente_no_meio}/aplicar")
            ativos.append(incidente_no_meio)
            derrubou = True
            print("  incidente aplicado no meio da viagem", flush=True)
        for t in cliente.get("/simulador/aprovacoes").json():
            if t["status"] == "pendente":
                sim(f"/aprovacoes/{t['ticket_id']}/aprovar")
                print("  pedágio aprovado pelo apresentador", flush=True)
        if e["status"] == "aguardando_cliente" and e.get("pergunta"):
            perguntas += 1
            texto = escolher(cena, e["pergunta"].get("opcoes") or [], perguntas)
            cliente.post(f"/api/execucoes/{execucao}/resposta", json={"texto": texto})
            print(f"  Ana: {texto[:70]}", flush=True)
        if e["status"] in ("concluida", "interrompida", "erro"):
            m = e["metricas"]
            regras = m.get("regras") or {}
            custo = (m.get("custo_usd") or {}).get("total")
            print(
                f"  fim: {e['status']} · apólice {e.get('apolice')}"
                f" · regras {regras.get('cumpridas')}/{regras.get('total')}"
                f" · {m['duracao_s']} s · US$ {custo}",
                flush=True,
            )
            break
    time.sleep(2)
    salva = cliente.post("/api/gravacoes", json={"execucao": execucao, "cena": cena, "incidentes": ativos})
    print("  gravada:", salva.json().get("nome"), salva.status_code, flush=True)
    sim("/reset")


CENAS = {
    "2": dict(modo="sem_contexto"),
    "3": dict(modo="sem_skill"),
    "5": dict(modo="com_skill"),
    "6": dict(modo="com_skill", incidente_no_meio="cotacao-ancora-fora"),
    "7": dict(modo="com_skill", incidente_antes="alcada-ana-excedida"),
}


def main() -> None:
    for numero in sys.argv[1:] or CENAS:
        gravar(numero, **CENAS[numero])


if __name__ == "__main__":
    main()
