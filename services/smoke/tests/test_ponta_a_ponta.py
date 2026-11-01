"""Checagem ponta a ponta, pela rede interna do compose, com a demo no ar.

O smoke é ferramenta de teste: ele pode conhecer todos os serviços.
O agente, não. Por isso as tools são sempre chamadas pelo gateway.
"""

import asyncio
import json
import os
import time

import httpx
import pytest
from redis import Redis

from bussola_comum.cliente_mcp import conectar
from bussola_comum.skills import (
    CHAVE_EXECUCAO,
    CHAVE_SKILL_ATIVA,
    ler_arquivo,
    listar_skills,
    tools_permitidas,
)

SERVICOS_PYTHON = [
    "agent",
    "mcp-gateway",
    "skills-mcp",
    "contexto-mcp",
    "cliente-mcp",
    "consentimento-mcp",
    "risco-mcp",
    "seguradoras-mcp",
    "pagamentos-mcp",
    "atendimento-mcp",
    "canais-mcp",
    "simulator",
]
SERVIDORES_MCP = [s for s in SERVICOS_PYTHON if s.endswith("-mcp")]
GATEWAY = "http://mcp-gateway:8000/mcp"
SIMULADOR = "http://simulator:8000"
TOKEN = os.environ["GATEWAY_TOKEN"]


def gateway(tool: str, argumentos: dict | None = None):
    """Chama uma tool (ou lê um resource) pelo gateway, como o agente fará."""

    async def chamar():
        async with conectar(GATEWAY, TOKEN) as cliente:
            if "://" in tool:
                return await cliente.read_resource(tool)
            if tool == "--listar":
                return await cliente.list_tools()
            if tool == "--prompts":
                return await cliente.list_prompts()
            return await cliente.call_tool(tool, argumentos or {})

    return asyncio.run(chamar())


def dados(tool: str, argumentos: dict | None = None) -> dict:
    resultado = gateway(tool, argumentos)
    assert not resultado.is_error, resultado.content[0].text
    return resultado.structured_content


def simulador(metodo: str, caminho: str) -> dict:
    resposta = httpx.request(metodo, f"{SIMULADOR}{caminho}", timeout=60)
    resposta.raise_for_status()
    return resposta.json()


# --- Fase 1: fundação ----------------------------------------------------------


@pytest.mark.parametrize("servico", SERVICOS_PYTHON)
def test_saude_de_cada_servico(servico):
    resposta = httpx.get(f"http://{servico}:8000/saude", timeout=5)
    assert resposta.status_code == 200, resposta.text
    assert resposta.json()["status"] == "ok"


def test_contexto_mcp_enxerga_o_grafo():
    corpo = httpx.get("http://contexto-mcp:8000/saude", timeout=5).json()
    assert corpo["dependencias"]["graph"] == "ok"


def test_gateway_recusa_chamada_sem_token():
    assert httpx.get("http://mcp-gateway:8000/saude/servicos", timeout=5).status_code == 401
    assert httpx.post(GATEWAY, json={}, timeout=5).status_code == 401


def test_status_pelo_caminho_web_agent_gateway():
    corpo = httpx.get("http://web/api/status", timeout=10).json()
    assert corpo["gateway"] == "ok"
    assert corpo["barramento"] == "ok"
    assert sorted(s["nome"] for s in corpo["servicos"]) == sorted(SERVIDORES_MCP)
    assert all(s["status"] == "ok" for s in corpo["servicos"])
    assert corpo["ferramentas"] == 41
    assert corpo["prompts"] == 3


def test_web_serve_a_aplicacao():
    resposta = httpx.get("http://web/", timeout=5)
    assert resposta.status_code == 200
    assert '<div id="raiz">' in resposta.text


def test_bastidores_servidos_pelo_web():
    resposta = httpx.get("http://web/bastidores/", timeout=5, follow_redirects=True)
    assert resposta.status_code == 200
    assert "Bastidores" in resposta.text


# --- Fase 2: camada de contexto (agora pelo gateway) ---------------------------


def test_grafo_semeado_com_a_ana():
    assert dados("contexto.consultar_entidade", {"id": "cliente-ana"})["entidade"]["nome"] == "Ana Ribeiro"


