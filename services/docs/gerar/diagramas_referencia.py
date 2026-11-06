"""Diagramas da referência técnica, gerados do repositório no build do docs.

- o grafo: o T-Box (classes por bairro), o A-Box da Ana e as camadas de profundidade;
- a arquitetura em níveis (C4): contexto, containers e componentes;
- o padrão do gateway MCP;
- diagramas de sequência desenhados de execuções reais gravadas (gravacoes/*.jsonl).

Os de Graphviz devolvem o texto .dot; os de sequência devolvem o SVG pronto (um desenhista
simples, aqui mesmo: sem Mermaid nem navegador no build, e o site continua sem rede).
"""

import ast
import json
import re
from collections import Counter
from html import escape
from pathlib import Path

import yaml

import referencia as ref
from diagramas import CINZA, FONTE, FUNDO_GRUPO, LARANJA, MARINHO, TEXTO, _cabecalho, _id, _rodape

MONO = "IBM Plex Mono"
BASE_DO_NO = ["id", "tipo", "tipo_exibicao", "nome", "descricao", "bairro", "x", "y", "prov_fonte", "prov_data", "prov_responsavel", "prov_confianca"]
ESTADO_DO_NO = ["status", "latencia_ms", "custo_estimado", "vigencia_inicio", "vigencia_fim"]


def _h(texto) -> str:
    """Texto seguro dentro de um rótulo HTML do Graphviz."""
    return escape(str(texto), quote=True)


# --- O grafo: T-Box em diagrama de classes, por bairro ---------------------------------------

def _classe(o, tipo: str, cor: str, contagem: int, props: list[str], com_estado: bool) -> str:
    exibicao = o.tipos[tipo].exibicao
    linhas = [
        f'<TR><TD BGCOLOR="{cor}33" ALIGN="LEFT"><B>{_h(exibicao)}</B></TD></TR>',
        f'<TR><TD ALIGN="LEFT"><FONT FACE="{MONO}" POINT-SIZE="9" COLOR="#525252">:Entidade:{_h(tipo)} · {contagem} inst.</FONT></TD></TR>',
    ]
    if props or com_estado:
        linhas.append("<HR/>")
    for p in props:
        linhas.append(f'<TR><TD ALIGN="LEFT"><FONT FACE="{MONO}" POINT-SIZE="9">attr_{_h(p)}</FONT></TD></TR>')
    if com_estado:
        linhas.append(f'<TR><TD ALIGN="LEFT"><FONT FACE="{MONO}" POINT-SIZE="9" COLOR="{LARANJA}">+ estado vivo</FONT></TD></TR>')
    return (
        f'<<TABLE BORDER="1" CELLBORDER="0" CELLSPACING="0" CELLPADDING="3" COLOR="{cor}" BGCOLOR="white">'
        + "".join(linhas)
        + "</TABLE>>"
    )


# A jornada (Jornada → Rota → Parada) toca quase todos os tipos: num diagrama só, as setas dela
# cruzariam o domínio inteiro. Por isso o T-Box sai em dois: o domínio do banco e a jornada.
TIPOS_DA_JORNADA = ("Jornada", "Rota", "Parada")


def _aresta_de_classe(rel: str, origem: str, destino: str, mult_origem: str, mult_destino: str) -> str:
    return (
        f"  {_id(origem)} -> {_id(destino)} [label={_id(rel)}, taillabel={_id(mult_origem)},"
        f' headlabel={_id(mult_destino)}, fontname="{MONO}", labelfontsize=8, labelfontcolor="{LARANJA}"];'
    )


