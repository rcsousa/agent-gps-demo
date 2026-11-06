"""Diagramas dos bastidores, gerados do próprio repositório no build do docs (Graphviz → SVG).

A doc não desatualiza: se um serviço entra no compose, uma relação muda na ontologia ou a
ordem de uma skill muda no workflow.yaml, o diagrama muda junto no próximo build.

Uso: python diagramas.py <raiz-do-repositorio> <pasta-de-saida>
"""

import subprocess
import sys
from pathlib import Path

import yaml

FONTE = "IBM Plex Sans"
LARANJA = "#f26522"
MARINHO = "#1d3557"
CINZA = "#8d8d8d"
TEXTO = "#161616"
FUNDO_GRUPO = "#f4f4f4"


def _id(texto: str) -> str:
    return '"' + texto.replace('"', '\\"') + '"'


def _cabecalho(nome: str, direcao: str = "LR") -> list[str]:
    return [
        f"digraph {_id(nome)} {{",
        f'  graph [rankdir={direcao}, bgcolor="transparent", fontname="{FONTE}", fontsize=12,'
        ' nodesep=0.35, ranksep=0.55, pad=0.2];',
        f'  node [fontname="{FONTE}", fontsize=11, shape=box, style="rounded,filled", fillcolor="white",'
        f' color="{CINZA}", fontcolor="{TEXTO}", penwidth=1];',
        f'  edge [fontname="{FONTE}", fontsize=9, color="{CINZA}", fontcolor="#525252", arrowsize=0.7];',
    ]


def _rodape(fontes: list[str]) -> list[str]:
    texto = "gerado de " + ", ".join(fontes)
    return [f'  label={_id(texto)}; labelloc=b; labeljust=r; fontsize=9; fontcolor="{CINZA}";', "}"]


# --- Arquitetura -----------------------------------------------------------------------

GRUPOS = [
    ("front", "Front (o que a plateia vê)", lambda n: n in ("web", "docs")),
    ("agente", "Agente", lambda n: n == "agent"),
    ("gateway", "Ponto único de acesso MCP", lambda n: n == "mcp-gateway"),
    ("mcp", "Servidores MCP (as tools do banco)", lambda n: n.endswith("-mcp")),
    ("mundo", "O mundo simulado", lambda n: n == "simulator"),
    ("dados", "Dados e eventos", lambda n: n in ("bus", "graph", "seed")),
]
RELACOES_CONHECIDAS = {
    ("web", "agent"): "/api",
    ("web", "simulator"): "/simulador",
    ("web", "docs"): "/bastidores",
    ("agent", "mcp-gateway"): "MCP",
    ("agent", "bus"): "eventos",
    ("contexto-mcp", "graph"): "Cypher",
    ("seed", "graph"): "carga",
}


def arquitetura(raiz: Path) -> str:
    compose = yaml.safe_load((raiz / "docker-compose.yml").read_text(encoding="utf-8"))
    upstreams = yaml.safe_load(
        (raiz / "services/mcp-gateway/config/upstreams.yaml").read_text(encoding="utf-8")
    )
    servicos = {n: s for n, s in compose["services"].items() if not s.get("profiles")}
    mcp = {u["nome"] for u in upstreams["servidores"]}

    linhas = _cabecalho("arquitetura")
    for chave, rotulo, pertence in GRUPOS:
        membros = [n for n in servicos if pertence(n)]
        if not membros:
            continue
        linhas.append(f"  subgraph cluster_{chave} {{")
        linhas.append(
            f'    label={_id(rotulo)}; style="rounded,filled"; fillcolor="{FUNDO_GRUPO}"; color="#e0e0e0";'
        )
        for n in membros:
            cor = LARANJA if n == "mcp-gateway" else MARINHO if n == "agent" else CINZA
            largura = 2 if n in ("mcp-gateway", "agent") else 1
            linhas.append(f'    {_id(n)} [color="{cor}", penwidth={largura}];')
        linhas.append("  }")

    arestas: set[tuple[str, str]] = set()
    for nome, servico in servicos.items():
        dependencias = servico.get("depends_on") or {}
        for dep in dependencias if isinstance(dependencias, (dict, list)) else []:
            if dep in servicos and not (nome == "mcp-gateway" and dep in mcp):
                arestas.add((nome, dep))
    for nome in sorted(mcp):
        if nome in servicos:
            arestas.add(("mcp-gateway", nome))
    for de, para in sorted(arestas):
        atributos = []
        rotulo = RELACOES_CONHECIDAS.get((de, para))
        if de == "mcp-gateway" and para in mcp:
            rotulo = "MCP"
            atributos.append(f'color="{LARANJA}"')
        elif para == "bus" and de != "agent":
            rotulo = rotulo or "eventos"
            atributos.append("style=dashed")
        if rotulo:
            atributos.append(f"label={_id(rotulo)}")
        linhas.append(f"  {_id(de)} -> {_id(para)} [{', '.join(atributos)}];")
    return "\n".join(linhas + _rodape(["docker-compose.yml", "mcp-gateway/config/upstreams.yaml"]))


