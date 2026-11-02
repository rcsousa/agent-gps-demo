"""Custo por execução e o modelo escolhido no painel."""

import pytest
from fakeredis import FakeAsyncRedis
from fastapi.testclient import TestClient
from mcp.client.client import Client
from test_motor import PublicadorFalso, _gateway

from agent.config import Config
from agent.custos import custo, precos_por_milhao
from agent.execucao import Motor
from agent.llm.base import Passo, Uso
from agent.main import criar_app

pytestmark = pytest.mark.anyio

PRECOS = {
    "claude-opus-5-5": {"entrada": 0.000004, "saida": 0.00002},
    "claude-haiku-5-5": {"entrada": 0.0000001, "saida": 0.0000005},
}


def _config(**campos) -> Config:
    base = {
        "llm_provider": "anthropic",
        "anthropic_model": "claude-haiku-5-5",
        "anthropic_modelos": "claude-opus-5-5",
        "llm_precos": PRECOS,
        "cache_leitura_fator": 0.1,
        "cache_escrita_fator": 1.25,
    }
    return Config(**{**base, **campos})


def test_custo_com_cache_e_sem_cache():
    tokens = {"entrada": 1_000, "cache_leitura": 100_000, "cache_escrita": 10_000, "saida": 5_000}
    c = custo(_config(), "claude-opus-5-5", tokens)
    assert c["entrada"] == pytest.approx(0.004)
    assert c["cache_leitura"] == pytest.approx(100_000 * 0.000004 * 0.1)
    assert c["cache_escrita"] == pytest.approx(10_000 * 0.000004 * 1.25)
    assert c["saida"] == pytest.approx(0.1)
    assert c["total"] == pytest.approx(0.004 + 0.04 + 0.05 + 0.1)
    assert c["sem_cache"] == pytest.approx(111_000 * 0.000004 + 0.1)
    assert custo(_config(), "modelo-sem-preco", tokens) is None


def test_preco_por_milhao_para_o_painel():
    assert precos_por_milhao(_config(), "claude-haiku-5-5") == {"entrada": 0.1, "saida": 0.5}
    assert precos_por_milhao(_config(), "outro") is None


@pytest.fixture
def api():
    config = _config()
    redis = FakeAsyncRedis(decode_responses=True)
    motor = Motor(config, redis, None, lambda: None)

    async def ok() -> bool:
        return True

    with TestClient(criar_app(config, checagens={"bus": ok}, motor=motor, redis=redis)) as cliente:
        yield cliente


def test_modelo_padrao_e_o_haiku_e_o_painel_troca(api):
    inicial = api.get("/api/llm/modelo").json()
    assert inicial["modelo"] == "claude-haiku-5-5" and inicial["padrao"] == "claude-haiku-5-5"
    assert [m["id"] for m in inicial["modelos"]] == ["claude-haiku-5-5", "claude-opus-5-5"]
    assert inicial["modelos"][1]["precos"] == {"entrada": 4.0, "saida": 20.0}

    trocado = api.put("/api/llm/modelo", json={"modelo": "claude-opus-5-5"})
    assert trocado.status_code == 200 and trocado.json()["modelo"] == "claude-opus-5-5"
    assert api.get("/api/status").json()["llm"]["modelo"] == "claude-opus-5-5"
    assert api.put("/api/llm/modelo", json={"modelo": "gpt-qualquer"}).status_code == 400


async def test_execucao_sem_modelo_usa_o_escolhido_e_registra_o_custo():
    class Sessao:
        provedor, modelo = "anthropic", "claude-opus-5-5"

        async def passo(self, tools):
            return Passo(texto="ok", fim=True, uso=Uso(entrada=10, saida=100, cache_leitura=1_000))

        def adicionar_resultados(self, resultados):
            pass

    config = _config()
    redis = FakeAsyncRedis(decode_responses=True)
    publicador = PublicadorFalso()
    servidor = _gateway([])
    pedidos = []

    def fabrica(provedor, modo, sistema, pedido, cfg, canal="app", modelo=""):
        pedidos.append(modelo)
        return Sessao()

    motor = Motor(config, redis, publicador, lambda: Client(servidor), fabrica_sessao=fabrica)
    await motor.definir_modelo("claude-opus-5-5")
    execucao = await motor.iniciar("sem_contexto", "anthropic")
    await motor.aguardar(execucao.id)

    assert pedidos == ["claude-opus-5-5"]
    final = await motor.obter(execucao.id)
    esperado = 10 * 0.000004 + 1_000 * 0.000004 * 0.1 + 100 * 0.00002
    assert final["metricas"]["custo_usd"]["total"] == pytest.approx(esperado)
    assert publicador.eventos[-1][1]["metricas"]["custo_usd"]["total"] == pytest.approx(esperado)