def tbox(raiz: Path) -> str:
    """O domínio do banco: todos os tipos, menos os da jornada, por bairro."""
    o = ref.carregar(raiz)
    contagem = ref.instancias_por_tipo(o)
    props = ref.propriedades_observadas(o)
    estado = ref.tem_estado(o)
    cores = {b.id: b.cor for b in o.bairros}
    linhas = _cabecalho("tbox", "LR")
    linhas.append("  graph [nodesep=0.25, ranksep=1.4, newrank=true];")
    linhas.append('  node [shape=plain, style=""];')
    grupos = [(b.id, b.nome, b.cor) for b in o.bairros] + [(ref.BAIRRO_VARIAVEL, "Bairro variável (cada instância diz o seu)", CINZA)]
    for ident, nome, cor in grupos:
        membros = [t for t, d in o.tipos.items() if d.bairro == ident and t not in TIPOS_DA_JORNADA]
        if not membros:
            continue
        linhas.append(f"  subgraph cluster_{ident} {{")
        linhas.append(
            f'    label=<<B><FONT COLOR="{cor}" POINT-SIZE="14">{_h(nome)}</FONT></B>>; style="rounded,filled";'
            f' fillcolor="{cor}10"; color="{cor}";'
        )
        for t in sorted(membros):
            linhas.append(f"    {_id(t)} [label={_classe(o, t, cores.get(ident, cor), contagem[t], props[t], t in estado)}];")
        linhas.append("  }")
    # As propriedades que toda entidade tem, uma vez só.
    base = "".join(f'<TR><TD ALIGN="LEFT"><FONT FACE="{MONO}" POINT-SIZE="9">{p}</FONT></TD></TR>' for p in BASE_DO_NO)
    viva = "".join(f'<TR><TD ALIGN="LEFT"><FONT FACE="{MONO}" POINT-SIZE="9" COLOR="{LARANJA}">{p}</FONT></TD></TR>' for p in ESTADO_DO_NO)
    linhas.append(
        f'  "toda-entidade" [label=<<TABLE BORDER="1" CELLBORDER="0" CELLSPACING="0" CELLPADDING="3" COLOR="{MARINHO}" BGCOLOR="white">'
        f'<TR><TD BGCOLOR="{MARINHO}22" ALIGN="LEFT"><B>Toda entidade (:Entidade)</B></TD></TR>{base}<HR/>'
        f'<TR><TD ALIGN="LEFT"><FONT POINT-SIZE="9">estado vivo, quando há:</FONT></TD></TR>{viva}</TABLE>>];'
    )
    for (rel, origem, destino), (mult_origem, mult_destino, _) in ref.cardinalidades(o).items():
        if origem not in TIPOS_DA_JORNADA and destino not in TIPOS_DA_JORNADA:
            linhas.append(_aresta_de_classe(rel, origem, destino, mult_origem, mult_destino))
    return "\n".join(linhas + _rodape(["contexto-mcp/ontologia (esquema e instâncias), pelo carregador do seed"]))


def tbox_jornada(raiz: Path) -> str:
    """A jornada no grafo: Jornada → Rota → Parada e os tipos que cada parada toca."""
    o = ref.carregar(raiz)
    contagem = ref.instancias_por_tipo(o)
    props = ref.propriedades_observadas(o)
    estado = ref.tem_estado(o)
    cores = {b.id: b.cor for b in o.bairros}
    card = {k: v for k, v in ref.cardinalidades(o).items() if k[1] in TIPOS_DA_JORNADA or k[2] in TIPOS_DA_JORNADA}
    tocados = sorted({t for k in card for t in (k[1], k[2])} - set(TIPOS_DA_JORNADA))
    linhas = _cabecalho("tbox-jornada", "LR")
    linhas.append("  graph [nodesep=0.2, ranksep=1.6];")
    linhas.append('  node [shape=plain, style=""];')
    for t in TIPOS_DA_JORNADA:
        cor = cores.get(o.tipos[t].bairro, MARINHO)
        linhas.append(f"  {_id(t)} [label={_classe(o, t, cor, contagem[t], props[t], t in estado)}];")
    for t in tocados:
        cor = cores.get(o.tipos[t].bairro, CINZA)
        linhas.append(
            f'  {_id(t)} [label=<<TABLE BORDER="1" CELLBORDER="0" CELLPADDING="4" COLOR="{cor}" BGCOLOR="{cor}22">'
            f"<TR><TD>{_h(o.tipos[t].exibicao)}</TD></TR></TABLE>>];"
        )
    for (rel, origem, destino), (mult_origem, mult_destino, _) in card.items():
        linhas.append(_aresta_de_classe(rel, origem, destino, mult_origem, mult_destino))
    return "\n".join(linhas + _rodape(["contexto-mcp/ontologia (jornada.yaml e esquema), pelo carregador do seed"]))


# --- O grafo: A-Box da Ana ---------------------------------------------------------------------

