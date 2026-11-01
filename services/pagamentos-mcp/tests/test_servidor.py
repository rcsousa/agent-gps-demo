import pytest
from fakeredis import FakeAsyncRedis
from mcp.client.client import Client

from bussola_comum.estado_vivo import EstadoVivo
from pagamentos_mcp.servidor import criar_servidor

pytestmark = pytest.mark.anyio


@pytest.fixture
def estado() -> EstadoVivo:
    return EstadoVivo(FakeAsyncRedis(decode_responses=True))


async def chamar(estado, tool, argumentos):
    async with Client(criar_servidor(estado, checagens={})) as cliente:
        return await cliente.call_tool(tool, argumentos)


async def test_debito_em_conta_da_ana(estado):
    corpo = (
        await chamar(
            estado, "processar_pagamento", {"cliente_id": "cliente-ana", "valor": 309.97, "referencia": "p-1"}
        )
    ).structured_content
    assert corpo["status"] == "aprovado"
    assert await estado.obter("pagamento", corpo["pagamento_id"])


async def test_meio_nao_permitido(estado):
    resultado = await chamar(
        estado, "processar_pagamento", {"cliente_id": "cliente-helena", "valor": 100, "referencia": "p-1"}
    )
    assert resultado.is_error and "não permite" in resultado.content[0].text


async def test_gateway_de_pagamentos_fora(estado):
    await estado.gravar_efeito("sistema-gateway-pagamentos", {"estado": {"status": "fora"}})
    resultado = await chamar(
        estado, "processar_pagamento", {"cliente_id": "cliente-ana", "valor": 100, "referencia": "p-1"}
    )
    assert resultado.is_error
