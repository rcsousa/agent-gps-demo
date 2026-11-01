import pytest
from fakeredis import FakeAsyncRedis
from mcp.client.client import Client

from atendimento_mcp.servidor import criar_servidor
from bussola_comum.estado_vivo import EstadoVivo

pytestmark = pytest.mark.anyio


@pytest.fixture
def estado() -> EstadoVivo:
    return EstadoVivo(FakeAsyncRedis(decode_responses=True))


async def test_ticket_de_aprovacao_comeca_pendente(estado):
    await estado.salvar(
        "proposta",
        "p-1",
        {
            "proposta_id": "p-1",
            "cliente_id": "cliente-ana",
            "premio_anual": 715,
            "importancia_segurada": 1800000,
        },
    )
    async with Client(criar_servidor(estado, checagens={})) as cliente:
        ticket = (
            await cliente.call_tool(
                "solicitar_aprovacao", {"proposta_id": "p-1", "motivo": "acima da alçada"}
            )
        ).structured_content
        consulta = (
            await cliente.call_tool("consultar_aprovacao", {"ticket_id": ticket["ticket_id"]})
        ).structured_content
    assert ticket["status"] == "pendente" and ticket["fila"] == "fila-aprovacao-alcada"
    assert consulta["status"] == "pendente"


async def test_proposta_inexistente(estado):
    async with Client(criar_servidor(estado, checagens={})) as cliente:
        resultado = await cliente.call_tool("solicitar_aprovacao", {"proposta_id": "nada", "motivo": "x"})
    assert resultado.is_error