def abox_ana(raiz: Path, saltos: int = 2) -> str:
    o = ref.carregar(raiz)
    dentro, relacoes = ref.vizinhanca(o, "cliente-ana", saltos)
    cores = {b.id: b.cor for b in o.bairros}
    linhas = _cabecalho("abox-ana", "LR")
    linhas.append("  graph [nodesep=0.3, ranksep=0.9];")
    for ident in sorted(dentro):
        e = o.entidades[ident]
        bairro = e.bairro or o.tipos[e.tipo].bairro
        cor = LARANJA if ident == "cliente-ana" else cores.get(bairro, CINZA)
        confianca = e.proveniencia.confianca
        aviso = f'<BR/><FONT POINT-SIZE="8" COLOR="{LARANJA}">confiança {confianca}</FONT>' if confianca != "alta" else ""
        rotulo = (
            f'<<B>{_h(e.nome)}</B><BR/><FONT FACE="{MONO}" POINT-SIZE="8" COLOR="#525252">'
            f"{_h(e.tipo)} · {_h(ident)}</FONT>"
            f'<BR/><FONT POINT-SIZE="8" COLOR="#525252">{_h(e.proveniencia.fonte)}</FONT>{aviso}>'
        )
        largura = 3 if ident == "cliente-ana" else 1.5
        linhas.append(f'  {_id(ident)} [label={rotulo}, color="{cor}", penwidth={largura}];')
    for r in relacoes:
        linhas.append(f'  {_id(r.de)} -> {_id(r.para)} [label={_id(r.tipo)}, fontname="{MONO}"];')
    return "\n".join(linhas + _rodape([f"contexto-mcp/ontologia/instancias: a Ana e tudo a até {saltos} saltos"]))


# --- O grafo: as camadas de profundidade -------------------------------------------------------

def camadas(raiz: Path) -> str:
    o = ref.carregar(raiz)
    c = ref.camadas(o, raiz)
    confianca = ", ".join(f"{n} {k}" for k, n in c["confianca"].items())
    blocos = [
        ("esquema", "Esquema (T-Box)", f"{c['tipos']} tipos · {c['tipos_relacao']} tipos de relação · {c['bairros']} bairros", "esquema.yaml, bairros.yaml"),
        ("instancias", "Instâncias (A-Box)", f"{c['entidades']} entidades · {c['relacoes']} relações", "instancias/*.yaml → seed → Neo4j"),
        ("estado", "Estado vivo (o trânsito)", f"{c['com_estado']} entidades com estado · {c['incidentes']} incidentes possíveis", "simulator → contexto-mcp (SET n += …)"),
        ("proveniencia", "Proveniência", f"{c['fontes']} fontes · confiança: {confianca}", "prov_* em cada nó e em cada relação"),
    ]
    # Empilhadas, de cima para baixo, como as camadas são de fato (e cabem na largura do texto).
    linhas = _cabecalho("camadas", "TB")
    for chave, titulo, numeros, fonte in blocos:
        rotulo = (
            f'<<B>{_h(titulo)}</B><BR/><FONT POINT-SIZE="10">{_h(numeros)}</FONT>'
            f'<BR/><FONT FACE="{MONO}" POINT-SIZE="8" COLOR="#525252">{_h(fonte)}</FONT>>'
        )
        linhas.append(f'  {_id(chave)} [label={rotulo}, color="{MARINHO}", penwidth=1.5, margin="0.2,0.12"];')
    linhas.append('  "esquema" -> "instancias" [label="valida"];')
    linhas.append('  "instancias" -> "estado" [label="muda em tempo real"];')
    linhas.append('  "estado" -> "proveniencia" [label="cada dado diz de onde veio", dir=back, style=dashed];')
    return "\n".join(linhas + _rodape(["ontologia, simulator/incidentes.yaml"]))


# --- Arquitetura em níveis (C4) --------------------------------------------------------------