def test_tres_rotas_com_estimativa():
    rotas = dados("contexto.consultar_rota")["rotas"]
    assert {r["id"] for r in rotas} == {"rota-rapida", "rota-economica", "rota-assistida"}
    assert all(r["estimativa"]["tempo_texto"].startswith("~") for r in rotas)


def test_mapa_com_todos_os_nos_posicionados():
    mapa = json.loads(gateway("contexto://mapa").contents[0].text)
    assert 150 <= len(mapa["nos"]) <= 300
    assert all(n["x"] is not None and n["y"] is not None for n in mapa["nos"])


# --- Fase 3: gateway, domínios e simulador -------------------------------------


@pytest.fixture
def mundo_limpo():
    simulador("POST", "/reset")
    yield
    simulador("POST", "/reset")


def test_gateway_agrega_41_tools_qualificadas():
    nomes = {t.name for t in gateway("--listar").tools}
    assert len(nomes) == 41
    assert all("." in n for n in nomes)
    assert {"cliente.obter_perfil", "seguradoras.cotar_seguro", "contexto.consultar_rota"} <= nomes
    assert not any(n.endswith(".ping") for n in nomes)


def test_proveniencia_carimbada_pelo_gateway():
    resultado = gateway("cliente.obter_perfil", {"cliente_id": "cliente-ana"})
    proveniencia = resultado.meta["bussola/proveniencia"]
    assert proveniencia["servidor"] == "cliente-mcp" and proveniencia["status"] == "ok"


def test_todo_cliente_do_mapa_existe_no_sistema_de_clientes():
    clientes = dados("contexto.buscar_entidades", {"tipo": "Cliente"})["entidades"]
    for cliente in clientes:
        assert dados("cliente.obter_perfil", {"cliente_id": cliente["id"]})["nome"] == cliente["nome"]


def test_jornada_feliz_da_ana(mundo_limpo):
    ana = {"cliente_id": "cliente-ana"}
    assert dados("consentimento.verificar", {**ana, "finalidade": "finalidade-oferta-personalizada"})[
        "permitido"
    ]
    assert dados("risco.consultar_elegibilidade", {**ana, "produto_id": "produto-residencial-farol"})[
        "elegivel"
    ]
    precos = {
        s: dados("seguradoras.cotar_seguro", {**ana, "seguradora": s})
        for s in ("ancora", "farol", "horizonte")
    }
    assert {s: round(c["premio_anual"]) for s, c in precos.items()} == {
        "ancora": 320,
        "farol": 310,
        "horizonte": 280,
    }

    cotacao = precos["farol"]
    alcada = dados(
        "risco.verificar_alcada", {"premio_anual": cotacao["premio_anual"], "importancia_segurada": 780000}
    )
    assert alcada["exige_aprovacao_humana"] is False
    proposta = dados("seguradoras.gerar_proposta", {"cotacao_id": cotacao["cotacao_id"]})
    dados("seguradoras.registrar_aceite", {"proposta_id": proposta["proposta_id"]})
    pagamento = dados(
        "pagamentos.processar_pagamento",
        {**ana, "valor": cotacao["premio_anual"], "referencia": proposta["proposta_id"]},
    )
    apolice = dados(
        "seguradoras.emitir_apolice",
        {"proposta_id": proposta["proposta_id"], "pagamento_id": pagamento["pagamento_id"]},
    )
    assert apolice["status"] == "emitida" and apolice["seguradora"] == "Farol Seguros"


def test_rua_interditada_e_recalculo(mundo_limpo):
    simulador("POST", "/incidentes/cotacao-ancora-fora/aplicar")
    resultado = gateway("seguradoras.cotar_seguro", {"cliente_id": "cliente-ana", "seguradora": "ancora"})
    assert resultado.is_error and "fora do ar" in resultado.content[0].text
    rapida = dados("contexto.consultar_rota", {"rota": "rota-rapida"})["rotas"][0]
    assert rapida["estimativa"]["bloqueada"] is True
    assert rapida["alertas"][0]["entidade"]["id"] == "api-cotacao-ancora"

    simulador("POST", "/incidentes/cotacao-ancora-fora/remover")
    rapida = dados("contexto.consultar_rota", {"rota": "rota-rapida"})["rotas"][0]
    assert rapida["estimativa"]["bloqueada"] is False
    assert not gateway(
        "seguradoras.cotar_seguro", {"cliente_id": "cliente-ana", "seguradora": "ancora"}
    ).is_error


