"""Rotas internas usadas pelo simulador para mudar o estado vivo do grafo."""

import asyncio

import pytest
from neo4j import GraphDatabase
from starlette.testclient import TestClient

from bussola_comum.mcp_servidor import criar_app
from contexto_mcp.config import Config
from contexto_mcp.grafo import EntidadeNaoEncontrada, RepositorioGrafo
from contexto_mcp.layout import carregar_layout
from contexto_mcp.ontologia import carregar_ontologia
from contexto_mcp.seed import aplicar_seed
from contexto_mcp.servidor import criar_servidor

TOKEN = "token-do-simulador"


async def _ok() -> bool:
    return True


def _http(token: str) -> TestClient:
    return TestClient(criar_app(criar_servidor({"graph": _ok}, Config(simulador_token=token))))


def test_rotas_internas_desligadas_sem_token_configurado():
    with _http("") as http:
        assert http.post("/interno/estado", json={"efeitos": []}).status_code == 503


def test_rotas_internas_exigem_o_token_do_simulador():
    with _http(TOKEN) as http:
        assert http.post("/interno/estado", json={"efeitos": []}).status_code == 401
        assert http.post("/interno/reset", headers={"Authorization": "Bearer errado"}).status_code == 401


def test_rotas_internas_nao_viram_tools():
    async def listar():
        from mcp.client.client import Client

        async with Client(criar_servidor({"graph": _ok})) as cliente:
            return {t.name for t in (await cliente.list_tools()).tools}

    assert not any("interno" in nome or "reset" in nome for nome in asyncio.run(listar()))


# --- Integração com o Neo4j ---------------------------------------------------


@pytest.fixture
def repo():
    config = Config()
    try:
        with GraphDatabase.driver(
            config.neo4j_uri, auth=(config.neo4j_user, config.neo4j_password)
        ) as driver:
            driver.verify_connectivity()
            aplicar_seed(driver, carregar_ontologia(), carregar_layout())
            yield RepositorioGrafo(config.neo4j_uri, config.neo4j_user, config.neo4j_password)
            aplicar_seed(driver, carregar_ontologia(), carregar_layout())
    except Exception as erro:  # noqa: BLE001
        pytest.skip(f"Neo4j indisponível: {erro}")


TIPOS = set(carregar_ontologia().tipos_relacao)


@pytest.mark.grafo
def test_rua_interditada_bloqueia_a_rota_rapida(repo):
    async def cenario():
        await repo.aplicar_efeitos([{"entidade": "api-cotacao-ancora", "estado": {"status": "fora"}}], TIPOS)
        rotas = {r.id: r for r in (await repo.rotas("contratacao-seguro-residencial", None)).rotas}
        await repo.fechar()
        return rotas

    rotas = asyncio.run(cenario())
    assert rotas["rota-rapida"].estimativa.bloqueada is True
    assert rotas["rota-rapida"].alertas[0].entidade.id == "api-cotacao-ancora"
    assert rotas["rota-economica"].estimativa.bloqueada is True
    assert rotas["rota-assistida"].estimativa.bloqueada is False


@pytest.mark.grafo
def test_desvio_por_obra_adiciona_relacao_com_proveniencia(repo):
    async def cenario():
        await repo.aplicar_efeitos(
            [
                {
                    "entidade": "area-sp-zona-sul",
                    "atributos": {"nivel": "alto"},
                    "proveniencia": {"fonte": "Comitê de Riscos", "confianca": "alta"},
                    "relacoes_adicionar": [["area-sp-zona-sul", "EXIGE", "regra-vistoria-area-risco"]],
                }
            ],
            TIPOS,
        )
        regras = await repo.regras("area-sp-zona-sul")
        await repo.fechar()
        return regras

    regras = asyncio.run(cenario())
    assert "regra-vistoria-area-risco" in {r.regra.id for r in regras.regras}


@pytest.mark.grafo
def test_efeito_em_entidade_inexistente_nao_escreve_nada(repo):
    async def cenario():
        try:
            await repo.aplicar_efeitos([{"entidade": "nao-existe", "estado": {"status": "fora"}}], TIPOS)
        finally:
            await repo.fechar()

    with pytest.raises(EntidadeNaoEncontrada):
        asyncio.run(cenario())


@pytest.mark.grafo
def test_relacao_fora_do_esquema_e_recusada(repo):
    async def cenario():
        try:
            await repo.aplicar_efeitos(
                [
                    {
                        "entidade": "area-sp-zona-sul",
                        "relacoes_adicionar": [["area-sp-zona-sul", "INVENTADA", "norma-cdc"]],
                    }
                ],
                TIPOS,
            )
        finally:
            await repo.fechar()

    with pytest.raises(ValueError, match="fora do esquema"):
        asyncio.run(cenario())