def c4_contexto(raiz: Path) -> str:
    linhas = _cabecalho("c4-contexto", "LR")
    linhas.append(f'  "pessoa" [label=<<B>Apresentador e plateia</B><BR/><FONT POINT-SIZE="9">navegador, com login</FONT>>, shape=box, color="{MARINHO}", penwidth=2];')
    linhas.append(f'  "demo" [label=<<B>Demo GPS de Contexto</B><BR/><FONT POINT-SIZE="9">docker compose · um único endereço (web)</FONT>>, color="{LARANJA}", penwidth=2.5, margin="0.3,0.2"];')
    linhas.append('  "llm" [label=<<B>Provedor de LLM</B><BR/><FONT POINT-SIZE="9">Microsoft Foundry · API da Anthropic · Azure OpenAI</FONT>>, style="rounded,dashed,filled"];')
    linhas.append('  "pessoa" -> "demo" [label="HTTP: abertura, mapa, Raio-X, bastidores"];')
    linhas.append('  "demo" -> "llm" [label="HTTPS: só o agent (LLM_PROVIDER)"];')
    return "\n".join(linhas + _rodape(["docker-compose.yml"]))


def _rotas_do_nginx(raiz: Path) -> list[tuple[str, str, bool]]:
    """(caminho, serviço, público?) de cada location com proxy_pass no nginx do web."""
    texto = (raiz / "services/web/nginx.conf").read_text(encoding="utf-8")
    rotas = []
    for bloco in re.finditer(r"location\s+(=\s*)?(\S+)\s*\{(.*?)\}", texto, re.S):
        caminho, corpo = bloco.group(2), bloco.group(3)
        alvo = re.search(r"proxy_pass\s+http://([\w-]+)", corpo)
        if alvo and not caminho.startswith("/_"):
            rotas.append((caminho, alvo.group(1), "auth_request off" in corpo))
    return rotas


def _tecnologia(nome: str, servico: dict) -> str:
    imagem = servico.get("image", "")
    construcao = servico.get("build") or {}
    arquivo = construcao.get("dockerfile", "") if isinstance(construcao, dict) else ""
    if "neo4j" in imagem:
        return "Neo4j 5 (grafo)"
    if "redis" in imagem:
        return "Redis 7 (Streams)"
    if nome == "web":
        return "nginx + React/TypeScript"
    if nome == "docs":
        return "nginx + MkDocs"
    if "python-service" in arquivo or "bussola-contexto" in imagem:
        return "Python · FastAPI" + (" · MCP" if nome.endswith("-mcp") or nome == "mcp-gateway" else "")
    return imagem or "container"


def c4_containers(raiz: Path) -> str:
    compose = yaml.safe_load((raiz / "docker-compose.yml").read_text(encoding="utf-8"))
    servicos = {n: s for n, s in compose["services"].items() if not s.get("profiles")}
    rotas = _rotas_do_nginx(raiz)
    linhas = _cabecalho("c4-containers", "LR")
    linhas.append("  graph [ranksep=1.0, nodesep=0.3];")
    linhas.append(f'  "navegador" [label=<<B>Navegador</B>>, color="{MARINHO}", penwidth=2];')
    for nome, s in servicos.items():
        portas = ", ".join(str(p).split(":")[-1] if isinstance(p, str) else str(p) for p in s.get("ports", []))
        publico = " · porta publicada" if s.get("ports") else ""
        rotulo = (
            f'<<B>{_h(nome)}</B><BR/><FONT POINT-SIZE="9">{_h(_tecnologia(nome, s))}</FONT>'
            f'<BR/><FONT FACE="{MONO}" POINT-SIZE="8" COLOR="#525252">{_h(portas or "rede interna")}{_h(publico)}</FONT>>'
        )
        cor = LARANJA if nome == "mcp-gateway" else MARINHO if nome in ("agent", "web") else CINZA
        linhas.append(f'  {_id(nome)} [label={rotulo}, color="{cor}", penwidth={2 if cor != CINZA else 1}];')
    linhas.append('  "navegador" -> "web" [label="HTTP (sessão em cookie)"];')
    for caminho, alvo, publico in rotas:
        if alvo in servicos:
            estilo = ', color="#24a148", fontcolor="#24a148"' if publico else ""
            rotulo = f"{caminho} ({'público' if publico else 'com sessão'})"
            linhas.append(f"  \"web\" -> {_id(alvo)} [label={_id(rotulo)}{estilo}];")
    arestas = set()
    for nome, s in servicos.items():
        dependencias = s.get("depends_on") or {}
        for dep in dependencias if isinstance(dependencias, (dict, list)) else []:
            if dep in servicos and nome != "web":
                arestas.add((nome, dep))
    for de, para in sorted(arestas):
        linhas.append(f"  {_id(de)} -> {_id(para)} [style=dashed, color=\"{CINZA}\"];")
    return "\n".join(linhas + _rodape(["docker-compose.yml", "services/web/nginx.conf"]))