def test_pedagio_com_aprovacao_do_apresentador(mundo_limpo):
    simulador("POST", "/incidentes/alcada-ana-excedida/aplicar")
    cotacao = dados("seguradoras.cotar_seguro", {"cliente_id": "cliente-ana", "seguradora": "farol"})
    assert cotacao["importancia_segurada"] == 1800000
    proposta = dados("seguradoras.gerar_proposta", {"cotacao_id": cotacao["cotacao_id"]})
    assert proposta["exige_aprovacao_humana"] is True
    ticket = dados(
        "atendimento.solicitar_aprovacao", {"proposta_id": proposta["proposta_id"], "motivo": "IS acima"}
    )
    simulador("POST", f"/aprovacoes/{ticket['ticket_id']}/aprovar")
    assert (
        dados("atendimento.consultar_aprovacao", {"ticket_id": ticket["ticket_id"]})["status"] == "aprovada"
    )


def test_todos_os_incidentes_se_aplicam_ao_mapa_real(mundo_limpo):
    """Cada efeito do catálogo aponta para entidades que existem no grafo."""
    for incidente in simulador("GET", "/incidentes"):
        assert simulador("POST", f"/incidentes/{incidente['id']}/aplicar")["ativo"] is True
    assert all(i["ativo"] for i in simulador("GET", "/incidentes"))


def test_chamadas_viram_eventos_no_barramento():
    redis = Redis.from_url("redis://bus:6379/0", decode_responses=True)
    antes = redis.xlen("bussola:eventos")
    gateway("cliente.obter_perfil", {"cliente_id": "cliente-ana"})
    [(_, evento)] = redis.xrevrange("bussola:eventos", count=1)
    assert redis.xlen("bussola:eventos") > antes
    assert evento["tipo"] == "tool.called" and json.loads(evento["dados"])["tool"] == "cliente.obter_perfil"


def test_desligar_tool_pelo_painel_do_web(mundo_limpo):
    """O painel desliga pelo caminho do web (/simulador), e o agente sente a falha no gateway."""
    nome = "seguradoras.cotar_seguro"
    httpx.post(f"http://web/simulador/tools/{nome}/desligar", timeout=10).raise_for_status()

    resultado = gateway(nome, {"cliente_id": "cliente-ana", "seguradora": "farol"})
    assert resultado.is_error and "fora do ar" in resultado.content[0].text
    assert resultado.meta["bussola/proveniencia"]["motivo"] == "desligada"

    status = httpx.get("http://web/api/status", timeout=10).json()
    assert status["ferramentas_fora"] == 1
    [seguradoras] = [s for s in status["servicos"] if s["nome"] == "seguradoras-mcp"]
    assert {f["nome"] for f in seguradoras["ferramentas"] if f["fora"]} == {"cotar_seguro"}
    assert {f["nome"] for f in seguradoras["ferramentas"] if not f["visivel"]} == {"ping"}

    httpx.post("http://web/simulador/tools/religar-todas", timeout=10).raise_for_status()
    assert not gateway(nome, {"cliente_id": "cliente-ana", "seguradora": "farol"}).is_error


# --- Fase 4: skills-workflow ---------------------------------------------------

PRINCIPAL = "skill://contratacao-seguro-residencial/SKILL.md"


def _com_cliente(acao):
    async def executar():
        async with conectar(GATEWAY, TOKEN) as cliente:
            return await acao(cliente)

    return asyncio.run(executar())


def test_quatro_skills_pelo_gateway_com_digest_verificado():
    async def verificar(cliente):
        entradas = await listar_skills(cliente)
        for entrada in entradas:
            for arquivo in entrada["resources"]:
                await ler_arquivo(cliente, arquivo["uri"], entrada)  # falha se digest ou tamanho divergirem
        return entradas

    entradas = _com_cliente(verificar)
    assert {e["frontmatter"]["name"] for e in entradas} == {
        "contratacao-seguro-residencial",
        "verificacao-consentimento",
        "cotacao-multisseguradora",
        "escalonamento-humano",
    }


def test_toda_tool_permitida_existe_no_gateway():
    entradas = _com_cliente(listar_skills)
    catalogo = {t.name for t in gateway("--listar").tools}
    for entrada in entradas:
        assert tools_permitidas(entrada["frontmatter"]) <= catalogo, entrada["uri"]


