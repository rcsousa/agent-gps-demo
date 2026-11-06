"""Números e tabelas da referência técnica, calculados do repositório no build do docs.

A ontologia é lida pelo mesmo carregador que o seed usa para montar o Neo4j
(contexto_mcp/ontologia.py, importado do repositório pelo PYTHONPATH): o que a doc mostra é o que vai para o grafo.
Nada aqui é escrito à mão: cada número das páginas vem de um fragmento gerado por este módulo.
"""

import ast
import json
from collections import Counter, defaultdict
from pathlib import Path

import yaml

from contexto_mcp.ontologia import BAIRRO_VARIAVEL, Ontologia, carregar_ontologia

PASTA_ONTOLOGIA = "services/contexto-mcp/ontologia"
CATALOGO = "services/smoke/referencia/catalogo.json"
# As relações que a tool contexto.consultar_regras percorre (ver contexto_mcp/grafo.py, "regras").
RELACOES_DE_REGRA = ("EXIGE", "REQUER", "SUJEITA_A", "REGIDO_POR")


def carregar(raiz: Path) -> Ontologia:
    return carregar_ontologia(raiz / PASTA_ONTOLOGIA, limites=None)


def catalogo(raiz: Path) -> dict:
    return json.loads((raiz / CATALOGO).read_text(encoding="utf-8"))


# --- O modelo (T-Box) ----------------------------------------------------------------------

def bairro_do_tipo(o: Ontologia, tipo: str) -> str:
    return o.tipos[tipo].bairro


def instancias_por_tipo(o: Ontologia) -> Counter:
    return Counter(e.tipo for e in o.entidades.values())


def propriedades_observadas(o: Ontologia) -> dict[str, list[str]]:
    """As chaves de atributos que as instâncias de cada tipo trazem (o esquema não as declara)."""
    props: dict[str, set[str]] = defaultdict(set)
    for e in o.entidades.values():
        props[e.tipo] |= set(e.atributos)
    return {t: sorted(props[t]) for t in o.tipos}


def tem_estado(o: Ontologia) -> set[str]:
    return {e.tipo for e in o.entidades.values() if e.estado}


def _faixa(valores: list[int]) -> str:
    menor, maior = min(valores), max(valores)
    fim = "n" if maior > 1 else str(maior)
    return fim if str(menor) == fim else f"{menor}..{fim}"


def cardinalidades(o: Ontologia) -> dict[tuple[str, str, str], tuple[str, str, int]]:
    """(relação, tipo de origem, tipo de destino) -> (multiplicidade na origem, no destino, arestas).

    Observada nas instâncias: no destino, quantos destinos cada origem desse tipo tem (incluindo as
    que não têm nenhum); na origem, quantas origens chegam a cada destino.
    """
    tipo = {i: e.tipo for i, e in o.entidades.items()}
    saidas: dict[tuple, Counter] = defaultdict(Counter)
    entradas: dict[tuple, Counter] = defaultdict(Counter)
    for r in o.relacoes:
        chave = (r.tipo, tipo[r.de], tipo[r.para])
        saidas[chave][r.de] += 1
        entradas[chave][r.para] += 1
    por_tipo = defaultdict(list)
    for i, t in tipo.items():
        por_tipo[t].append(i)
    resultado = {}
    for chave in saidas:
        _, origem, destino = chave
        no_destino = [saidas[chave][i] for i in por_tipo[origem]]
        na_origem = [entradas[chave][i] for i in por_tipo[destino]]
        resultado[chave] = (_faixa(na_origem), _faixa(no_destino), sum(saidas[chave].values()))
    return dict(sorted(resultado.items()))


# --- A profundidade ------------------------------------------------------------------------

def _sucessores(o: Ontologia, tipos_relacao: tuple[str, ...] | None = None) -> dict[str, list[tuple[str, str]]]:
    proximos: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for r in o.relacoes:
        if tipos_relacao is None or r.tipo in tipos_relacao:
            proximos[r.de].append((r.tipo, r.para))
    return proximos