def _modulos(pasta: Path, pacote: str) -> dict[str, tuple[str, set[str]]]:
    """módulo -> (primeira linha da docstring, módulos do mesmo pacote que ele importa)."""
    modulos = {}
    for arquivo in sorted(pasta.glob("*.py")):
        if arquivo.stem in ("__init__", "__main__"):
            continue
        arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
        doc = (ast.get_docstring(arvore) or "").strip().splitlines()
        importa = set()
        for no in ast.walk(arvore):
            if isinstance(no, ast.ImportFrom) and no.module:
                if no.module.startswith(f"{pacote}."):
                    importa.add(no.module.split(".")[1])
                elif no.module == pacote:
                    importa |= {a.name for a in no.names}
        modulos[arquivo.stem] = (doc[0] if doc else "", importa)
    return modulos


COMPONENTES = [
    ("agent", "agent", "services/agent/src/agent", MARINHO),
    ("mcp-gateway", "mcp_gateway", "services/mcp-gateway/src/mcp_gateway", LARANJA),
    ("contexto-mcp", "contexto_mcp", "services/contexto-mcp/src/contexto_mcp", "#1192e8"),
]


def c4_componentes(raiz: Path) -> str:
    linhas = _cabecalho("c4-componentes", "LR")
    linhas.append("  graph [ranksep=0.8, nodesep=0.25];")
    for servico, pacote, pasta, cor in COMPONENTES:
        modulos = _modulos(raiz / pasta, pacote)
        linhas.append(f"  subgraph cluster_{pacote} {{")
        linhas.append(f'    label=<<B><FONT COLOR="{cor}" POINT-SIZE="13">{_h(servico)}</FONT></B>>; style="rounded,filled"; fillcolor="{FUNDO_GRUPO}"; color="{cor}";')
        for nome, (doc, _) in modulos.items():
            resumo = doc if len(doc) <= 70 else doc[:67].rstrip() + "…"
            descricao = f'<BR/><FONT POINT-SIZE="8" COLOR="#525252">{_h(resumo)}</FONT>' if resumo else ""
            rotulo = f'<<FONT FACE="{MONO}"><B>{_h(nome)}.py</B></FONT>{descricao}>'
            linhas.append(f'    {_id(pacote + "." + nome)} [label={rotulo}, color="{cor}"];')
        linhas.append("  }")
        for nome, (_, importa) in modulos.items():
            for alvo in sorted(importa & set(modulos)):
                linhas.append(f"  {_id(pacote + '.' + nome)} -> {_id(pacote + '.' + alvo)} [color=\"{CINZA}\", arrowsize=0.5];")
    linhas.append(f'  "agent.ferramentas" -> "mcp_gateway.servidor_mcp" [label="MCP (Streamable HTTP)", color="{LARANJA}", penwidth=1.6, constraint=false];')
    linhas.append(f'  "mcp_gateway.upstreams" -> "contexto_mcp.servidor" [label="MCP", color="{LARANJA}", penwidth=1.6, constraint=false];')
    return "\n".join(linhas + _rodape([p for _, _, p, _ in COMPONENTES] + ["(módulos e imports lidos do código)"]))


# --- O padrão do gateway ------------------------------------------------------------------------

PASSOS_DA_GOVERNANCA = [
    "autentica o agente (GATEWAY_TOKEN)",
    "lista: tools de todos os upstreams, com nome qualificado (servidor.tool)",
    "skill ativa (_meta bussola/skill): só as allowed-tools",
    "ordem: os pré-requisitos do workflow.yaml (senão, contramão)",
    "encaminha ao servidor dono da tool",
    "carimba a proveniência no resultado",
    "publica tool.called no barramento",
]


