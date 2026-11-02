"""Extensão io.modelcontextprotocol/skills (SEP-2640): formato do protocolo e consumo.

Fica isolado num módulo próprio porque o suporte a skills nos SDKs ainda muda:
servidor (skills-mcp), gateway e clientes (smoke, agente) falam por aqui.
"""

import hashlib
from typing import Any, Literal

import yaml
from mcp import types
from mcp.client.client import Client

IDENTIFICADOR = "io.modelcontextprotocol/skills"
CHAVE_SKILL_ATIVA = "bussola/skill"
# Correlaciona as chamadas de uma execução do agente nos eventos do gateway.
CHAVE_EXECUCAO = "bussola/execucao"


class ParamsListar(types.RequestParams):
    cursor: str | None = None


class ParamsObter(types.RequestParams):
    uri: str


class ResultadoListar(types.Result):
    skills: list[dict[str, Any]]
    next_cursor: str | None = None


class ResultadoObter(types.Result):
    skill: dict[str, Any]


# Requisições tipadas: com o `types.Request` genérico, o SDK descarta os params
# extras (como `uri`) ao injetar o `_meta` do protocolo 2026-07-28.
class RequisicaoListar(types.Request[ParamsListar, Literal["skills/list"]]):
    method: Literal["skills/list"] = "skills/list"
    params: ParamsListar


class RequisicaoObter(types.Request[ParamsObter, Literal["skills/get"]]):
    method: Literal["skills/get"] = "skills/get"
    params: ParamsObter


class SkillNaoConfere(Exception):
    """O conteúdo lido não é o que a listagem prometeu: o host não pode usá-lo."""


def anuncia_skills(cliente: Client) -> bool:
    return IDENTIFICADOR in (cliente.server_capabilities.extensions or {})


def _params(classe: type[types.RequestParams], meta: dict[str, Any] | None, **campos: Any):
    """Params com o `_meta` do host (execução e skill), quando houver: o gateway correlaciona os eventos."""
    return classe.model_validate({**campos, **({"_meta": meta} if meta else {})})


async def listar_skills(cliente: Client, meta: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Todas as entradas de skills/list, seguindo a paginação."""
    entradas, cursor = [], None
    while True:
        resultado = await cliente.session.send_request(
            RequisicaoListar(params=_params(ParamsListar, meta, cursor=cursor)), ResultadoListar
        )
        entradas.extend(resultado.skills)
        cursor = resultado.next_cursor
        if not cursor:
            return entradas


async def obter_skill(cliente: Client, uri: str, meta: dict[str, Any] | None = None) -> dict[str, Any]:
    resultado = await cliente.session.send_request(
        RequisicaoObter(params=_params(ParamsObter, meta, uri=uri)), ResultadoObter
    )
    return resultado.skill


def ler_frontmatter(texto: str) -> dict[str, Any]:
    fim = texto.find("\n---\n", 4)
    return yaml.safe_load(texto[4:fim]) if texto.startswith("---\n") and fim > 0 else {}


async def ler_arquivo(
    cliente: Client, uri: str, entrada: dict[str, Any], meta: dict[str, Any] | None = None
) -> str:
    """Lê um arquivo da skill e verifica tamanho, digest e (no SKILL.md) o frontmatter."""
    descritor = next((r for r in entrada["resources"] if r["uri"] == uri), None)
    if descritor is None:
        raise SkillNaoConfere(f"{uri} não está entre os arquivos listados da skill.")
    texto = (await cliente.read_resource(uri, meta=meta)).contents[0].text
    conteudo = texto.encode("utf-8")
    if len(conteudo) != descritor["size"]:
        raise SkillNaoConfere(f"{uri}: tamanho {len(conteudo)} diferente do listado ({descritor['size']}).")
    if "sha256:" + hashlib.sha256(conteudo).hexdigest() != descritor["digest"]:
        raise SkillNaoConfere(f"{uri}: digest diferente do listado.")
    if uri == entrada["uri"] and ler_frontmatter(texto) != entrada["frontmatter"]:
        raise SkillNaoConfere(f"{uri}: frontmatter diferente do listado.")
    return texto


def tools_permitidas(frontmatter: dict[str, Any]) -> set[str]:
    return set((frontmatter.get("allowed-tools") or "").split())


def skills_usadas(frontmatter: dict[str, Any]) -> list[str]:
    return (frontmatter.get("metadata", {}).get("usa-skills") or "").split()


def tools_da_skill(entradas: dict[str, dict[str, Any]], uri: str) -> set[str] | None:
    """Tools que a skill permite, somadas às das skills que ela usa. None se a skill não existe.

    `entradas` mapeia a URI do SKILL.md para a entrada de skills/list.
    """
    if uri not in entradas:
        return None
    frontmatter = entradas[uri]["frontmatter"]
    permitidas = tools_permitidas(frontmatter)
    por_nome = {e["frontmatter"]["name"]: e["frontmatter"] for e in entradas.values()}
    for nome in skills_usadas(frontmatter):
        if nome in por_nome:
            permitidas |= tools_permitidas(por_nome[nome])
    return permitidas
