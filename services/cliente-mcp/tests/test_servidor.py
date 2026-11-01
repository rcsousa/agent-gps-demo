import pytest
from fakeredis import FakeAsyncRedis
from mcp.client.client import Client
from starlette.testclient import TestClient

from bussola_comum.estado_vivo import EstadoVivo
from bussola_comum.mcp_servidor import criar_app
from cliente_mcp.servidor import criar_servidor

pytestmark = pytest.mark.anyio


@pytest.fixture
def estado() -> EstadoVivo:
    return EstadoVivo(FakeAsyncRedis(decode_responses=True))


async def chamar(estado, tool, argumentos):
    async with Client(criar_servidor(estado, checagens={})) as cliente:
        return await cliente.call_tool(tool, argumentos)


def test_saude():
    with TestClient(criar_app(criar_servidor(EstadoVivo(FakeAsyncRedis()), checagens={}))) as http:
        assert http.get("/saude").status_code == 200


async def test_tools_da_jornada_e_de_distracao(estado):
    async with Client(criar_servidor(estado, checagens={})) as cliente:
        nomes = {t.name for t in (await cliente.list_tools()).tools}
    assert {"obter_perfil", "obter_imovel", "consultar_laudo_avaliacao", "atualizar_endereco"} <= nomes


async def test_perfil_da_ana(estado):
    perfil = (await chamar(estado, "obter_perfil", {"cliente_id": "cliente-ana"})).structured_content
    assert perfil["nome"] == "Ana Ribeiro"
    assert perfil["idade"] == 38
    assert perfil["proveniencia"]["confianca"] == "alta"


async def test_imovel_com_importancia_segurada(estado):
    imovel = (await chamar(estado, "obter_imovel", {"cliente_id": "cliente-ana"})).structured_content
    assert imovel["id"] == "imovel-ana"
    assert imovel["importancia_segurada"] == 780000


async def test_cliente_inexistente(estado):
    resultado = await chamar(estado, "obter_perfil", {"cliente_id": "cliente-x"})
    assert resultado.is_error
    assert "não encontrado" in resultado.content[0].text


async def test_ponte_interditada_muda_a_proveniencia_mas_nao_o_laudo(estado):
    await estado.gravar_efeito(
        "imovel-ana",
        {
            "atributos": {"valor_estimado": 1250000},
            "proveniencia": {"fonte": "Planilha", "confianca": "baixa"},
        },
    )
    imovel = (await chamar(estado, "obter_imovel", {"cliente_id": "cliente-ana"})).structured_content
    laudo = (
        await chamar(estado, "consultar_laudo_avaliacao", {"imovel_id": "imovel-ana"})
    ).structured_content
    assert imovel["valor_estimado"] == 1250000 and imovel["proveniencia"]["confianca"] == "baixa"
    assert laudo["valor_avaliado"] == 780000 and laudo["proveniencia"]["confianca"] == "alta"


async def test_crm_fora_do_ar(estado):
    await estado.gravar_efeito("sistema-crm", {"estado": {"status": "fora"}})
    resultado = await chamar(estado, "obter_perfil", {"cliente_id": "cliente-ana"})
    assert resultado.is_error
    assert "fora do ar" in resultado.content[0].text


# --- Código-fonte para o dashboard (fábrica comum) ------------------------------------


async def test_fonte_da_tool_e_o_codigo_real_fora_do_catalogo(estado):
    import json

    from mcp.shared.exceptions import MCPError

    async with Client(criar_servidor(estado, checagens={})) as cliente:
        fonte = json.loads(
            (await cliente.read_resource("fonte://cliente-mcp/tool/obter_perfil")).contents[0].text
        )
        listados = [str(r.uri) for r in (await cliente.list_resources()).resources]
        with pytest.raises(MCPError):
            await cliente.read_resource("fonte://cliente-mcp/tool/nao_existe")
    assert fonte["arquivo"] == "services/cliente-mcp/src/cliente_mcp/servidor.py"
    assert fonte["linguagem"] == "python" and fonte["linha"] > 1
    assert "async def obter_perfil(cliente_id: str)" in fonte["texto"]
    assert not any(u.startswith("fonte://") for u in listados)  # o agente nunca recebe código


async def test_dossie_completo_traz_dados_alem_da_tarefa(estado):
    async with Client(criar_servidor(estado, checagens={})) as cliente:
        dossie = (
            await cliente.call_tool("obter_dossie_completo", {"cliente_id": "cliente-ana"})
        ).structured_content
    assert {"perfil", "imovel", "renda_mensal", "transacoes", "limite_credito", "produtos"} <= set(dossie)
    assert dossie["transacoes"] and dossie["renda_mensal"] > 0