def gateway(raiz: Path) -> str:
    upstreams = yaml.safe_load((raiz / "services/mcp-gateway/config/upstreams.yaml").read_text(encoding="utf-8"))["servidores"]
    cat = ref.catalogo(raiz)
    tools = Counter(t["nome"].split(".")[0] for t in cat["tools"])
    prompts = Counter(p["nome"].split(".")[0] for p in cat["prompts"])
    linhas = _cabecalho("gateway", "LR")
    linhas.append("  graph [ranksep=1.1];")
    linhas.append(f'  "agent" [label=<<B>agent</B><BR/><FONT POINT-SIZE="9">host MCP · conhece um endereço só</FONT>>, color="{MARINHO}", penwidth=2];')
    itens = "".join(f'<TR><TD ALIGN="LEFT">{i}. {_h(p)}</TD></TR>' for i, p in enumerate(PASSOS_DA_GOVERNANCA, 1))
    linhas.append(
        f'  "mcp-gateway" [label=<<TABLE BORDER="0" CELLSPACING="0" CELLPADDING="3"><TR><TD><B><FONT POINT-SIZE="13">mcp-gateway</FONT></B></TD></TR>'
        f'<TR><TD><FONT POINT-SIZE="9">um servidor MCP para o agente; cliente MCP de cada upstream</FONT></TD></TR>{itens}</TABLE>>,'
        f' color="{LARANJA}", penwidth=2.5];'
    )
    linhas.append('  "agent" -> "mcp-gateway" [label="initialize · tools/list · tools/call\\nprompts/get · skills/list · resources/read"];')
    linhas.append("  subgraph cluster_upstreams {")
    linhas.append(f'    label="Servidores MCP (upstreams.yaml)"; style="rounded,filled"; fillcolor="{FUNDO_GRUPO}"; color="#e0e0e0";')
    for u in upstreams:
        serve = []
        if tools[u["prefixo"]]:
            serve.append(f"{tools[u['prefixo']]} tools")
        if prompts[u["prefixo"]]:
            serve.append(f"{prompts[u['prefixo']]} prompts")
        if u["nome"] == "skills-mcp":
            serve.append(f"{len(cat['skills'])} skills (SEP-2640)")
        rotulo = f'<<B>{_h(u["nome"])}</B><BR/><FONT FACE="{MONO}" POINT-SIZE="9">{_h(u["prefixo"])}.*</FONT><BR/><FONT POINT-SIZE="9">{_h(", ".join(serve) or "—")}</FONT>>'
        linhas.append(f"    {_id(u['nome'])} [label={rotulo}];")
        linhas.append(f'  "mcp-gateway" -> {_id(u["nome"])} [color="{LARANJA}"];')
    linhas.append("  }")
    linhas.append('  "bus" [label=<<B>bus</B><BR/><FONT POINT-SIZE="9">Redis Streams · bussola:eventos</FONT>>];')
    linhas.append('  "mcp-gateway" -> "bus" [label="tool.called", style=dashed];')
    return "\n".join(linhas + _rodape(["mcp-gateway/config/upstreams.yaml", "catálogo do gateway (smoke/referencia)"]))


# --- Sequências desenhadas de execuções gravadas ------------------------------------------------

LARGURA_COLUNA = 168
ALTURA_LINHA = 24
TOPO = 70


def _eventos(raiz: Path, gravacao: str) -> list[dict]:
    linhas = (raiz / "gravacoes" / f"{gravacao}.jsonl").read_text(encoding="utf-8").splitlines()
    return [e for e in (json.loads(linha) for linha in linhas if linha.strip()) if "tipo" in e]


def _curto(texto, limite=48) -> str:
    texto = " ".join(str(texto).split())
    return texto if len(texto) <= limite else texto[: limite - 1] + "…"


