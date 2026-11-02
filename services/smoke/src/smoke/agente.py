"""Dirige o agente pela API do web e acompanha os eventos ao vivo (SSE).

Uso (pelo script):
  ./scripts/agente.sh executar --modo com_skill [--canal app|agencia|central] [--provedor roteiro] [--auto]
  ./scripts/agente.sh executar --modo com_skill --modelo claude-haiku-5-5   # outro modelo permitido
  ./scripts/agente.sh responder <id> "Sim, é esse apartamento"
  ./scripts/agente.sh responder <id> --sugestao 1
  ./scripts/agente.sh estado <id>

--auto responde pela Ana com a primeira opção sugerida (ensaio sem apresentador).
"""

import json
import sys

import httpx

API = "http://web/api"


def _linha(evento: dict) -> str:
    tipo, d = evento["tipo"], evento["dados"]
    if tipo == "run.started":
        return f"▶ início · modo {d['modo']} · canal {d['canal']} · provedor {d['provedor']} ({d['modelo']})"
    if tipo == "prompt.loaded":
        if d["origem"] == "gateway":
            return f"◆ persona do canal: {d['nome']} (pelo gateway)"
        return f"◆ persona embutida · {d.get('motivo', '')}"
    if tipo == "skill.loaded":
        return f"◆ skill carregada: {d['nome']} ({len(d['tools_permitidas'])} tools permitidas)"
    if tipo == "route.planned":
        e = d["estimativa"]
        return f"◆ rota planejada: {d['nome']} · {e['tempo_texto']} · risco {e['risco']} · {d['motivo']}"
    if tipo == "step.started":
        return f"  ● parada {d.get('numero') or '-'}: {d.get('nome', d['id'])} ({d.get('bairro', '?')})"
    if tipo == "tool.called":
        marca = "✓" if d["status"] == "ok" else f"✗ {d.get('motivo') or 'erro'}"
        return f"      {d['tool']:40} {marca} {d['duracao_ms']} ms"
    if tipo == "incident.detected":
        return f"  ⚠ incidente: {d['metafora']} · {d['descricao']}"
    if tipo == "route.recalculated":
        return f"◆ rota recalculada: {d['de']} → {d['para']} · {d['motivo']} · regra: {d['regra']}"
    if tipo == "human.required":
        return f"  ✋ pedágio: especialista acionado (ticket {d['ticket_id']})"
    if tipo == "client.asked":
        opcoes = "".join(f"\n      [{i}] {o}" for i, o in enumerate(d["opcoes"], 1))
        return f"  ? pergunta: {d['pergunta']}{opcoes}"
    if tipo == "client.answered":
        return f"  ↳ resposta: {d['texto']}"
    if tipo == "agent.message":
        return f"  💬 agente: {d['texto']}"
    if tipo == "run.finished":
        m = d["metricas"]
        return (
            f"■ fim · {d['status']}"
            + (f" · apólice {d['apolice']}" if d.get("apolice") else "")
            + (f" · erro: {d['erro']}" if d.get("erro") else "")
            + f"\n  métricas: {m['chamadas_tool']} chamadas, {len(m['tools_irrelevantes'])} irrelevantes, "
            f"{m['bloqueios']} bloqueios, {m['incidentes']} incidentes, "
            f"{m['tokens']['entrada']}+{m['tokens']['saida']} tokens, "
            f"{m['duracao_s']} s"
            + (f", US$ {m['custo_usd']['total']:.4f}".replace(".", ",") if m.get("custo_usd") else "")
        )
    return f"  · {tipo}"


def acompanhar(ident: str, auto: bool) -> int:
    with httpx.stream("GET", f"{API}/execucoes/{ident}/eventos", timeout=None) as resposta:
        for linha in resposta.iter_lines():
            if not linha.startswith("data:"):
                continue
            evento = json.loads(linha[5:])
            print(_linha(evento), flush=True)
            if evento["tipo"] == "client.asked":
                opcoes = evento["dados"]["opcoes"]
                if auto and opcoes:
                    httpx.post(f"{API}/execucoes/{ident}/resposta", json={"texto": opcoes[0]}, timeout=10)
                else:
                    print(
                        f"    responda em outro terminal: ./scripts/agente.sh responder {ident} --sugestao 1",
                        flush=True,
                    )
            if evento["tipo"] == "run.finished":
                return 0 if evento["dados"]["status"] == "concluida" else 1
    return 1


def main() -> int:
    args = sys.argv[1:]
    if not args:
        print(__doc__, file=sys.stderr)
        return 2
    comando = args[0]
    if comando == "executar":
        corpo = {"modo": args[args.index("--modo") + 1] if "--modo" in args else "com_skill"}
        if "--canal" in args:
            corpo["canal"] = args[args.index("--canal") + 1]
        if "--modelo" in args:
            corpo["modelo"] = args[args.index("--modelo") + 1]
        if "--provedor" in args:
            corpo["provedor"] = args[args.index("--provedor") + 1]
        resposta = httpx.post(f"{API}/execucoes", json=corpo, timeout=10)
        if resposta.status_code != 201:
            print(resposta.text, file=sys.stderr)
            return 1
        ident = resposta.json()["id"]
        print(f"execução {ident}", flush=True)
        return acompanhar(ident, auto="--auto" in args)
    if comando == "responder" and len(args) >= 3:
        ident = args[1]
        if args[2] == "--sugestao":
            pergunta = httpx.get(f"{API}/execucoes/{ident}", timeout=10).json().get("pergunta") or {}
            texto = pergunta.get("opcoes", [""])[int(args[3]) - 1]
        else:
            texto = args[2]
        resposta = httpx.post(f"{API}/execucoes/{ident}/resposta", json={"texto": texto}, timeout=10)
        print(resposta.json())
        return 0 if resposta.status_code == 200 else 1
    if comando == "estado" and len(args) >= 2:
        print(
            json.dumps(
                httpx.get(f"{API}/execucoes/{args[1]}", timeout=10).json(), ensure_ascii=False, indent=2
            )
        )
        return 0
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