# --- Ontologia -----------------------------------------------------------------------

def ontologia(raiz: Path) -> str:
    base = raiz / "services/contexto-mcp/ontologia"
    esquema = yaml.safe_load((base / "esquema.yaml").read_text(encoding="utf-8"))
    bairros = yaml.safe_load((base / "bairros.yaml").read_text(encoding="utf-8"))["bairros"]
    tipos = esquema["tipos"]

    # Visão por bairro: cada bairro lista seus tipos; as setas juntam as relações entre bairros.
    # (As paradas ligam-se a todos os bairros e aparecem no diagrama de rotas.)
    linhas = _cabecalho("ontologia")
    linhas.append("  graph [nodesep=0.6, ranksep=1.1];")
    for b in bairros:
        membros = [tipos[t]["exibicao"] for t, d in tipos.items() if d["bairro"] == b["id"]]
        itens = "".join(f'<TR><TD ALIGN="LEFT">{m}</TD></TR>' for m in membros)
        rotulo = (
            f'<<TABLE BORDER="0" CELLSPACING="0" CELLPADDING="3">'
            f'<TR><TD><B><FONT COLOR="{b["cor"]}" POINT-SIZE="13">{b["nome"]}</FONT></B></TD></TR>{itens}</TABLE>>'
        )
        linhas.append(f'  {_id(b["id"])} [label={rotulo}, color="{b["cor"]}", penwidth=2, fillcolor="white"];')

    entre: dict[tuple[str, str], set[str]] = {}
    for nome, rel in (esquema.get("relacoes") or {}).items():
        for o in rel.get("origem", []):
            for d in rel.get("destino", []):
                if o not in tipos or d not in tipos:
                    continue
                bo, bd = tipos[o]["bairro"], tipos[d]["bairro"]
                if "variavel" in (bo, bd) or bo == bd:
                    continue
                entre.setdefault((bo, bd), set()).add(nome.replace("_", " ").lower())
    for (bo, bd), nomes in sorted(entre.items()):
        rotulo = ", ".join(sorted(nomes))
        linhas.append(f"  {_id(bo)} -> {_id(bd)} [label={_id(rotulo)}, penwidth={min(1 + len(nomes) * 0.4, 3)}];")
    return "\n".join(linhas + _rodape(["contexto-mcp/ontologia/esquema.yaml", "bairros.yaml"]))


# --- A ordem de uma skill -------------------------------------------------------------

def _condicao(item) -> tuple[str, str]:
    """(tool, rótulo) de um pré-requisito do workflow.yaml."""
    if isinstance(item, str):
        return item, ""
    tool, condicao = next(iter(item.items()))
    if not isinstance(condicao, dict):
        return tool, ""
    return tool, ", ".join(f"{k}: {v}" for k, v in condicao.items())


def skill(pasta: Path) -> str | None:
    arquivo = pasta / "workflow.yaml"
    if not arquivo.exists():
        return None
    workflow = yaml.safe_load(arquivo.read_text(encoding="utf-8")) or {}
    linhas = _cabecalho(f"skill-{pasta.name}")
    nos: set[str] = set()
    arestas: list[str] = []
    for tool, requisitos in (workflow.get("pre-requisitos") or {}).items():
        nos.add(tool)
        for item in requisitos:
            if isinstance(item, dict) and "qualquer" in item:
                ou = f"qualquer::{tool}"
                linhas.append(f'  {_id(ou)} [label="um destes", shape=diamond, fontsize=9, fillcolor="{FUNDO_GRUPO}"];')
                arestas.append(f"  {_id(ou)} -> {_id(tool)};")
                for alternativa in item["qualquer"]:
                    anterior, rotulo = _condicao(alternativa)
                    nos.add(anterior)
                    arestas.append(f"  {_id(anterior)} -> {_id(ou)} [label={_id(rotulo)}, style=dashed];")
                continue
            anterior, rotulo = _condicao(item)
            nos.add(anterior)
            arestas.append(f"  {_id(anterior)} -> {_id(tool)} [label={_id(rotulo)}];")
    for tool, impedidores in (workflow.get("impedimentos") or {}).items():
        nos.add(tool)
        for impedidor in impedidores:
            nos.add(impedidor)
            arestas.append(
                f'  {_id(impedidor)} -> {_id(tool)} [label="impede", color="#da1e28", fontcolor="#da1e28",'
                " style=dashed, arrowhead=tee];"
            )
    for no in sorted(nos):
        dominio = no.split(".")[0]
        destaque = f', color="{LARANJA}", penwidth=2' if dominio == "seguradoras" else ""
        linhas.append(f"  {_id(no)} [fontname=\"IBM Plex Mono\", fontsize=10{destaque}];")
    linhas.extend(arestas)
    return "\n".join(linhas + _rodape([f"skills-mcp/skills/{pasta.name}/workflow.yaml"]))


