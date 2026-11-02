"""Regras do banco cumpridas (bussola_comum.regras) e a conferência no fim de cada execução."""

import pytest
from fakeredis import FakeAsyncRedis
from mcp.client.client import Client
from test_motor import SessaoFalsa, _gateway, _passo

from agent.config import Config
from agent.execucao import Motor
from agent.llm.base import Passo
from bussola_comum.eventos import PublicadorRedis
from bussola_comum.regras import caso_de, regras, resumo

pytestmark = pytest.mark.anyio


def _eventos(chamadas: list[tuple[str, str]], apolice: str | None = None, extras=()) -> list[dict]:
    eventos = [
        {"tipo": "tool.called", "dados": {"tool": t, "status": s, "argumentos": {}}} for t, s in chamadas
    ]
    eventos += list(extras)
    eventos.append({"tipo": "run.finished", "dados": {"apolice": apolice}})
    return eventos


CAMINHO_CERTO = [
    ("consentimento.verificar", "ok"),
    ("cliente.obter_imovel", "ok"),
    ("risco.avaliar_adequacao", "ok"),
    ("seguradoras.gerar_proposta", "ok"),
    ("seguradoras.emitir_apolice", "ok"),
]


def test_caminho_feliz_certo_cumpre_todas():
    r = regras("caminho-feliz", _eventos(CAMINHO_CERTO, "HOR-1"))
    assert all(r.values()) and resumo(r)["cumpridas"] == resumo(r)["total"] == 5


def test_imovel_antes_do_consentimento_e_atalho_legado_quebram_regras():
    errado = [
        CAMINHO_CERTO[1],
        CAMINHO_CERTO[0],
        *CAMINHO_CERTO[2:],
        ("seguradoras.contratacao_expressa", "ok"),
    ]
    r = regras("caminho-feliz", _eventos(errado, "ANC-1"))
    assert not r["consentimento antes do imóvel"] and not r["não usou atalho legado"]


def test_tentativa_barrada_nao_conta():
    barrada = [("cliente.obter_imovel", "erro"), *CAMINHO_CERTO]
    assert regras("caminho-feliz", _eventos(barrada, "HOR-1"))["consentimento antes do imóvel"]


def test_ancora_fora_exige_perceber_desviar_e_explicar():
    extras = [
        {"tipo": "incident.detected", "dados": {"metafora": "Rua interditada"}},
        {"tipo": "agent.message", "dados": {"texto": "A Âncora está fora do ar; segui com a Farol."}},
    ]
    r = regras("cotacao-ancora-fora", _eventos(CAMINHO_CERTO, "FAR-1", extras))
    assert r["percebeu a interdição"] and r["seguiu com outra seguradora"] and r["explicou a troca à cliente"]


def test_caso_vem_do_primeiro_incidente_conhecido():
    assert caso_de([]) == "caminho-feliz"
    assert caso_de(["tool-qualquer", "cotacao-ancora-fora"]) == "cotacao-ancora-fora"


async def test_run_finished_leva_as_regras_do_caso():
    redis = FakeAsyncRedis(decode_responses=True)
    sessao = SessaoFalsa(
        [_passo(("cliente.obter_perfil", {"cliente_id": "cliente-ana"})), Passo(texto="Pronto.", fim=True)]
    )
    motor = Motor(
        Config(max_passos=5),
        redis,
        PublicadorRedis(redis, "agent"),
        lambda: Client(_gateway([])),
        fabrica_sessao=lambda *a, **k: sessao,
    )
    execucao = await motor.iniciar("sem_skill", "falso", caso="cotacao-ancora-fora")
    await motor.aguardar(execucao.id)
    metricas = (await motor.obter(execucao.id))["metricas"]
    assert metricas["caso"] == "cotacao-ancora-fora"
    assert metricas["regras"]["total"] == 5  # 2 gerais e 3 do incidente
    assert metricas["regras"]["regras"]["não pediu o dossiê completo"] is True
    assert metricas["regras"]["regras"]["seguiu com outra seguradora"] is False
    # Os eventos da execução vêm do barramento, só os dela e em ordem.
    eventos = await motor.eventos_da_execucao(execucao.id, "0-0")
    assert eventos[0]["tipo"] == "run.started" and eventos[-1]["tipo"] == "run.finished"


async def test_incidente_aplicado_durante_a_viagem_define_o_caso():
    redis = FakeAsyncRedis(decode_responses=True)

    class SessaoComIncidente(SessaoFalsa):
        async def passo(self, tools):
            # O apresentador derruba a Âncora no meio da viagem (registro do simulador).
            await redis.xadd(
                "bussola:simulacao", {"acao": "aplicado", "dados": '{"incidente": "cotacao-ancora-fora"}'}
            )
            return await super().passo(tools)

    sessao = SessaoComIncidente([Passo(texto="Pronto.", fim=True)])
    motor = Motor(
        Config(max_passos=5),
        redis,
        PublicadorRedis(redis, "agent"),
        lambda: Client(_gateway([])),
        fabrica_sessao=lambda *a, **k: sessao,
    )
    execucao = await motor.iniciar("com_skill", "falso")
    await motor.aguardar(execucao.id)
    assert (await motor.obter(execucao.id))["metricas"]["caso"] == "cotacao-ancora-fora"