def caminho_mais_longo(o: Ontologia, tipos_relacao: tuple[str, ...] | None = None) -> list[tuple[str, str | None]]:
    """O caminho dirigido simples mais longo do grafo de instâncias: [(entidade, relação que sai dela)]."""
    proximos = _sucessores(o, tipos_relacao)
    melhor: list[tuple[str, str | None]] = []

    def explorar(no: str, caminho: list[tuple[str, str | None]], vistos: set[str]) -> None:
        nonlocal melhor
        if len(caminho) > len(melhor):
            melhor = list(caminho)
        for relacao, prox in sorted(proximos.get(no, [])):
            if prox in vistos:
                continue
            caminho[-1] = (no, relacao)
            caminho.append((prox, None))
            vistos.add(prox)
            explorar(prox, caminho, vistos)
            vistos.discard(prox)
            caminho.pop()
            caminho[-1] = (no, None)

    for inicio in sorted(o.entidades):
        explorar(inicio, [(inicio, None)], {inicio})
    return melhor


def vizinhanca(o: Ontologia, centro: str, saltos: int) -> tuple[set[str], list]:
    """As entidades a até N saltos do centro (em qualquer sentido) e as relações entre elas."""
    vizinhos: dict[str, set[str]] = defaultdict(set)
    for r in o.relacoes:
        vizinhos[r.de].add(r.para)
        vizinhos[r.para].add(r.de)
    nivel = {centro: 0}
    fronteira = [centro]
    for n in range(1, saltos + 1):
        nova = []
        for no in fronteira:
            for v in sorted(vizinhos[no]):
                if v not in nivel:
                    nivel[v] = n
                    nova.append(v)
        fronteira = nova
    dentro = set(nivel)
    return dentro, [r for r in o.relacoes if r.de in dentro and r.para in dentro]


def camadas(o: Ontologia, raiz: Path) -> dict:
    incidentes = yaml.safe_load((raiz / "services/simulator/incidentes.yaml").read_text(encoding="utf-8"))
    lista = incidentes.get("incidentes", incidentes) if isinstance(incidentes, dict) else incidentes
    confiancas = Counter(e.proveniencia.confianca for e in o.entidades.values())
    confiancas.update(r.proveniencia.confianca for r in o.relacoes)
    return {
        "tipos": len(o.tipos),
        "tipos_relacao": len(o.tipos_relacao),
        "bairros": len(o.bairros),
        "entidades": len(o.entidades),
        "relacoes": len(o.relacoes),
        "com_estado": sum(1 for e in o.entidades.values() if e.estado),
        "incidentes": len(lista),
        "fontes": len({e.proveniencia.fonte for e in o.entidades.values()} | {r.proveniencia.fonte for r in o.relacoes}),
        "confianca": dict(sorted(confiancas.items())),
    }


# --- Os fragmentos em Markdown (inseridos nas páginas com --8<--) --------------------------

def _tabela(cabecalho: list[str], linhas: list[list]) -> str:
    saida = ["| " + " | ".join(cabecalho) + " |", "| " + " | ".join("---" for _ in cabecalho) + " |"]
    saida += ["| " + " | ".join(str(c) for c in linha) + " |" for linha in linhas]
    return "\n".join(saida) + "\n"


def _nome_bairro(o: Ontologia, ident: str) -> str:
    return "variável (cada instância diz o seu)" if ident == BAIRRO_VARIAVEL else o.bairro(ident).nome


