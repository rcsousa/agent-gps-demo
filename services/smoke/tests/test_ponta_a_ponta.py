"""Checagem ponta a ponta da Fase 1, pela rede interna do compose.

O smoke é ferramenta de teste: ele pode conhecer todos os serviços.
O agente, não.
"""

import asyncio
import json
import os

import httpx
import pytest
from mcp.client.client import Client

SERVICOS_PYTHON = [
    "agent",
    "mcp-gateway",
    "skills-mcp",
    "contexto-mcp",
    "cliente-mcp",
    "consentimento-mcp",
    "risco-mcp",
    "seguradoras-mcp",
    "pagamentos-mcp",
    "atendimento-mcp",
    "simulator",
]
SERVIDORES_MCP = [s for s in SERVICOS_PYTHON if s.endswith("-mcp")]
TOKEN = {"Authorization": f"Bearer {os.environ['GATEWAY_TOKEN']}"}


@pytest.mark.parametrize("servico", SERVICOS_PYTHON)
def test_saude_de_cada_servico(servico):
    resposta = httpx.get(f"http://{servico}:8000/saude", timeout=5)
    assert resposta.status_code == 200, resposta.text
    assert resposta.json()["status"] == "ok"


def test_contexto_mcp_enxerga_o_grafo():
    corpo = httpx.get("http://contexto-mcp:8000/saude", timeout=5).json()
    assert corpo["dependencias"]["graph"] == "ok"


@pytest.mark.parametrize("servidor", SERVIDORES_MCP)
def test_ping_mcp_via_gateway(servidor):
    resposta = httpx.post(f"http://mcp-gateway:8000/ping/{servidor}", headers=TOKEN, timeout=10)
    assert resposta.status_code == 200, resposta.text
    assert resposta.json()["resposta"] == f"pong de {servidor}"


def test_gateway_recusa_chamada_sem_token():
    assert httpx.get("http://mcp-gateway:8000/saude/servicos", timeout=5).status_code == 401


def test_status_pelo_caminho_web_agent_gateway():
    corpo = httpx.get("http://web/api/status", timeout=10).json()
    assert corpo["gateway"] == "ok"
    assert corpo["barramento"] == "ok"
    assert sorted(s["nome"] for s in corpo["servicos"]) == sorted(SERVIDORES_MCP)
    assert all(s["status"] == "ok" for s in corpo["servicos"])


def test_web_serve_a_aplicacao():
    resposta = httpx.get("http://web/", timeout=5)
    assert resposta.status_code == 200
    assert '<div id="raiz">' in resposta.text


def test_bastidores_servidos_pelo_web():
    resposta = httpx.get("http://web/bastidores/", timeout=5, follow_redirects=True)
    assert resposta.status_code == 200
    assert "Bastidores" in resposta.text


# --- Fase 2: camada de contexto ------------------------------------------------


def _contexto(tool: str, argumentos: dict | None = None):
    async def chamar():
        async with Client("http://contexto-mcp:8000/mcp", read_timeout_seconds=15) as cliente:
            if tool.startswith("contexto://"):
                return await cliente.read_resource(tool)
            return await cliente.call_tool(tool, argumentos or {})

    return asyncio.run(chamar())


def test_grafo_semeado_com_a_ana():
    resultado = _contexto("consultar_entidade", {"id": "cliente-ana"})
    assert not resultado.is_error
    assert resultado.structured_content["entidade"]["nome"] == "Ana Ribeiro"


def test_tres_rotas_com_estimativa():
    rotas = _contexto("consultar_rota").structured_content["rotas"]
    assert {r["id"] for r in rotas} == {"rota-rapida", "rota-economica", "rota-assistida"}
    assert all(r["estimativa"]["tempo_texto"].startswith("~") for r in rotas)


def test_mapa_com_todos_os_nos_posicionados():
    mapa = json.loads(_contexto("contexto://mapa").contents[0].text)
    assert 150 <= len(mapa["nos"]) <= 300
    assert all(n["x"] is not None and n["y"] is not None for n in mapa["nos"])
