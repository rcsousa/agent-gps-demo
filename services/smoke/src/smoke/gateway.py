"""Fala com o MCP gateway como o agente faria e imprime a resposta em JSON.

Uso (pelo script):
  ./scripts/gateway.sh cliente.obter_perfil '{"cliente_id": "cliente-ana"}'
  ./scripts/gateway.sh pagamentos.estornar '{"pagamento_id": "x"}' --skill contratacao-seguro-residencial
  ./scripts/gateway.sh <tool> '{...}' --skill <nome> --execucao <id>   # a ordem vale por execução
  ./scripts/gateway.sh --listar                         # tools
  ./scripts/gateway.sh --skills                         # skills (skills/list)
  ./scripts/gateway.sh --prompts                        # prompts (persona por canal)
  ./scripts/gateway.sh --prompt canais.atendimento_agencia '{"cliente_id": "cliente-ana"}'
  ./scripts/gateway.sh skill://<nome>/SKILL.md          # arquivo de skill, com digest verificado
  ./scripts/gateway.sh contexto://mapa                  # outro resource
"""

import asyncio
import json
import os
import sys
import uuid

from bussola_comum.cliente_mcp import conectar
from bussola_comum.skills import CHAVE_EXECUCAO, CHAVE_SKILL_ATIVA, ler_arquivo, listar_skills, obter_skill

URL = "http://mcp-gateway:8000/mcp"


def _imprimir(dados) -> None:
    print(json.dumps(dados, ensure_ascii=False, indent=2))


async def executar(alvo: str, argumentos: dict, skill: str | None, execucao: str | None = None) -> int:
    async with conectar(URL, os.environ["GATEWAY_TOKEN"]) as cliente:
        if alvo == "--listar":
            for tool in (await cliente.list_tools()).tools:
                print(f"{tool.name:45} {tool.description[:80]}")
            return 0
        if alvo == "--skills":
            for entrada in await listar_skills(cliente):
                fm = entrada["frontmatter"]
                print(f"\n{entrada['uri']}\n  {fm['description']}")
                print(f"  tools permitidas: {fm.get('allowed-tools', '')}")
                for arquivo in entrada["resources"]:
                    print(f"  · {arquivo['uri']}  {arquivo['size']} bytes  {arquivo['digest'][:19]}…")
            return 0
        if alvo == "--prompts":
            for prompt in (await cliente.list_prompts()).prompts:
                print(f"\n{prompt.name}\n  {prompt.description}")
                print(f"  argumentos: {', '.join(a.name for a in prompt.arguments or [])}")
            return 0
        if alvo.startswith("skill://"):
            raiz = alvo.split("/", 3)[2]
            entrada = await obter_skill(cliente, f"skill://{raiz}/SKILL.md")
            print(await ler_arquivo(cliente, alvo, entrada))
            print("\n[digest e tamanho conferem com skills/get]", file=sys.stderr)
            return 0
        if "://" in alvo:
            resultado = await cliente.read_resource(alvo)
            _imprimir(json.loads(resultado.contents[0].text))
            return 0
        meta = {CHAVE_SKILL_ATIVA: f"skill://{skill}/SKILL.md", CHAVE_EXECUCAO: execucao} if skill else None
        resultado = await cliente.call_tool(alvo, argumentos, meta=meta)
    if resultado.is_error:
        print(f"Erro da tool: {resultado.content[0].text}", file=sys.stderr)
        _imprimir({"_meta": resultado.meta})
        return 1
    _imprimir(
        {**(resultado.structured_content or {"texto": resultado.content[0].text}), "_meta": resultado.meta}
    )
    return 0


async def ler_prompt(nome: str, argumentos: dict) -> int:
    async with conectar(URL, os.environ["GATEWAY_TOKEN"]) as cliente:
        resultado = await cliente.get_prompt(nome, argumentos)
    for mensagem in resultado.messages:
        print(getattr(mensagem.content, "text", mensagem.content))
    _imprimir({"_meta": resultado.meta})
    return 0


def main() -> int:
    args = sys.argv[1:]
    skill = execucao = None
    if "--skill" in args:
        i = args.index("--skill")
        skill = args[i + 1]
        del args[i : i + 2]
    if "--execucao" in args:
        i = args.index("--execucao")
        execucao = args[i + 1]
        del args[i : i + 2]
    if skill and not execucao:
        # Com skill, a ordem vale por execução: sem id, cada chamada começa uma execução nova.
        execucao = f"cli-{uuid.uuid4().hex[:8]}"
        print(f"[execução {execucao}: repita --execucao {execucao} para seguir na mesma]", file=sys.stderr)
    if not args:
        print(__doc__, file=sys.stderr)
        return 2
    if args[0] == "--prompt" and len(args) > 1:
        argumentos = json.loads(args[2]) if len(args) > 2 else {}
        return asyncio.run(ler_prompt(args[1], argumentos))
    argumentos = json.loads(args[1]) if len(args) > 1 else {}
    return asyncio.run(executar(args[0], argumentos, skill, execucao))


if __name__ == "__main__":
    sys.exit(main())