def test_contramao_com_skill_ativa():
    async def chamar(cliente):
        # A skill tem ordem garantida: toda chamada com ela precisa da execução.
        meta = {CHAVE_SKILL_ATIVA: PRINCIPAL, CHAVE_EXECUCAO: f"smoke-{time.time_ns()}"}
        permitida = await cliente.call_tool("cliente.obter_perfil", {"cliente_id": "cliente-ana"}, meta=meta)
        bloqueada = await cliente.call_tool("pagamentos.estornar", {"pagamento_id": "x"}, meta=meta)
        sem_skill = await cliente.call_tool("pagamentos.estornar", {"pagamento_id": "x"})
        return permitida, bloqueada, sem_skill

    permitida, bloqueada, sem_skill = _com_cliente(chamar)
    assert not permitida.is_error
    assert bloqueada.is_error and bloqueada.meta["bussola/proveniencia"]["motivo"] == "fora_da_skill"
    # Sem skill, a chamada chega ao servidor (e falha lá, porque o pagamento não existe).
    assert "motivo" not in sem_skill.meta["bussola/proveniencia"]
    assert "não encontrado" in sem_skill.content[0].text


def test_status_conta_as_skills():
    assert httpx.get("http://web/api/status", timeout=10).json()["skills"] == 4


# --- Fase 5: agente e eventos (provedor roteiro: ensaio sem LLM) ----------------

API_AGENTE = "http://web/api"


def _executar(modo: str, ao_perguntar=None, canal: str | None = None) -> tuple[str, list[dict]]:
    """Inicia uma execução e lê o SSE até o run.finished, respondendo pela Ana."""
    corpo = {"modo": modo, "provedor": "roteiro", **({"canal": canal} if canal else {})}
    ident = httpx.post(f"{API_AGENTE}/execucoes", json=corpo, timeout=10).json()["id"]
    eventos: list[dict] = []
    with httpx.stream("GET", f"{API_AGENTE}/execucoes/{ident}/eventos", timeout=120) as resposta:
        for linha in resposta.iter_lines():
            if not linha.startswith("data:"):
                continue
            evento = json.loads(linha[5:])
            eventos.append(evento)
            if evento["tipo"] == "client.asked":
                if ao_perguntar:
                    ao_perguntar(len([e for e in eventos if e["tipo"] == "client.asked"]))
                texto = evento["dados"]["opcoes"][0]
                httpx.post(f"{API_AGENTE}/execucoes/{ident}/resposta", json={"texto": texto}, timeout=10)
            if evento["tipo"] == "run.finished":
                break
    return ident, eventos


def _do_tipo(eventos: list[dict], tipo: str) -> list[dict]:
    return [e["dados"] for e in eventos if e["tipo"] == tipo]


def test_com_skill_ate_a_apolice(mundo_limpo):
    ident, eventos = _executar("com_skill")
    tipos = [e["tipo"] for e in eventos]
    assert tipos[0] == "run.started" and tipos[-1] == "run.finished"
    assert _do_tipo(eventos, "skill.loaded")[0]["nome"] == "contratacao-seguro-residencial"
    assert _do_tipo(eventos, "route.planned")[0]["rota"] == "rota-rapida"
    assert [p["numero"] for p in _do_tipo(eventos, "step.started")] == list(range(1, 10))
    chamadas = _do_tipo(eventos, "tool.called")
    assert chamadas and all(c["execucao_id"] == ident for c in chamadas)
    assert all(c["skill"] == "skill://contratacao-seguro-residencial/SKILL.md" for c in chamadas)
    fim = _do_tipo(eventos, "run.finished")[0]
    assert fim["status"] == "concluida" and fim["apolice"].startswith("ANC-")
    assert fim["metricas"]["tools_irrelevantes"] == []


def test_com_skill_recalcula_quando_a_ancora_cai(mundo_limpo):
    def derrubar(numero_da_pergunta: int) -> None:
        if numero_da_pergunta == 1:  # depois de planejar a rota rápida, antes da cotação
            simulador("POST", "/incidentes/cotacao-ancora-fora/aplicar")

    _, eventos = _executar("com_skill", ao_perguntar=derrubar)
    assert any(i["metafora"] == "Rua interditada" for i in _do_tipo(eventos, "incident.detected"))
    recalculos = [
        r for r in _do_tipo(eventos, "route.recalculated") if r["regra"].startswith("Rua interditada")
    ]
    assert [(r["de"], r["para"]) for r in recalculos] == [("rota-rapida", "rota-economica")]
    fim = _do_tipo(eventos, "run.finished")[0]
    assert fim["status"] == "concluida" and not fim["apolice"].startswith("ANC-")


