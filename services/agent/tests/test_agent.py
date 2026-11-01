import re
from pathlib import Path

from fastapi.testclient import TestClient

from agent.main import Config, criar_app


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
    corpo = _cliente(llm_provider="azure_openai", azure_openai_api_key="x").get("/api/status").json()
    assert corpo["llm"] == {"provedor": "azure_openai", "configurado": True}


def test_agente_nao_conhece_servidores_de_dominio():
    """O agente só fala com o gateway: nenhum nome de servidor de domínio no código."""
    codigo = "\n".join(p.read_text(encoding="utf-8") for p in Path("src").rglob("*.py"))
    proibidos = re.findall(r"\b[a-z]+-mcp\b|\bgraph:7687\b|\bsimulator\b", codigo)
    assert proibidos == []
