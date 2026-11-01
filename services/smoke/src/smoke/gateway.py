"""Chama uma tool ou lê um resource pelo MCP gateway e imprime a resposta em JSON.

Uso (pelo script): ./scripts/gateway.sh cliente.obter_perfil '{"cliente_id": "cliente-ana"}'
Listar as tools:   ./scripts/gateway.sh --listar
Ler um resource:   ./scripts/gateway.sh contexto://mapa
"""

import asyncio
import json
import os
import sys

from bussola_comum.cliente_mcp import conectar

URL = "http://mcp-gateway:8000/mcp"


def _imprimir(dados) -> None:
    print(json.dumps(dados, ensure_ascii=False, indent=2))


async def executar(alvo: str, argumentos: dict) -> int:
    async with conectar(URL, os.environ["GATEWAY_TOKEN"]) as cliente:
        if alvo == "--listar":
            for tool in (await cliente.list_tools()).tools:
                print(f"{tool.name:45} {tool.description[:80]}")
            return 0
        if "://" in alvo:
            resultado = await cliente.read_resource(alvo)
            _imprimir(json.loads(resultado.contents[0].text))
            return 0
        resultado = await cliente.call_tool(alvo, argumentos)
    if resultado.is_error:
        print(f"Erro da tool: {resultado.content[0].text}", file=sys.stderr)
        _imprimir({"_meta": resultado.meta})
        return 1
    _imprimir(
        {**(resultado.structured_content or {"texto": resultado.content[0].text}), "_meta": resultado.meta}
    )
    return 0


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    argumentos = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
    return asyncio.run(executar(sys.argv[1], argumentos))


if __name__ == "__main__":
    sys.exit(main())