def test_sem_skill_contrata_pelo_atalho_legado(mundo_limpo):
    _, eventos = _executar("sem_skill")
    fim = _do_tipo(eventos, "run.finished")[0]
    irrelevantes = fim["metricas"]["tools_irrelevantes"]
    assert {"cliente.obter_dossie_completo", "seguradoras.contratacao_expressa"} <= set(irrelevantes)
    assert fim["apolice"].startswith("EXP-")  # emitida sem consentimento, adequação nem aceite


def test_sem_contexto_nao_chama_tools(mundo_limpo):
    _, eventos = _executar("sem_contexto")
    assert _do_tipo(eventos, "tool.called") == []
    assert _do_tipo(eventos, "run.finished")[0]["metricas"]["chamadas_tool"] == 0


def test_provedor_real_sem_chave_falha_com_mensagem_clara():
    # O smoke nunca gasta tokens: com um LLM configurado, este cenário não se aplica.
    if httpx.get(f"{API_AGENTE}/status", timeout=10).json()["llm"]["configurado"]:
        pytest.skip("LLM configurado no .env: o smoke não chama o modelo de verdade.")
    ident = httpx.post(
        f"{API_AGENTE}/execucoes", json={"modo": "com_skill", "provedor": "anthropic"}, timeout=10
    ).json()["id"]
    for _ in range(50):
        estado = httpx.get(f"{API_AGENTE}/execucoes/{ident}", timeout=10).json()
        if estado["status"] == "erro":
            break
        time.sleep(0.2)
    assert estado["status"] == "erro" and "ANTHROPIC_API_KEY" in estado["erro"]


# --- Fase 5.1: persona por canal (prompts MCP) ------------------------------------


def test_gateway_serve_a_persona_de_cada_canal_da_ontologia():
    prompts = {p.name: p for p in gateway("--prompts").prompts}
    assert set(prompts) == {
        "canais.atendimento_app",
        "canais.atendimento_agencia",
        "canais.atendimento_central",
    }
    for prompt in prompts.values():
        canal = prompt.description.split("Canal: ")[1].split(".")[0]
        assert dados("contexto.consultar_entidade", {"id": canal})["entidade"]["tipo"] == "Canal"


def test_com_skill_na_agencia_fala_com_o_gerente(mundo_limpo):
    ident, eventos = _executar("com_skill", canal="agencia")
    assert _do_tipo(eventos, "run.started")[0]["canal"] == "agencia"
    [carregado] = _do_tipo(eventos, "prompt.loaded")
    assert carregado["nome"] == "canais.atendimento_agencia" and carregado["origem"] == "gateway"
    [lido] = _do_tipo(eventos, "prompt.read")
    assert lido["servidor"] == "canais-mcp" and lido["execucao_id"] == ident
    assert _do_tipo(eventos, "client.asked")[0]["pergunta"].startswith("Confirme com a Ana")
    assert _do_tipo(eventos, "run.finished")[0]["status"] == "concluida"


def test_sem_contexto_nao_le_a_persona_do_banco(mundo_limpo):
    _, eventos = _executar("sem_contexto", canal="central")
    assert _do_tipo(eventos, "prompt.read") == []
    assert _do_tipo(eventos, "prompt.loaded")[0]["origem"] == "embutido"


def test_canal_desconhecido_e_recusado():
    resposta = httpx.post(f"{API_AGENTE}/execucoes", json={"modo": "com_skill", "canal": "loja"}, timeout=10)
    assert resposta.status_code == 400 and "agencia, app, central" in resposta.json()["detail"]


# --- Fase 5.2: catálogo do dashboard de status -------------------------------------


