"""Catálogo para o dashboard de status: o que o gateway oferece, por dentro.

Tudo vem do gateway, por MCP (tools, prompts, skills e o código em `fonte://`), e do
barramento (as chamadas recentes de cada item). O agente continua conhecendo só o
gateway e o barramento: o dashboard vê a plataforma pelos mesmos olhos dele.
"""

import json
import re
from collections.abc import Awaitable, Callable
from contextlib import AbstractAsyncContextManager
from typing import Any

from mcp.client.client import Client
from redis.asyncio import Redis

from agent import prompts
from bussola_comum.eventos import STREAM, decodificar
from bussola_comum.skills import (
    SkillNaoConfere,
    ler_arquivo,
    listar_skills,
    skills_usadas,
    tools_da_skill,
    tools_permitidas,
)

LIMITE_CHAMADAS = 20
JANELA_DO_BARRAMENTO = 5000
DESCRICAO_DE_CANAL = re.compile(r"Canal: (?P<canal>[\w-]+)\. Interlocutor: (?P<interlocutor>.+?)\.?$")


class NaoEncontrado(LookupError):
    pass


class Catalogo:
    def __init__(
        self,
        conectar_gateway: Callable[[], AbstractAsyncContextManager[Client]],
        redis: Redis,
        saude_do_gateway: Callable[[], Awaitable[dict[str, Any]]],
    ) -> None:
        self.conectar_gateway = conectar_gateway
        self.redis = redis
        self.saude_do_gateway = saude_do_gateway

    async def montar(self) -> dict[str, Any]:
        saude = await self.saude_do_gateway()
        async with self.conectar_gateway() as gateway:
            tools = (await gateway.list_tools()).tools
            lista_de_prompts = (await gateway.list_prompts()).prompts
            entradas = {e["uri"]: e for e in await listar_skills(gateway)}

        # Quem oferece o quê, segundo o gateway (inclui o que fica oculto e o que está fora do ar).
        origem_tool: dict[str, tuple[str, dict]] = {}
        origem_prompt: dict[str, str] = {}
        origem_skill: dict[str, str] = {}
        for servico in saude.get("servicos", []):
            for ferramenta in servico.get("ferramentas", []):
                if ferramenta.get("qualificado"):
                    origem_tool[ferramenta["qualificado"]] = (servico["nome"], ferramenta)
            for nome in servico.get("prompts", []):
                origem_prompt[nome] = servico["nome"]
            for uri in servico.get("skills", []):
                origem_skill[uri] = servico["nome"]

        tools_por_skill = {uri: tools_da_skill(entradas, uri) or set() for uri in entradas}
        diretas = {uri: tools_permitidas(e["frontmatter"]) for uri, e in entradas.items()}

        def skills_da_tool(nome: str) -> list[dict[str, Any]]:
            return [
                {"uri": uri, "nome": entradas[uri]["frontmatter"]["name"], "direta": nome in diretas[uri]}
                for uri in sorted(entradas)
                if nome in tools_por_skill[uri]
            ]

        return {
            "tools": [
                {
                    "nome": t.name,
                    "servidor": origem_tool.get(t.name, ("", {}))[0],
                    "nome_original": origem_tool.get(t.name, ("", {}))[1].get(
                        "nome", t.name.split(".", 1)[-1]
                    ),
                    "descricao": _sem_prefixo(t.description or ""),
                    "fora": origem_tool.get(t.name, ("", {}))[1].get("fora", False),
                    "esquema_entrada": t.input_schema,
                    "esquema_saida": t.output_schema,
                    "anotacoes": t.annotations.model_dump(exclude_none=True) if t.annotations else {},
                    "skills": skills_da_tool(t.name),
                }
                for t in sorted(tools, key=lambda t: t.name)
            ],
            "skills": [
                {
                    "uri": uri,
                    "nome": e["frontmatter"]["name"],
                    "descricao": e["frontmatter"].get("description", ""),
                    "servidor": origem_skill.get(uri, ""),
                    "frontmatter": e["frontmatter"],
                    "tools": sorted(diretas[uri]),
                    "tools_com_reuso": sorted(tools_por_skill[uri]),
                    "usa_skills": skills_usadas(e["frontmatter"]),
                    "arquivos": e["resources"],
                }
                for uri, e in sorted(entradas.items())
            ],
            "prompts": [
                _prompt(p, origem_prompt.get(p.name, ""))
                for p in sorted(lista_de_prompts, key=lambda p: p.name)
            ],
        }

    async def fonte(self, uri: str) -> dict[str, Any]:
        if not uri.startswith("fonte://"):
            raise ValueError("A fonte é lida só por URIs fonte://.")
        try:
            async with self.conectar_gateway() as gateway:
                resultado = await gateway.read_resource(uri)
        except Exception as erro:  # noqa: BLE001
            raise NaoEncontrado(f"Fonte não encontrada: {uri}.") from erro
        return json.loads(resultado.contents[0].text)

    async def arquivo_de_skill(self, uri: str) -> dict[str, Any]:
        if not uri.startswith("skill://"):
            raise ValueError("Arquivos de skill são lidos só por URIs skill://.")
        raiz = "/".join(uri.split("/")[:3]) + "/SKILL.md"
        # Erros saem depois de fechar a sessão: dentro dela, viriam embrulhados num ExceptionGroup.
        entrada, texto, problema = None, "", None
        async with self.conectar_gateway() as gateway:
            entrada = next((e for e in await listar_skills(gateway) if e["uri"] == raiz), None)
            if entrada is not None:
                try:
                    texto = await ler_arquivo(gateway, uri, entrada)
                except SkillNaoConfere as erro:
                    problema = str(erro)
        if entrada is None:
            raise NaoEncontrado(f"Skill não encontrada: {raiz}.")
        if problema:
            raise NaoEncontrado(problema)
        descritor = next(r for r in entrada["resources"] if r["uri"] == uri)
        return {"uri": uri, "texto": texto, "verificado": True, **descritor}

    async def previa_de_prompt(self, nome: str) -> dict[str, Any]:
        try:
            async with self.conectar_gateway() as gateway:
                resultado = await gateway.get_prompt(nome, {"cliente_id": prompts.CLIENTE_PADRAO})
        except Exception as erro:  # noqa: BLE001
            raise NaoEncontrado(f"Prompt indisponível: {nome}.") from erro
        texto = "\n\n".join(getattr(m.content, "text", "") for m in resultado.messages)
        return {"nome": nome, "cliente_id": prompts.CLIENTE_PADRAO, "texto": texto}

    async def chamadas(
        self, *, tool: str | None = None, prompt: str | None = None, skill: str | None = None
    ) -> list[dict]:
        """Os eventos mais recentes do item no barramento, do mais novo para o mais antigo."""

        def do_item(tipo: str, dados: dict[str, Any]) -> bool:
            if tool:
                return tipo == "tool.called" and dados.get("tool") == tool
            if prompt:
                return tipo == "prompt.read" and dados.get("prompt") == prompt
            if skill:
                return (tipo == "skill.loaded" and dados.get("uri") == skill) or (
                    tipo == "tool.called" and dados.get("skill") == skill
                )
            return False

        achados = []
        for ident, campos in await self.redis.xrevrange(STREAM, count=JANELA_DO_BARRAMENTO):
            evento = decodificar(campos)
            dados = evento["dados"]
            if not do_item(evento["tipo"], dados):
                continue
            achados.append(
                {
                    "id": ident,
                    "tipo": evento["tipo"],
                    "instante": evento["instante"],
                    "tool": dados.get("tool"),
                    "status": dados.get("status", "ok"),
                    "motivo": dados.get("motivo"),
                    "duracao_ms": dados.get("duracao_ms"),
                    "skill": dados.get("skill") or dados.get("uri"),
                    "execucao_id": dados.get("execucao_id"),
                    "erro": dados.get("erro"),
                }
            )
            if len(achados) == LIMITE_CHAMADAS:
                break
        return achados


def _sem_prefixo(descricao: str) -> str:
    """O gateway prefixa a descrição com o servidor ("[cliente] ..."); a tabela já mostra o servidor."""
    return re.sub(r"^\[[\w-]+\] ", "", descricao)


def _prompt(prompt: Any, servidor: str) -> dict[str, Any]:
    descricao = prompt.description or ""
    canal = DESCRICAO_DE_CANAL.search(descricao)
    return {
        "nome": prompt.name,
        "titulo": prompt.title,
        "descricao": DESCRICAO_DE_CANAL.sub("", descricao).strip(),
        "servidor": servidor,
        "canal": canal["canal"] if canal else None,
        "interlocutor": canal["interlocutor"] if canal else None,
        "argumentos": [
            {"nome": a.name, "descricao": a.description, "obrigatorio": bool(a.required)}
            for a in prompt.arguments or []
        ],
    }
