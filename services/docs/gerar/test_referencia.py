"""A referência técnica acompanha o repositório: tipos, relações, instâncias, serviços e gravações."""

import json
import re

import yaml

import diagramas_referencia as dr
import referencia as ref
from test_diagramas import RAIZ


def _ontologia():
    return ref.carregar(RAIZ)


def test_tbox_tem_todo_tipo_do_esquema():
    o = _ontologia()
    dominio, jornada = dr.tbox(RAIZ), dr.tbox_jornada(RAIZ)
    for tipo in o.tipos:
        alvo = jornada if tipo in dr.TIPOS_DA_JORNADA else dominio
        assert f'"{tipo}" [label=' in alvo, tipo


def test_tbox_tem_toda_relacao_observada_com_multiplicidade():
    dominio, jornada = dr.tbox(RAIZ), dr.tbox_jornada(RAIZ)
    for (rel, origem, destino), (mult_origem, mult_destino, _) in ref.cardinalidades(_ontologia()).items():
        aresta = f'"{origem}" -> "{destino}" [label="{rel}", taillabel="{mult_origem}", headlabel="{mult_destino}"'
        assert aresta in dominio or aresta in jornada, (rel, origem, destino)


def test_propriedades_observadas_estao_nas_classes():
    o = _ontologia()
    dominio = dr.tbox(RAIZ)
    cliente = ref.propriedades_observadas(o)["Cliente"]
    assert cliente and all(f"attr_{p}" in dominio for p in cliente)


def test_cardinalidade_bate_com_as_instancias():
    # A Ana tem duas contas: Cliente → Conta não pode ser "1" no destino.
    card = ref.cardinalidades(_ontologia())
    _, no_destino, arestas = card[("POSSUI", "Cliente", "Conta")]
    assert no_destino.endswith("n") and arestas >= 2


def test_abox_tem_a_ana_e_os_vizinhos_diretos():
    o = _ontologia()
    abox = dr.abox_ana(RAIZ)
    vizinhos = {r.para for r in o.relacoes if r.de == "cliente-ana"} | {r.de for r in o.relacoes if r.para == "cliente-ana"}
    for ident in {"cliente-ana", *vizinhos}:
        assert f'"{ident}" [label=' in abox, ident


def test_numeros_do_grafo_vem_da_ontologia():
    o = _ontologia()
    texto = ref.fragmento_numeros_grafo(o, RAIZ)
    assert f"{len(o.entidades)} entidades, {len(o.relacoes)} relações" in texto
    assert f"{len(o.tipos)} tipos" in texto


def test_c4_containers_tem_todo_servico_e_as_rotas_do_nginx():
    compose = yaml.safe_load((RAIZ / "docker-compose.yml").read_text(encoding="utf-8"))
    dot = dr.c4_containers(RAIZ)
    for nome, servico in compose["services"].items():
        if not servico.get("profiles"):
            assert f'"{nome}" [label=' in dot, nome
    caminhos = {c for c, _, _ in dr._rotas_do_nginx(RAIZ)}
    assert {"/api/", "/auth/", "/bastidores/"} <= caminhos


def test_c4_componentes_tem_todo_modulo():
    dot = dr.c4_componentes(RAIZ)
    for _, pacote, pasta, _ in dr.COMPONENTES:
        for arquivo in (RAIZ / pasta).glob("*.py"):
            if arquivo.stem not in ("__init__", "__main__"):
                assert f'"{pacote}.{arquivo.stem}"' in dot, arquivo


def test_gateway_tem_todo_upstream_e_o_catalogo_bate():
    upstreams = yaml.safe_load((RAIZ / "services/mcp-gateway/config/upstreams.yaml").read_text(encoding="utf-8"))
    dot = dr.gateway(RAIZ)
    for u in upstreams["servidores"]:
        assert f'"{u["nome"]}" [label=' in dot, u["nome"]
    cat = ref.catalogo(RAIZ)
    prefixos = {u["prefixo"] for u in upstreams["servidores"]}
    assert all(t["nome"].split(".")[0] in prefixos for t in cat["tools"])
    assert f"**{len(cat['tools'])} tools**" in ref.fragmento_catalogo(cat)


def test_sequencias_mostram_os_eventos_das_gravacoes():
    for nome, (gravacao, _, recorte) in dr.SEQUENCIAS.items():
        svg = dr.svgs(RAIZ)[nome]
        eventos = [json.loads(linha) for linha in (RAIZ / "gravacoes" / f"{gravacao}.jsonl").read_text(encoding="utf-8").splitlines() if linha.strip()]
        tools = [e["dados"]["tool"] for e in eventos if e.get("tipo") == "tool.called"]
        if recorte is None:
            # A viagem inteira: toda tool chamada aparece na sequência.
            assert all(f"tools/call {t}" in svg for t in tools), nome
        else:
            assert re.search(r"<svg [^>]*viewBox", svg) and "gerado de gravacoes/" in svg


def test_tools_do_host_lidas_do_agent():
    nomes = {n for n, _ in ref.tools_do_host(RAIZ)}
    assert {"conversa.perguntar_cliente", "agente.carregar_skill", "navegacao.planejar_rota"} <= nomes
