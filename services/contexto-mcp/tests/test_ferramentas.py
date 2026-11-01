"""Integração: seed no Neo4j e tools chamadas pelo protocolo MCP.

Precisa do grafo no ar (docker compose run --rm contexto-mcp pytest).
Sem grafo, os testes são pulados. O seed recoloca o grafo no estado-base,
o mesmo de toda subida da demo.
"""

import asyncio
import json

import pytest
from mcp.client.client import Client
from neo4j import GraphDatabase

from contexto_mcp.layout import carregar_layout
from contexto_mcp.ontologia import carregar_ontologia
from contexto_mcp.seed import aplicar_seed
from contexto_mcp.servidor import Config, criar_servidor

pytestmark = pytest.mark.grafo


async def _ok() -> bool:
    return True


@pytest.fixture(scope="module", autouse=True)
def grafo_semeado():
    config = Config()
    try:
        with GraphDatabase.driver(
            config.neo4j_uri, auth=(config.neo4j_user, config.neo4j_password)
        ) as driver:
            driver.verify_connectivity()
            yield aplicar_seed(driver, carregar_ontologia(), carregar_layout())
    except Exception as erro:  # noqa: BLE001
        pytest.skip(f"Neo4j indisponível: {erro}")


def _chamar(tool: str, argumentos: dict | None = None):
    async def chamar():
        async with Client(criar_servidor({"graph": _ok})) as cliente:
            return await cliente.call_tool(tool, argumentos or {})

    return asyncio.run(chamar())


def test_seed_grava_toda_a_ontologia(grafo_semeado):
    nos, arestas = grafo_semeado
    ontologia = carregar_ontologia()
    assert nos == len(ontologia.entidades)
    assert arestas == len(ontologia.relacoes)


def test_consultar_entidade_da_ana():
    resultado = _chamar("consultar_entidade", {"id": "cliente-ana"})
    assert not resultado.is_error
    corpo = resultado.structured_content
    assert corpo["entidade"]["nome"] == "Ana Ribeiro"
    assert corpo["entidade"]["proveniencia"]["fonte"] == "CRM Bússola"
    vizinhos = {r["entidade"]["id"] for r in corpo["relacoes"]}
    assert {"imovel-ana", "consentimento-ana-oferta", "contratado-ana-auto"} <= vizinhos


def test_entidade_inexistente_vira_erro_de_tool():
    resultado = _chamar("consultar_entidade", {"id": "nao-existe"})
    assert resultado.is_error
    assert "Não existe entidade com id 'nao-existe'" in resultado.content[0].text


def test_buscar_seguradoras():
    corpo = _chamar("buscar_entidades", {"tipo": "Seguradora"}).structured_content
    assert corpo["total"] == 3


def test_consultar_regras_do_produto_com_proveniencia():
    corpo = _chamar("consultar_regras", {"id": "produto-residencial-farol"}).structured_content
    regras = {r["regra"]["id"]: r for r in corpo["regras"]}
    assert regras["regra-imovel-residencial"]["distancia"] == 1
    assert regras["alcada-especialista"]["caminho"] == ["SUJEITA_A", "EXIGE"]
    assert all(r["regra"]["proveniencia"]["fonte"] for r in corpo["regras"])


def test_consultar_estado_das_apis_de_cotacao():
    corpo = _chamar("consultar_estado", {"tipo": "ApiCotacao"}).structured_content
    assert {i["entidade"]["id"] for i in corpo["itens"]} == {
        "api-cotacao-ancora",
        "api-cotacao-farol",
        "api-cotacao-horizonte",
    }
    assert all(i["estado"]["status"] == "ok" for i in corpo["itens"])


def test_consultar_proveniencia_de_relacao():
    corpo = _chamar(
        "consultar_proveniencia", {"id": "cliente-elisa", "relacionado_a": "imovel-elisa"}
    ).structured_content
    assert corpo["proveniencia"]["confianca"] == "baixa"
    assert corpo["relacoes"][0]["tipo"] == "POSSUI"


def test_consultar_rota_com_estimativas():
    corpo = _chamar("consultar_rota").structured_content
    rotas = {r["id"]: r for r in corpo["rotas"]}
    assert set(rotas) == {"rota-rapida", "rota-economica", "rota-assistida"}
    rapida, assistida = rotas["rota-rapida"], rotas["rota-assistida"]
    assert [p["numero"] for p in rapida["paradas"]] == list(range(1, 10))
    assert rapida["estimativa"]["tempo_s"] < rotas["rota-economica"]["estimativa"]["tempo_s"]
    assert assistida["estimativa"]["tempo_s"] > rotas["rota-economica"]["estimativa"]["tempo_s"]
    assert not rapida["estimativa"]["bloqueada"] and rapida["alertas"] == []


def test_recurso_do_mapa():
    async def ler():
        async with Client(criar_servidor({"graph": _ok})) as cliente:
            return await cliente.read_resource("contexto://mapa")

    mapa = json.loads(asyncio.run(ler()).contents[0].text)
    assert len(mapa["bairros"]) == 6
    assert len(mapa["nos"]) == len(carregar_ontologia().entidades)
    assert all(isinstance(n["x"], int) and isinstance(n["y"], int) for n in mapa["nos"])
    assert mapa["rio"] and mapa["avenidas"]