# --- As rotas ---------------------------------------------------------------------------

CORES_DAS_ROTAS = {"rota-rapida": MARINHO, "rota-economica": LARANJA, "rota-assistida": "#8a3ffc"}


def rotas(raiz: Path) -> str:
    jornada = yaml.safe_load(
        (raiz / "services/contexto-mcp/ontologia/instancias/jornada.yaml").read_text(encoding="utf-8")
    )
    entidades = {e["id"]: e for e in jornada["entidades"]}
    passagens: dict[str, list[tuple[int, str]]] = {}
    for r in jornada["relacoes"]:
        if isinstance(r, dict) and r.get("tipo") == "PASSA_POR":
            passagens.setdefault(r["de"], []).append((r["atributos"]["ordem"], r["para"]))

    linhas = _cabecalho("rotas")
    for ident, e in entidades.items():
        if e["tipo"] != "Parada":
            continue
        numero = e.get("atributos", {}).get("numero")
        rotulo = f"{numero} · {e['nome']}" if numero else e["nome"]
        extra = f', color="{LARANJA}", penwidth=2' if numero else ', style="rounded,dashed"'
        linhas.append(f"  {_id(ident)} [label={_id(rotulo)}{extra}];")
    for rota, paradas in sorted(passagens.items()):
        cor = CORES_DAS_ROTAS.get(rota, CINZA)
        nome = entidades[rota]["nome"] if rota in entidades else rota
        sequencia = [p for _, p in sorted(paradas)]
        for i, (a, b) in enumerate(zip(sequencia, sequencia[1:], strict=False)):
            rotulo = f', label={_id(nome)}, fontcolor="{cor}"' if i == 0 else ""
            linhas.append(f'  {_id(a)} -> {_id(b)} [color="{cor}", penwidth=1.6{rotulo}];')
    return "\n".join(linhas + _rodape(["contexto-mcp/ontologia/instancias/jornada.yaml"]))


# --- Saída ---------------------------------------------------------------------------------

def gerar(raiz: Path, saida: Path, fragmentos: Path | None = None) -> list[Path]:
    # A referência técnica importa os helpers daqui: o import fica dentro da função.
    import diagramas_referencia
    import referencia

    saida.mkdir(parents=True, exist_ok=True)
    fontes = {"arquitetura": arquitetura(raiz), "ontologia": ontologia(raiz), "rotas": rotas(raiz)}
    for pasta in sorted((raiz / "services/skills-mcp/skills").iterdir()):
        if pasta.is_dir() and (dot := skill(pasta)):
            fontes[f"skill-{pasta.name}"] = dot
    fontes.update(diagramas_referencia.dots(raiz))
    gerados = []
    for nome, dot in fontes.items():
        (saida / f"{nome}.dot").write_text(dot, encoding="utf-8")
        svg = saida / f"{nome}.svg"
        subprocess.run(["dot", "-Tsvg", "-o", str(svg)], input=dot.encode("utf-8"), check=True)
        gerados.append(svg)
    for nome, svg in diagramas_referencia.svgs(raiz).items():
        caminho = saida / f"{nome}.svg"
        caminho.write_text(svg, encoding="utf-8")
        gerados.append(caminho)
    # Os números e as tabelas da referência, inseridos nas páginas com --8<--.
    if fragmentos is not None:
        gerados += referencia.gerar(raiz, fragmentos)
    return gerados


if __name__ == "__main__":
    extra = Path(sys.argv[3]) if len(sys.argv) > 3 else None
    for caminho in gerar(Path(sys.argv[1]), Path(sys.argv[2]), extra):
        print(caminho)
