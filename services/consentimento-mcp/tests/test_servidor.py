import pytest
from fakeredis import FakeAsyncRedis
from mcp.client.client import Client

from bussola_comum.estado_vivo import EstadoVivo
from consentimento_mcp.servidor import criar_servidor

pytestmark = pytest.mark.anyio
OFERTA = "finalidade-oferta-personalizada"


@pytest.fixture
def estado() -> EstadoVivo:
    return EstadoVivo(FakeAsyncRedis(decode_responses=True))


async def chamar(estado, tool, argumentos):
    async with Client(criar_servidor(estado, checagens={})) as cliente:
        return await cliente.call_tool(tool, argumentos)


async def test_consentimento_da_ana_vigente(estado):
    corpo = (
        await chamar(estado, "verificar", {"cliente_id": "cliente-ana", "finalidade": OFERTA})
    ).structured_content
    assert corpo["permitido"] is True
    assert corpo["base_legal"] == "base-consentimento"


async def test_consentimento_do_bruno_vencido(estado):
    corpo = (
        await chamar(estado, "verificar", {"cliente_id": "cliente-bruno", "finalidade": OFERTA})
    ).structured_content
    assert corpo["permitido"] is False
    assert "renovação" in corpo["motivo"]


async def test_contramao_quando_o_simulador_expira_o_consentimento(estado):
    await estado.gravar_efeito(
        "consentimento-ana-oferta", {"estado": {"status": "fora", "vigencia_fim": "2026-10-31"}}
    )
    corpo = (
        await chamar(estado, "verificar", {"cliente_id": "cliente-ana", "finalidade": OFERTA})
    ).structured_content
    assert corpo["permitido"] is False
    assert corpo["vigencia"]["fim"] == "2026-10-31"


async def test_cobranca_usa_execucao_de_contrato(estado):
    corpo = (
        await chamar(estado, "verificar", {"cliente_id": "cliente-ana", "finalidade": "finalidade-cobranca"})
    ).structured_content
    assert corpo["permitido"] is True
    assert corpo["base_legal"] == "base-execucao-contrato"


async def test_renovacao_fica_aguardando_a_cliente(estado):
    pedido = (
        await chamar(estado, "solicitar_renovacao", {"cliente_id": "cliente-ana", "finalidade": OFERTA})
    ).structured_content
    assert pedido["status"] == "aguardando_cliente"
    assert await estado.obter("renovacao", pedido["pedido_id"])


async def test_finalidade_desconhecida(estado):
    resultado = await chamar(estado, "verificar", {"cliente_id": "cliente-ana", "finalidade": "marketing"})
    assert resultado.is_error