def fragmento_numeros_grafo(o: Ontologia, raiz: Path) -> str:
    c = camadas(o, raiz)
    longo = caminho_mais_longo(o)
    regra = caminho_mais_longo(o, RELACOES_DE_REGRA)
    confianca = ", ".join(f"{n} {k}" for k, n in c["confianca"].items())
    return _tabela(
        ["Camada", "O que guarda", "Tamanho"],
        [
            ["Esquema (T-Box)", "tipos de entidade e relações permitidas", f"{c['tipos']} tipos, {c['tipos_relacao']} tipos de relação, {c['bairros']} bairros"],
            ["Instâncias (A-Box)", "as entidades e as relações do banco", f"{c['entidades']} entidades, {c['relacoes']} relações"],
            ["Estado vivo", "status, latência, custo e vigência, que o simulador muda", f"{c['com_estado']} entidades com estado, {c['incidentes']} incidentes possíveis"],
            ["Proveniência", "fonte, data, responsável e confiança de cada nó e de cada relação", f"{c['fontes']} fontes; confiança: {confianca}"],
            ["Profundidade", "o caminho dirigido mais longo entre instâncias", f"{len(longo) - 1} saltos"],
            ["Cadeia de regras", f"o caminho mais longo só por {', '.join(RELACOES_DE_REGRA)}", f"{len(regra) - 1} saltos"],
        ],
    )


def fragmento_tipos(o: Ontologia) -> str:
    contagem = instancias_por_tipo(o)
    props = propriedades_observadas(o)
    estado = tem_estado(o)
    linhas = []
    for t, d in sorted(o.tipos.items(), key=lambda kv: (kv[1].bairro, kv[0])):
        atributos = ", ".join(f"`attr_{p}`" for p in props[t]) or "—"
        linhas.append([d.exibicao, f"`:Entidade:{t}`", _nome_bairro(o, d.bairro), contagem[t], atributos, "sim" if t in estado else "—"])
    return _tabela(["Tipo", "Rótulos no Neo4j", "Bairro", "Instâncias", "Propriedades observadas", "Estado vivo"], linhas)


def fragmento_relacoes(o: Ontologia) -> str:
    card = cardinalidades(o)
    linhas = []
    for nome, rel in o.tipos_relacao.items():
        observadas = [(k, v) for k, v in card.items() if k[0] == nome]
        usos = "<br>".join(f"{k[1]} `{v[0]}` → `{v[1]}` {k[2]} ({v[2]})" for k, v in observadas) or "nenhuma instância"
        linhas.append([f"`{nome}`", rel.descricao, ", ".join(rel.origem), ", ".join(rel.destino), usos])
    return _tabela(["Relação", "Significado", "Origem permitida", "Destino permitido", "Observada: multiplicidade (arestas)"], linhas)


def fragmento_caminhos(o: Ontologia) -> str:
    def descrever(caminho):
        partes = []
        for ident, relacao in caminho:
            e = o.entidades[ident]
            partes.append(f"{e.nome} ({o.tipos[e.tipo].exibicao})")
            if relacao:
                partes.append(f"`{relacao}`")
        return " → ".join(partes)

    return (
        f"- **O caminho dirigido mais longo** ({len(caminho_mais_longo(o)) - 1} saltos): "
        f"{descrever(caminho_mais_longo(o))}\n"
        f"- **A cadeia de regras mais longa** ({len(caminho_mais_longo(o, RELACOES_DE_REGRA)) - 1} saltos, "
        f"só por {', '.join(f'`{r}`' for r in RELACOES_DE_REGRA)}): {descrever(caminho_mais_longo(o, RELACOES_DE_REGRA))}\n"
    )


