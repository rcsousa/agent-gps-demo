from fastapi.testclient import TestClient

from simulator.main import Config, criar_app


async def _ok() -> bool:
    return True


async def _fora() -> bool:
    return False


def test_saude_ok_com_barramento():
    resposta = TestClient(criar_app(Config(), checagens={"bus": _ok})).get("/saude")
    assert resposta.status_code == 200
    assert resposta.json()["dependencias"] == {"bus": "ok"}


def test_saude_fora_sem_barramento():
    resposta = TestClient(criar_app(Config(), checagens={"bus": _fora})).get("/saude")
    assert resposta.status_code == 503
