"""Chama uma tool do contexto-mcp e imprime a resposta em JSON.

Uso (pelo script): ./scripts/contexto.sh consultar_rota '{"rota": "rota-rapida"}'
Para ler o mapa:   ./scripts/contexto.sh contexto://mapa
"""

import asyncio
import json
import sys

from mcp.client.client import Client

URL = "http://contexto-mcp:8000/mcp"


async def chamar(alvo: str, argumentos: dict) -> int:
    async with Client(URL, read_timeout_seconds=15) as cliente:
        if alvo.startswith("contexto://"):
            resultado = await cliente.read_resource(alvo)
            print(json.dumps(json.loads(resultado.contents[0].text), ensure_ascii=False, indent=2))
            return 0
        resultado = await cliente.call_tool(alvo, argumentos)
    if resultado.is_error:
        print(f"Erro da tool: {resultado.content[0].text}", file=sys.stderr)
        return 1
    print(json.dumps(resultado.structured_content, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    argumentos = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
    return asyncio.run(chamar(sys.argv[1], argumentos))


if __name__ == "__main__":
    sys.exit(main())