def fragmento_catalogo(cat: dict) -> str:
    por_servidor: dict[str, list[dict]] = defaultdict(list)
    for t in cat["tools"]:
        por_servidor[t["nome"].split(".")[0]].append(t)
    saida = [
        f"O gateway expõe **{len(cat['tools'])} tools** de **{len(por_servidor)} servidores**, "
        f"**{len(cat['prompts'])} prompts** e **{len(cat['skills'])} skills**.\n"
    ]
    for servidor in sorted(por_servidor):
        saida.append(f"\n#### `{servidor}` · {len(por_servidor[servidor])} tools\n")
        linhas = []
        for t in sorted(por_servidor[servidor], key=lambda x: x["nome"]):
            esquema = t.get("parametros") or {}
            obrigatorios = set(esquema.get("required", []))
            params = ", ".join(
                f"`{p}`{'' if p in obrigatorios else '?'}: {(d.get('type') or 'objeto') if isinstance(d, dict) else ''}"
                for p, d in (esquema.get("properties") or {}).items()
            ) or "—"
            descricao = " ".join((t.get("descricao") or "").split())
            linhas.append([f"`{t['nome']}`", descricao.replace("|", "\\|"), params])
        saida.append(_tabela(["Tool", "Descrição", "Parâmetros (`?` = opcional)"], linhas))
    saida.append("\n#### Prompts\n")
    saida.append(_tabela(
        ["Prompt", "Descrição", "Argumentos"],
        [[f"`{p['nome']}`", " ".join((p.get("descricao") or "").split()), ", ".join(f"`{a}`" for a in p.get("argumentos", [])) or "—"] for p in cat["prompts"]],
    ))
    saida.append("\n#### Skills\n")
    saida.append(_tabela(
        ["Skill", "Para que serve", "Tools permitidas"],
        [[f"`{s['nome']}`", " ".join(s.get("descricao", "").split()), len(s.get("tools_permitidas", []))] for s in cat["skills"]],
    ))
    return "".join(saida)


def fragmento_numeros_gateway(raiz: Path, cat: dict) -> str:
    upstreams = yaml.safe_load((raiz / "services/mcp-gateway/config/upstreams.yaml").read_text(encoding="utf-8"))
    tools = Counter(t["nome"].split(".")[0] for t in cat["tools"])
    prompts = Counter(p["nome"].split(".")[0] for p in cat["prompts"])
    linhas = []
    for u in upstreams["servidores"]:
        serve = []
        if tools[u["prefixo"]]:
            serve.append(f"{tools[u['prefixo']]} tools")
        if prompts[u["prefixo"]]:
            serve.append(f"{prompts[u['prefixo']]} prompts")
        if u["nome"] == "skills-mcp":
            serve.append(f"{len(cat['skills'])} skills (SEP-2640)")
        linhas.append([f"`{u['nome']}`", f"`{u['prefixo']}.*`", ", ".join(serve) or "—", f"`{u['url']}`"])
    return _tabela(["Servidor MCP", "Nome para o agente", "Serve", "Endereço interno"], linhas)


def tools_do_host(raiz: Path) -> list[tuple[str, str]]:
    """(nome, descrição) das tools que o próprio agente executa, lidas de agent/ferramentas.py."""
    arvore = ast.parse((raiz / "services/agent/src/agent/ferramentas.py").read_text(encoding="utf-8"))
    tools = []
    for no in ast.walk(arvore):
        if isinstance(no, ast.Call) and getattr(no.func, "id", None) == "DefinicaoTool" and len(no.args) >= 2:
            nome, descricao = no.args[0], no.args[1]
            if isinstance(nome, ast.Constant):
                try:
                    texto = ast.literal_eval(descricao)
                except ValueError:
                    texto = ""
                tools.append((nome.value, " ".join(str(texto).split())))
    return sorted(tools)


def fragmento_tools_do_host(raiz: Path) -> str:
    linhas = [[f"`{nome}`", descricao.replace("|", "\\|")] for nome, descricao in tools_do_host(raiz)]
    return _tabela(["Tool do host (executada pelo agent)", "Para que serve"], linhas)


def gerar(raiz: Path, saida: Path) -> list[Path]:
    saida.mkdir(parents=True, exist_ok=True)
    o = carregar(raiz)
    cat = catalogo(raiz)
    fragmentos = {
        "numeros-grafo.md": fragmento_numeros_grafo(o, raiz),
        "tipos.md": fragmento_tipos(o),
        "relacoes.md": fragmento_relacoes(o),
        "caminhos.md": fragmento_caminhos(o),
        "catalogo.md": fragmento_catalogo(cat),
        "numeros-gateway.md": fragmento_numeros_gateway(raiz, cat),
        "tools-do-host.md": fragmento_tools_do_host(raiz),
    }
    gerados = []
    for nome, texto in fragmentos.items():
        caminho = saida / nome
        caminho.write_text(texto, encoding="utf-8")
        gerados.append(caminho)
    return gerados
