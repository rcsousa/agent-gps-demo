import pytest
from fakeredis import FakeAsyncRedis
from mcp.client.client import Client

from bussola_comum.estado_vivo import EstadoVivo
from risco_mcp.servidor import criar_servidor

pytestmark = pytest.mark.anyio


@pytest.fixture
def estado() -> EstadoVivo:
    return EstadoVivo(FakeAsyncRedis(decode_responses=True))


async def chamar(estado, tool, argumentos):
    async with Client(criar_servidor(estado, checagens={})) as cliente:
        return (await cliente.call_tool(tool, argumentos)).structured_content


async def test_ana_elegivel_ao_farol(estado):
    corpo = await chamar(
        estado,
        "consultar_elegibilidade",
        {"cliente_id": "cliente-ana", "produto_id": "produto-residencial-farol"},
    )
    assert corpo["elegivel"] is True
    assert corpo["falhas"] == [] and corpo["pendencias"] == []


async def test_carla_em_area_de_risco_precisa_de_vistoria(estado):
    corpo = await chamar(
        estado,
        "consultar_elegibilidade",
        {"cliente_id": "cliente-carla", "produto_id": "produto-residencial-farol"},
    )
    assert corpo["elegivel"] is False
    assert corpo["pendencias"] == ["regra-vistoria-area-risco"]


async def test_desvio_por_obra_na_zona_sul(estado):
    await estado.gravar_efeito(
        "area-sp-zona-sul", {"atributos": {"nivel": "alto", "fatores": ["alagamento"]}}
    )
    corpo = await chamar(
        estado,
        "consultar_elegibilidade",
        {"cliente_id": "cliente-ana", "produto_id": "produto-residencial-ancora"},
    )
    assert corpo["pendencias"] == ["regra-vistoria-area-risco"]


async def test_diego_acima_do_valor_maximo_da_horizonte(estado):
    corpo = await chamar(
        estado,
        "consultar_elegibilidade",
        {"cliente_id": "cliente-diego", "produto_id": "produto-residencial-horizonte"},
    )
    assert "regra-valor-maximo-imovel" in corpo["falhas"]


async def test_alcada_automatica_para_a_ana(estado):
    corpo = await chamar(estado, "verificar_alcada", {"premio_anual": 320, "importancia_segurada": 780000})
    assert corpo["exige_aprovacao_humana"] is False
    assert corpo["alcada"]["alcada_id"] == "alcada-automatica"


async def test_pedagio_acima_de_1_5_milhao(estado):
    corpo = await chamar(estado, "verificar_alcada", {"premio_anual": 715, "importancia_segurada": 1800000})
    assert corpo["exige_aprovacao_humana"] is True
    assert corpo["alcada"]["alcada_id"] == "alcada-especialista"


async def test_adequacao_da_ana(estado):
    corpo = await chamar(
        estado,
        "avaliar_adequacao",
        {
            "cliente_id": "cliente-ana",
            "produto_id": "produto-residencial-farol",
            "necessidade": "seguro residencial para meu apartamento",
            "premio_anual": 310,
        },
    )
    assert corpo["adequado"] is True


async def test_agendar_vistoria(estado):
    corpo = await chamar(estado, "agendar_vistoria", {"imovel_id": "imovel-carla"})
    assert corpo["status"] == "agendada" and corpo["prazo_dias"] == 3