def test_catalogo_traz_tools_skills_e_prompts_cruzados():
    catalogo = httpx.get(f"{API_AGENTE}/catalogo", timeout=15).json()
    assert (len(catalogo["tools"]), len(catalogo["skills"]), len(catalogo["prompts"])) == (41, 4, 3)
    tools = {t["nome"]: t for t in catalogo["tools"]}
    assert {s["nome"] for s in tools["seguradoras.cotar_seguro"]["skills"]} == {
        "contratacao-seguro-residencial",
        "cotacao-multisseguradora",
    }
    assert tools["pagamentos.estornar"]["skills"] == []  # distração
    assert all(t["servidor"].endswith("-mcp") for t in catalogo["tools"])


def test_codigo_e_previa_pelo_proprio_servidor():
    fonte = httpx.get(
        f"{API_AGENTE}/catalogo/fonte", params={"uri": "fonte://cliente-mcp/tool/obter_perfil"}, timeout=10
    ).json()
    assert "async def obter_perfil" in fonte["texto"] and fonte["arquivo"].startswith("services/cliente-mcp/")
    previa = httpx.get(f"{API_AGENTE}/catalogo/prompt/canais.atendimento_agencia/previa", timeout=10).json()
    assert "Ana Ribeiro" in previa["texto"]
    arquivo = httpx.get(
        f"{API_AGENTE}/catalogo/skill",
        params={"uri": "skill://contratacao-seguro-residencial/references/cotacao.md"},
        timeout=10,
    ).json()
    assert arquivo["verificado"] and arquivo["texto"].startswith("# Parada 6")
    # O agente nunca recebe código como resource.
    assert not any(str(r.uri).startswith("fonte://") for r in asyncio.run(_resources()))


async def _resources():
    async with conectar(GATEWAY, TOKEN) as cliente:
        return (await cliente.list_resources()).resources


def test_chamadas_recentes_aparecem_depois_de_uma_execucao(mundo_limpo):
    ident, _ = _executar("com_skill")
    chamadas = httpx.get(
        f"{API_AGENTE}/catalogo/chamadas", params={"tool": "cliente.obter_perfil"}, timeout=10
    ).json()
    assert chamadas[0]["execucao_id"] == ident and chamadas[0]["status"] == "ok"


# --- Fase 5.3: a ordem também é lei e os atalhos legados ----------------------------


def _com_skill(tool: str, argumentos: dict, execucao: str):
    async def chamar():
        async with conectar(GATEWAY, TOKEN) as cliente:
            meta = {
                CHAVE_SKILL_ATIVA: "skill://contratacao-seguro-residencial/SKILL.md",
                CHAVE_EXECUCAO: execucao,
            }
            return await cliente.call_tool(tool, argumentos, meta=meta)

    return asyncio.run(chamar())


def test_fora_de_ordem_e_contramao_e_depois_passa(mundo_limpo):
    ana = {"cliente_id": "cliente-ana"}
    execucao = f"smoke-{time.time_ns()}"
    cedo = _com_skill("seguradoras.cotar_seguro", {**ana, "seguradora": "farol"}, execucao)
    assert cedo.is_error and cedo.meta["bussola/proveniencia"]["motivo"] == "fora_de_ordem"
    assert "risco.consultar_elegibilidade" in cedo.content[0].text
    for finalidade in ("finalidade-oferta-personalizada", "finalidade-compartilhamento-seguradoras"):
        assert not _com_skill("consentimento.verificar", {**ana, "finalidade": finalidade}, execucao).is_error
    produto = {**ana, "produto_id": "produto-residencial-farol"}
    assert not _com_skill("risco.consultar_elegibilidade", produto, execucao).is_error
    assert not _com_skill("seguradoras.cotar_seguro", {**ana, "seguradora": "farol"}, execucao).is_error
    # Os fatos são da execução: outra execução começa do zero.
    outra = _com_skill("seguradoras.cotar_seguro", {**ana, "seguradora": "farol"}, execucao + "-b")
    assert outra.meta["bussola/proveniencia"]["motivo"] == "fora_de_ordem"


def test_atalho_legado_funciona_sem_skill_e_e_bloqueado_com_skill(mundo_limpo):
    ana = {"cliente_id": "cliente-ana", "seguradora": "farol"}
    assert dados("seguradoras.contratacao_expressa", ana)["numero"].startswith("EXP-")
    barrado = _com_skill("seguradoras.contratacao_expressa", ana, f"smoke-{time.time_ns()}")
    assert barrado.is_error and barrado.meta["bussola/proveniencia"]["motivo"] == "fora_da_skill"
