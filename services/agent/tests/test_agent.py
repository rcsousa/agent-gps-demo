import re
from pathlib import Path

from fastapi.testclient import TestClient

from agent.config import Config
from agent.main import criar_app


async def _ok() -> bool:
    return True


def _cliente(**campos) -> TestClient:
    # Porta 9 (discard): o gateway não responde.
    config = Config(gateway_url="http://127.0.0.1:9", **campos)
    return TestClient(criar_app(config, checagens={"bus": _ok}))


def test_saude_responde_ok():
    resposta = _cliente().get("/saude")
    assert resposta.status_code == 200
    assert resposta.json()["servico"] == "agent"


def test_status_marca_gateway_fora_quando_nao_responde():
    corpo = _cliente().get("/api/status").json()
    assert corpo["gateway"] == "fora"
    assert corpo["barramento"] == "ok"
    assert corpo["servicos"] == []


def test_status_informa_provedor_de_llm():
    corpo = (
        _cliente(
            llm_provider="azure_openai",
            azure_openai_api_key="x",
            azure_openai_endpoint="https://exemplo.openai.azure.com",
            azure_openai_deployment="gpt",
        )
        .get("/api/status")
        .json()
    )
    assert corpo["llm"] == {"provedor": "azure_openai", "configurado": True}


def test_agente_nao_conhece_servidores_de_dominio():
    """O agente só fala com o gateway: nenhum nome de servidor de domínio no código."""
    codigo = "\n".join(p.read_text(encoding="utf-8") for p in Path("src").rglob("*.py"))
    proibidos = re.findall(r"\b[a-z]+-mcp\b|\bgraph:7687\b|\bsimulator\b", codigo)
    assert proibidos == []


class MotorFalso:
    def __init__(self, canais):
        self._canais, self.iniciadas = canais, []

    async def canais(self):
        if isinstance(self._canais, Exception):
            raise self._canais
        return self._canais

    async def iniciar(self, modo, provedor, pedido, canal):
        from agent.execucao import Execucao

        self.iniciadas.append(canal)
        return Execucao(id="e1", modo=modo, provedor=provedor or "roteiro", pedido="", canal=canal or "app")


def _api(motor) -> TestClient:
    return TestClient(criar_app(Config(), checagens={"bus": _ok}, motor=motor, redis=object()))


def test_canal_validado_contra_os_prompts_do_gateway():
    motor = MotorFalso(["agencia", "app", "central"])
    with _api(motor) as api:
        assert (
            api.post("/api/execucoes", json={"modo": "com_skill", "canal": "agencia"}).json()["canal"]
            == "agencia"
        )
        resposta = api.post("/api/execucoes", json={"modo": "com_skill", "canal": "loja"})
    assert resposta.status_code == 400 and "agencia, app, central" in resposta.json()["detail"]
    assert motor.iniciadas == ["agencia"]


def test_gateway_fora_nao_impede_a_execucao():
    motor = MotorFalso(ConnectionError("fora"))
    with _api(motor) as api:
        assert api.post("/api/execucoes", json={"modo": "com_skill", "canal": "agencia"}).status_code == 201
