"""As skills versionadas e a extensão io.modelcontextprotocol/skills (SEP-2640)."""

import hashlib
import re

import pytest
from mcp.client.client import Client
from mcp.shared.exceptions import MCPError

from bussola_comum.skills import (
    IDENTIFICADOR,
    ler_arquivo,
    ler_frontmatter,
    listar_skills,
    obter_skill,
    skills_usadas,
    tools_permitidas,
)
from skills_mcp.catalogo import PASTA_PADRAO, ErroSkill, carregar_catalogo, carregar_skill
from skills_mcp.servidor import criar_servidor

pytestmark = pytest.mark.anyio
SKILLS_DA_SPEC = {
    "contratacao-seguro-residencial",
    "verificacao-consentimento",
    "cotacao-multisseguradora",
    "escalonamento-humano",
}
NOME_TOOL = re.compile(r"[a-z]+\.[a-z_]+")


@pytest.fixture(scope="module")
def catalogo():
    return carregar_catalogo()


# --- As skills versionadas -------------------------------------------------------


def test_as_quatro_skills_da_spec(catalogo):
    assert {s.nome for s in catalogo.values()} == SKILLS_DA_SPEC


def test_tools_permitidas_bem_formadas(catalogo):
    for skill in catalogo.values():
        tools = tools_permitidas(skill.frontmatter)
        assert tools, f"{skill.nome} sem allowed-tools"
        assert all(NOME_TOOL.fullmatch(t) for t in tools), skill.nome


def test_skills_usadas_existem(catalogo):
    nomes = {s.nome for s in catalogo.values()}
    for skill in catalogo.values():
        assert set(skills_usadas(skill.frontmatter)) <= nomes


def test_toda_referencia_citada_existe_e_nada_sobra(catalogo):
    principal = catalogo["skill://contratacao-seguro-residencial/SKILL.md"]
    texto = principal.arquivos[0].texto
    citados = set(re.findall(r"skill://contratacao-seguro-residencial/(references/[a-z]+\.md)", texto))
    arquivos = {a.uri.split("/", 3)[3] for a in principal.arquivos[1:]}
    assert citados == arquivos


def test_skills_citadas_por_uri_existem(catalogo):
    for skill in catalogo.values():
        for arquivo in skill.arquivos:
            for uri in re.findall(r"skill://[a-z-]+/SKILL\.md", arquivo.texto):
                assert uri in catalogo, f"{arquivo.uri} cita {uri}, que não existe"


def test_nenhuma_tool_de_distracao_e_permitida(catalogo):
    distracao = {
        "cliente.listar_transacoes",
        "cliente.atualizar_endereco",
        "consentimento.revogar",
        "pagamentos.estornar",
        "seguradoras.cancelar_apolice",
        "atendimento.transferir_para_humano",
    }
    for skill in catalogo.values():
        assert not tools_permitidas(skill.frontmatter) & distracao, skill.nome


def test_skill_mal_formada_e_recusada(tmp_path):
    pasta = tmp_path / "minha-skill"
    pasta.mkdir()
    (pasta / "SKILL.md").write_text("---\nname: outra\ndescription: x\n---\n", encoding="utf-8")
    with pytest.raises(ErroSkill, match="igual ao nome da pasta"):
        carregar_skill(pasta)
    (pasta / "SKILL.md").write_text("sem frontmatter", encoding="utf-8")
    with pytest.raises(ErroSkill, match="frontmatter"):
        carregar_skill(pasta)


def test_pasta_padrao_existe():
    assert (PASTA_PADRAO / "contratacao-seguro-residencial" / "SKILL.md").exists()


# --- O protocolo (SEP-2640) ------------------------------------------------------


async def test_capacidade_anunciada():
    async with Client(criar_servidor()) as cliente:
        assert IDENTIFICADOR in cliente.server_capabilities.extensions
        assert cliente.server_capabilities.resources is not None


async def test_skills_list_com_frontmatter_literal_e_digests(catalogo):
    async with Client(criar_servidor()) as cliente:
        entradas = await listar_skills(cliente)
        assert {e["uri"] for e in entradas} == set(catalogo)
        for entrada in entradas:
            skill_md = (await cliente.read_resource(entrada["uri"])).contents[0].text
            assert ler_frontmatter(skill_md) == entrada["frontmatter"]
            assert entrada["resources"][0]["uri"] == entrada["uri"]
            for descritor in entrada["resources"]:
                conteudo = (await cliente.read_resource(descritor["uri"])).contents[0].text.encode()
                assert descritor["digest"] == "sha256:" + hashlib.sha256(conteudo).hexdigest()
                assert descritor["size"] == len(conteudo)


async def test_skills_get_e_leitura_verificada():
    async with Client(criar_servidor()) as cliente:
        entrada = await obter_skill(cliente, "skill://contratacao-seguro-residencial/SKILL.md")
        texto = await ler_arquivo(
            cliente, "skill://contratacao-seguro-residencial/references/desvios.md", entrada
        )
    assert "Rua interditada" in texto and "Pedágio" in texto


async def test_skills_get_desconhecida_devolve_parametros_invalidos():
    async with Client(criar_servidor()) as cliente:
        with pytest.raises(MCPError) as erro:
            await obter_skill(cliente, "skill://nao-existe/SKILL.md")
    assert erro.value.error.code == -32602
