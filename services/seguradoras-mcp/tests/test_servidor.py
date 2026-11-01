import time

import pytest
from fakeredis import FakeAsyncRedis
from mcp.client.client import Client

from bussola_comum.estado_vivo import EstadoVivo
from seguradoras_mcp.servidor import criar_servidor

pytestmark = pytest.mark.anyio


@pytest.fixture
def estado() -> EstadoVivo:
    return EstadoVivo(FakeAsyncRedis(decode_responses=True))


async def chamar(cliente, tool, argumentos):
    return await cliente.call_tool(tool, argumentos)


@pytest.mark.parametrize(
    ("seguradora", "premio"), [("ancora", 320), ("farol", 310), ("Horizonte Seguros", 280)]
)
async def test_precos_da_ana(estado, seguradora, premio):
    async with Client(criar_servidor(estado, checagens={})) as c:
        cotacao = (
            await chamar(c, "cotar_seguro", {"cliente_id": "cliente-ana", "seguradora": seguradora})
        ).structured_content
    assert round(cotacao["premio_anual"]) == premio
    assert cotacao["base_calculo"]["origem_valor"]["confianca"] == "alta"


async def test_rua_interditada(estado):
    await estado.gravar_efeito("api-cotacao-ancora", {"estado": {"status": "fora"}})
    async with Client(criar_servidor(estado, checagens={})) as c:
        resultado = await chamar(c, "cotar_seguro", {"cliente_id": "cliente-ana", "seguradora": "ancora"})
        farol = await chamar(c, "cotar_seguro", {"cliente_id": "cliente-ana", "seguradora": "farol"})
    assert resultado.is_error and "Âncora" in resultado.content[0].text
    assert not farol.is_error


async def test_congestionamento_atrasa_e_avisa(estado):
    await estado.gravar_efeito("api-cotacao-farol", {"estado": {"status": "degradado", "latencia_ms": 500}})
    async with Client(criar_servidor(estado, checagens={})) as c:
        inicio = time.perf_counter()
        cotacao = (
            await chamar(c, "cotar_seguro", {"cliente_id": "cliente-ana", "seguradora": "farol"})
        ).structured_content
    assert time.perf_counter() - inicio >= 0.5
    assert "lentidão" in cotacao["aviso"]


async def _ate_o_pagamento(c, estado, importancia_segurada=None):
    args = {"cliente_id": "cliente-ana", "seguradora": "farol"}
    if importancia_segurada:
        args["importancia_segurada"] = importancia_segurada
    cotacao = (await chamar(c, "cotar_seguro", args)).structured_content
    proposta = (await chamar(c, "gerar_proposta", {"cotacao_id": cotacao["cotacao_id"]})).structured_content
    await chamar(c, "registrar_aceite", {"proposta_id": proposta["proposta_id"]})
    await estado.salvar("pagamento", "pag-1", {"pagamento_id": "pag-1", "status": "aprovado"})
    return proposta


async def test_jornada_completa_ate_a_apolice(estado):
    async with Client(criar_servidor(estado, checagens={})) as c:
        proposta = await _ate_o_pagamento(c, estado)
        apolice = await chamar(
            c, "emitir_apolice", {"proposta_id": proposta["proposta_id"], "pagamento_id": "pag-1"}
        )
    assert proposta["exige_aprovacao_humana"] is False
    assert apolice.structured_content["status"] == "emitida"


async def test_emissao_sem_aceite_e_barrada(estado):
    async with Client(criar_servidor(estado, checagens={})) as c:
        cotacao = (
            await chamar(c, "cotar_seguro", {"cliente_id": "cliente-ana", "seguradora": "farol"})
        ).structured_content
        proposta = (
            await chamar(c, "gerar_proposta", {"cotacao_id": cotacao["cotacao_id"]})
        ).structured_content
        resultado = await chamar(
            c, "emitir_apolice", {"proposta_id": proposta["proposta_id"], "pagamento_id": "x"}
        )
    assert resultado.is_error and "aceita" in resultado.content[0].text


async def test_pedagio_exige_aprovacao(estado):
    async with Client(criar_servidor(estado, checagens={})) as c:
        proposta = await _ate_o_pagamento(c, estado, importancia_segurada=1800000)
        sem = await chamar(
            c, "emitir_apolice", {"proposta_id": proposta["proposta_id"], "pagamento_id": "pag-1"}
        )
        await estado.salvar(
            "aprovacao",
            "t-1",
            {"ticket_id": "t-1", "proposta_id": proposta["proposta_id"], "status": "aprovada"},
        )
        com = await chamar(
            c,
            "emitir_apolice",
            {"proposta_id": proposta["proposta_id"], "pagamento_id": "pag-1", "aprovacao_id": "t-1"},
        )
    assert proposta["exige_aprovacao_humana"] is True
    assert sem.is_error and "alçada" in sem.content[0].text
    assert not com.is_error


async def test_area_de_risco_exige_vistoria_para_emitir(estado):
    await estado.gravar_efeito("area-sp-zona-sul", {"atributos": {"nivel": "alto"}})
    async with Client(criar_servidor(estado, checagens={})) as c:
        proposta = await _ate_o_pagamento(c, estado)
        resultado = await chamar(
            c, "emitir_apolice", {"proposta_id": proposta["proposta_id"], "pagamento_id": "pag-1"}
        )
    assert resultado.is_error and "vistoria" in resultado.content[0].text


async def test_cotacao_com_laudo_herda_a_proveniencia_do_laudo(estado):
    async with Client(criar_servidor(estado, checagens={})) as c:
        pelo_laudo = await chamar(
            c, "cotar_seguro", {"cliente_id": "cliente-ana", "seguradora": "farol", "usar_laudo": True}
        )
        informado = await chamar(
            c,
            "cotar_seguro",
            {"cliente_id": "cliente-ana", "seguradora": "farol", "importancia_segurada": 780000},
        )
        os_dois = await chamar(
            c,
            "cotar_seguro",
            {
                "cliente_id": "cliente-ana",
                "seguradora": "farol",
                "importancia_segurada": 1,
                "usar_laudo": True,
            },
        )
        sem_laudo = await chamar(
            c, "cotar_seguro", {"cliente_id": "cliente-bruno", "seguradora": "farol", "usar_laudo": True}
        )

    base = pelo_laudo.structured_content["base_calculo"]
    assert pelo_laudo.structured_content["importancia_segurada"] == 780000
    assert base["origem_valor"]["confianca"] == "alta"
    assert base["origem_valor"]["fonte"] == "Laudo de avaliação (Engenharia Bússola)"
    # O mesmo valor, informado à mão, não prova a origem: confiança média.
    assert informado.structured_content["base_calculo"]["origem_valor"]["confianca"] == "media"
    assert os_dois.is_error and "não os dois" in os_dois.content[0].text
    assert sem_laudo.is_error and "Não há laudo" in sem_laudo.content[0].text