def _passos(eventos: list[dict]) -> list[tuple]:
    """Cada evento vira mensagens (de, para, rótulo, tracejada) ou notas (texto, cor)."""
    passos: list[tuple] = []
    for e in eventos:
        d, tipo = e["dados"], e["tipo"]
        if tipo == "run.started":
            passos.append(("msg", "navegador", "agent", f"POST /api/execucoes · {d.get('modo')} · {d.get('modelo')}", False))
        elif tipo == "tools.listed":
            passos.append(("msg", "agent", "mcp-gateway", "tools/list", False))
            passos.append(("msg", "mcp-gateway", "agent", f"{d.get('quantidade')} tools qualificadas", True))
        elif tipo == "skills.listed":
            passos.append(("msg", "agent", "mcp-gateway", "skills/list", False))
            passos.append(("msg", "mcp-gateway", "skills-mcp", "skills/list", False))
        elif tipo == "prompt.read":
            passos.append(("msg", "agent", "mcp-gateway", f"prompts/get {d.get('prompt')}", False))
            passos.append(("msg", "mcp-gateway", d.get("servidor", "canais-mcp"), f"prompts/get · {d.get('duracao_ms')} ms", False))
        elif tipo == "model.step":
            pedidas = d.get("tools_pedidas") or []
            alvo = f" → {', '.join(pedidas)}" if pedidas else f" → {d.get('motivo_parada')}"
            passos.append(("msg", "agent", "llm", _curto(f"passo {d.get('passo')} · {d.get('duracao_ms')} ms{alvo}", 52), False))
        elif tipo == "resource.read":
            passos.append(("msg", "agent", "mcp-gateway", _curto(f"resources/read {d.get('uri')}"), False))
            passos.append(("msg", "mcp-gateway", d.get("servidor", "skills-mcp"), f"{d.get('tamanho')} bytes · {d.get('duracao_ms')} ms", False))
        elif tipo == "skill.loaded":
            passos.append(("nota", f"skill ativa: {d.get('nome')} · {len(d.get('tools_permitidas') or [])} tools permitidas", MARINHO))
        elif tipo == "tool.called":
            servidor = d.get("servidor") or "?"
            passos.append(("msg", "agent", "mcp-gateway", f"tools/call {d.get('tool')}", False))
            if d.get("motivo"):
                passos.append(("nota", f"contramão: {_curto(d['motivo'], 70)}", "#da1e28"))
                passos.append(("msg", "mcp-gateway", "agent", "erro: bloqueada pela skill", True))
                continue
            passos.append(("msg", "mcp-gateway", servidor, f"{d.get('tool').split('.', 1)[-1]} · {d.get('duracao_ms')} ms", False))
            passos.append(("msg", "mcp-gateway", "bus", "tool.called", True))
            passos.append(("msg", "mcp-gateway", "agent", f"{d.get('status')} + proveniência", True))
        elif tipo == "client.asked":
            passos.append(("msg", "agent", "navegador", _curto(f"pergunta: {d.get('pergunta')}"), True))
        elif tipo == "client.answered":
            passos.append(("msg", "navegador", "agent", _curto(f"resposta: {d.get('texto')}"), False))
        elif tipo == "step.started":
            passos.append(("nota", f"parada {d.get('numero')} · {d.get('nome')}", CINZA))
        elif tipo == "route.planned":
            passos.append(("nota", f"rota planejada: {d.get('nome') or d.get('rota')}", MARINHO))
        elif tipo == "incident.detected":
            passos.append(("nota", f"incidente: {d.get('metafora')} · {_curto(d.get('descricao'), 60)}", "#da1e28"))
        elif tipo == "route.recalculated":
            passos.append(("nota", f"recálculo: {d.get('de')} → {d.get('para')} · {_curto(d.get('regra'), 50)}", LARANJA))
        elif tipo == "human.required":
            passos.append(("nota", f"pedágio: aprovação humana · {d.get('ticket_id')}", LARANJA))
        elif tipo == "agent.message":
            passos.append(("msg", "agent", "navegador", _curto(f"mensagem: {d.get('texto')}"), True))
        elif tipo == "run.finished":
            passos.append(("msg", "agent", "navegador", f"run.finished · {d.get('status')} · apólice {d.get('apolice') or '—'}", True))
    return passos


