"""Prompts por canal: arquivos versionados, servidos pela primitiva prompts do MCP."""

import asyncio
from pathlib import Path

import pytest
from mcp.client.client import Client
from starlette.testclient import TestClient

from bussola_comum.mcp_servidor import criar_app
from canais_mcp.servidor import NOME, PromptInvalido, carregar_prompt, carregar_prompts, criar_servidor

CANAIS_DA_ONTOLOGIA = {"canal-app", "canal-internet-banking", "canal-agencia", "canal-central"}


def _chamar(funcao):
    async def rodar():
        async with Client(criar_servidor()) as cliente:
            return await funcao(cliente)

    return asyncio.run(rodar())


def test_saude_responde_ok():
    with TestClient(criar_app(criar_servidor())) as cliente:
        resposta = cliente.get("/saude")
    assert resposta.json()["servico"] == NOME


def test_tres_canais_com_canal_da_ontologia():
    prompts = carregar_prompts()
    assert set(prompts) == {"atendimento_app", "atendimento_agencia", "atendimento_central"}
    assert {p.canal for p in prompts.values()} <= CANAIS_DA_ONTOLOGIA


def test_lista_os_prompts_com_o_argumento_da_cliente():
    resultado = _chamar(lambda c: c.list_prompts())
    nomes = {p.name for p in resultado.prompts}
    assert nomes == {"atendimento_app", "atendimento_agencia", "atendimento_central"}
    for prompt in resultado.prompts:
        assert [(a.name, a.required) for a in prompt.arguments] == [("cliente_id", True)]
        assert "Interlocutor:" in prompt.description


def test_persona_traz_o_nome_da_cliente_do_cadastro():
    resultado = _chamar(lambda c: c.get_prompt("atendimento_agencia", {"cliente_id": "cliente-ana"}))
    texto = resultado.messages[0].content.text
    assert "Ana Ribeiro" in texto and "`cliente-ana`" in texto
    assert "{" not in texto  # nenhum marcador sobrando
    assert "gerente" in texto


def test_cliente_desconhecida_nao_ganha_nome_inventado():
    resultado = _chamar(lambda c: c.get_prompt("atendimento_app", {"cliente_id": "cliente-x"}))
    assert "atende a cliente (id `cliente-x`)" in resultado.messages[0].content.text


def test_frontmatter_incompleto_e_nome_errado_sao_recusados(tmp_path: Path):
    incompleto = tmp_path / "loja.md"
    incompleto.write_text("---\nname: atendimento_loja\n---\n\nOi.\n", encoding="utf-8")
    with pytest.raises(PromptInvalido, match="frontmatter sem"):
        carregar_prompt(incompleto)
    errado = tmp_path / "loja.md"
    errado.write_text(
        "---\nname: outro\ncanal: canal-app\ntitle: T\ndescription: D\ninterlocutor: I\n---\n\nOi.\n",
        encoding="utf-8",
    )
    with pytest.raises(PromptInvalido, match="atendimento_loja"):
        carregar_prompt(errado)
