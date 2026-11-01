from datetime import UTC, date, datetime, timedelta

import pytest
from fakeredis import FakeAsyncRedis
from fastapi.testclient import TestClient

from bussola_comum.estado_vivo import EstadoVivo
from simulator.incidentes import catalogo, efeitos_concretos
from simulator.main import Config, criar_app
from simulator.mundo import Mundo

pytestmark = pytest.mark.anyio
METAFORAS_DA_SPEC = {
    "Rua interditada",
    "Congestionamento",
    "Contramão",
    "Desvio por obra",
    "Pedágio",
    "Ponte interditada",
}


class GrafoFalso:
    def __init__(self) -> None:
        self.aplicados: list[dict] = []
        self.resets = 0

    async def aplicar(self, efeitos: list[dict]) -> None:
        self.aplicados.extend(efeitos)

    async def reset(self) -> None:
        self.resets += 1
        self.aplicados.clear()


@pytest.fixture
def mundo() -> Mundo:
    return Mundo(EstadoVivo(FakeAsyncRedis(decode_responses=True)), GrafoFalso())


def test_catalogo_cobre_os_seis_incidentes_da_spec():
    assert {i.metafora for i in catalogo().values()} == METAFORAS_DA_SPEC


def test_datas_relativas_viram_datas_reais():
    [efeito] = efeitos_concretos(catalogo()["consentimento-ana-expirado"], hoje=date(2026, 11, 1))
    assert efeito["estado"]["vigencia_fim"] == "2026-10-31"


async def test_aplicar_escreve_no_grafo_e_no_estado_vivo(mundo):
    await mundo.aplicar("cotacao-ancora-fora")
    assert (await mundo.estado.efeito("api-cotacao-ancora"))["estado"]["status"] == "fora"
    assert mundo.grafo.aplicados[0]["entidade"] == "api-cotacao-ancora"
    assert await mundo.ativos() == ["cotacao-ancora-fora"]


async def test_remover_volta_ao_base_e_reaplica_os_outros(mundo):
    await mundo.aplicar("cotacao-ancora-fora")
    await mundo.aplicar("emissao-lenta")
    await mundo.remover("cotacao-ancora-fora")
    assert await mundo.estado.efeito("api-cotacao-ancora") == {}
    assert (await mundo.estado.efeito("api-emissao-ancora"))["estado"]["status"] == "degradado"
    assert mundo.grafo.resets == 1
    assert {e["entidade"] for e in mundo.grafo.aplicados} == {"api-emissao-ancora", "api-emissao-farol"}


async def test_dois_incidentes_na_mesma_entidade_se_somam(mundo):
    await mundo.aplicar("alcada-ana-excedida")
    await mundo.aplicar("proveniencia-fraca-ana")
    efeito = await mundo.estado.efeito("imovel-ana")
    assert efeito["atributos"]["colecao_arte_declarada"] == 1020000
    assert efeito["proveniencia"]["confianca"] == "baixa"


async def test_reset_limpa_registros_de_dominio(mundo):
    await mundo.estado.salvar("cotacao", "c-1", {"cotacao_id": "c-1"})
    await mundo.aplicar("cotacao-ancora-fora")
    await mundo.reset()
    assert await mundo.estado.listar("cotacao") == []
    assert await mundo.ativos() == []


async def test_pedagio_aprovado_pelo_apresentador(mundo):
    await mundo.estado.salvar(
        "aprovacao", "t-1", {"ticket_id": "t-1", "status": "pendente", "criado_em": _ha(2)}
    )
    ticket = await mundo.decidir("t-1", aprovar=True)
    assert ticket["status"] == "aprovada" and ticket["decidido_por"] == "apresentador"


async def test_sem_acao_em_30s_a_especialista_aprova(mundo):
    await mundo.estado.salvar(
        "aprovacao", "t-1", {"ticket_id": "t-1", "status": "pendente", "criado_em": _ha(31)}
    )
    await mundo.estado.salvar(
        "aprovacao", "t-2", {"ticket_id": "t-2", "status": "pendente", "criado_em": _ha(5)}
    )
    await mundo.tique()
    assert (await mundo.estado.obter("aprovacao", "t-1"))["decidido_por"] == "especialista-marina"
    assert (await mundo.estado.obter("aprovacao", "t-2"))["status"] == "pendente"


async def test_cliente_confirma_renovacao_no_app(mundo):
    await mundo.aplicar("consentimento-ana-expirado")
    await mundo.estado.salvar(
        "renovacao",
        "r-1",
        {
            "pedido_id": "r-1",
            "consentimento_id": "consentimento-ana-oferta",
            "status": "aguardando_cliente",
            "criado_em": _ha(6),
        },
    )
    await mundo.tique()
    efeito = await mundo.estado.efeito("consentimento-ana-oferta")
    assert efeito["estado"]["status"] == "ok"
    assert efeito["estado"]["vigencia_fim"] > date.today().isoformat()
    assert await mundo.ativos() == []


def test_api_http(mundo):
    async def ok() -> bool:
        return True

    app = criar_app(Config(), checagens={"bus": ok}, mundo=mundo, passar_o_tempo=False)
    with TestClient(app) as http:
        assert http.get("/saude").status_code == 200
        assert len(http.get("/incidentes").json()) == 6
        assert http.post("/incidentes/cotacao-ancora-fora/aplicar").json()["ativo"] is True
        assert http.post("/incidentes/nao-existe/aplicar").status_code == 404
        assert http.post("/aprovacoes/t-x/talvez").status_code == 400


def _ha(segundos: int) -> str:
    return (datetime.now(UTC) - timedelta(seconds=segundos)).isoformat(timespec="seconds")