def sequencia(raiz: Path, gravacao: str, titulo: str, recorte: tuple[str, int, int] | None = None) -> str:
    """O SVG de um diagrama de sequência a partir de uma gravação real.

    recorte: (tipo de evento âncora, eventos antes, eventos depois), para mostrar só um trecho.
    """
    eventos = _eventos(raiz, gravacao)
    if recorte:
        ancora, antes, depois = recorte
        i = next(n for n, e in enumerate(eventos) if e["tipo"] == ancora)
        eventos = eventos[max(0, i - antes) : i + depois + 1]
    passos = _passos(eventos)
    envolvidos = {p[1] for p in passos if p[0] == "msg"} | {p[2] for p in passos if p[0] == "msg"}
    ordem = ["navegador", "agent", "llm", "mcp-gateway"]
    servidores = sorted(n for n in envolvidos if n not in ordem and n != "bus")
    participantes = [p for p in ordem if p in envolvidos] + servidores + (["bus"] if "bus" in envolvidos else [])
    x = {p: 40 + LARGURA_COLUNA * i + LARGURA_COLUNA / 2 for i, p in enumerate(participantes)}
    largura = 80 + LARGURA_COLUNA * len(participantes)
    altura = TOPO + ALTURA_LINHA * (len(passos) + 1) + 40
    rotulos = {"navegador": "Navegador", "llm": "LLM (provedor)", "bus": "bus (Redis)"}
    s = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{largura:.0f}" height="{altura:.0f}" viewBox="0 0 {largura:.0f} {altura:.0f}"'
        f' font-family="{FONTE}, sans-serif" font-size="11">',
        f"<title>{escape(titulo)}</title>",
        '<defs><marker id="seta" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
        f'<path d="M0,0 L10,5 L0,10 z" fill="{TEXTO}"/></marker></defs>',
        f'<text x="20" y="22" font-size="14" font-weight="600" fill="{TEXTO}">{escape(titulo)}</text>',
    ]
    for p in participantes:
        cor = LARANJA if p == "mcp-gateway" else MARINHO if p == "agent" else CINZA
        s.append(f'<line x1="{x[p]}" y1="{TOPO}" x2="{x[p]}" y2="{altura - 30}" stroke="#c6c6c6" stroke-dasharray="4 4"/>')
        s.append(f'<rect x="{x[p] - 72}" y="{TOPO - 32}" width="144" height="26" rx="4" fill="white" stroke="{cor}" stroke-width="{2 if cor != CINZA else 1}"/>')
        s.append(f'<text x="{x[p]}" y="{TOPO - 15}" text-anchor="middle" font-weight="600" fill="{TEXTO}">{escape(rotulos.get(p, p))}</text>')
    y = TOPO + ALTURA_LINHA
    for passo in passos:
        if passo[0] == "nota":
            _, texto, cor = passo
            s.append(f'<rect x="30" y="{y - 15}" width="{largura - 60}" height="20" rx="3" fill="{cor}18" stroke="{cor}"/>')
            s.append(f'<text x="{largura / 2}" y="{y - 1}" text-anchor="middle" fill="{TEXTO}">{escape(texto)}</text>')
        else:
            _, de, para, texto, tracejada = passo
            traco = ' stroke-dasharray="5 3"' if tracejada else ""
            s.append(f'<line x1="{x[de]}" y1="{y}" x2="{x[para]}" y2="{y}" stroke="{TEXTO}"{traco} marker-end="url(#seta)"/>')
            meio = (x[de] + x[para]) / 2
            s.append(f'<text x="{meio}" y="{y - 4}" text-anchor="middle" font-family="{MONO}, monospace" font-size="9" fill="#393939">{escape(texto)}</text>')
        y += ALTURA_LINHA
    s.append(f'<text x="{largura - 20}" y="{altura - 10}" text-anchor="end" font-size="9" fill="{CINZA}">gerado de gravacoes/{gravacao}.jsonl (execução real)</text>')
    s.append("</svg>")
    return "\n".join(s)


SEQUENCIAS = {
    "sequencia-cena-5": ("cena-5", "A viagem completa, com skill (cena 5)", None),
    "sequencia-recalculo": ("cena-6", "Rua interditada e recálculo (cena 6)", ("incident.detected", 6, 6)),
    "sequencia-pedagio": ("cena-7", "Pedágio: aprovação humana (cena 7)", ("human.required", 8, 4)),
}


def dots(raiz: Path) -> dict[str, str]:
    return {
        "tbox": tbox(raiz),
        "tbox-jornada": tbox_jornada(raiz),
        "abox-ana": abox_ana(raiz),
        "camadas": camadas(raiz),
        "c4-contexto": c4_contexto(raiz),
        "c4-containers": c4_containers(raiz),
        "c4-componentes": c4_componentes(raiz),
        "gateway": gateway(raiz),
    }


def svgs(raiz: Path) -> dict[str, str]:
    return {nome: sequencia(raiz, g, t, r) for nome, (g, t, r) in SEQUENCIAS.items()}
