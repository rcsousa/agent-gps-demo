from pathlib import Path

from fastapi.testclient import TestClient

from mcp_gateway.main import Config, criar_app
from mcp_gateway.upstreams import carregar_upstreams

TOKEN = "token-de-teste"


async def _ok() -> bool:
    return True


def _cliente(tmp_path: Path) -> TestClient:
    arquivo = tmp_path / "upstreams.yaml"
    # Porta 9 (discard): ninguém escuta, então o upstream aparece como fora.
    arquivo.write_text(
        "servidores:\n  - nome: risco-mcp\n    prefixo: risco\n    url: http://127.0.0.1:9\n",
        encoding="utf-8",
    )
    config = Config(gateway_token=TOKEN, upstreams_arquivo=arquivo)
    return TestClient(criar_app(config, checagens={"bus": _ok}))


def test_saude_responde_ok(tmp_path):
    resposta = _cliente(tmp_path).get("/saude")
    assert resposta.status_code == 200
    assert resposta.json()["servico"] == "mcp-gateway"


def test_saude_servicos_exige_token(tmp_path):
    assert _cliente(tmp_path).get("/saude/servicos").status_code == 401


def test_saude_servicos_marca_upstream_fora(tmp_path):
    resposta = _cliente(tmp_path).get("/saude/servicos", headers={"Authorization": f"Bearer {TOKEN}"})
    assert resposta.status_code == 200
    [servico] = resposta.json()["servicos"]
    assert servico["nome"] == "risco-mcp"
    assert servico["status"] == "fora"


def test_ping_servidor_desconhecido(tmp_path):
    resposta = _cliente(tmp_path).post("/ping/inexistente", headers={"Authorization": f"Bearer {TOKEN}"})
    assert resposta.status_code == 404


def test_config_versionada_lista_os_oito_servidores_mcp():
    nomes = [u.nome for u in carregar_upstreams(Config().upstreams_arquivo)]
    assert len(nomes) == 8
    assert "skills-mcp" in nomes and "contexto-mcp" in nomes
