"""O mapa da cidade para o Modo Mapa: tudo vem da camada de contexto, pelo gateway.

O web desenha a cidade a partir do grafo (`contexto://mapa`), as rotas a partir de
`contexto.consultar_rota` e o detalhe de cada nó a partir de `contexto.consultar_entidade`.
Nada é desenhado à mão: o mapa é o grafo.
"""

import json
import re
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from typing import Any

from mcp.client.client import Client

RECURSO = "contexto://mapa"
# O SDK prefixa os erros de tool com "Error executing tool <nome>: "; a UI mostra só a mensagem.
PREFIXO_DO_SDK = re.compile(r"^Error executing tool [^:]+:\s*")


class EntidadeNaoEncontrada(LookupError):
    pass


class Mapa:
    def __init__(self, conectar_gateway: Callable[[], AbstractAsyncContextManager[Client]]) -> None:
        self.conectar_gateway = conectar_gateway

    async def cidade(self) -> dict[str, Any]:
        """Bairros, rio, avenidas, nós (com x, y e status vivo) e arestas."""
        async with self.conectar_gateway() as gateway:
            resultado = await gateway.read_resource(RECURSO)
        return json.loads(resultado.contents[0].text)

    async def rotas(self) -> dict[str, Any]:
        """As rotas da jornada, com paradas em ordem, estimativa (tempo, custo, risco) e alertas."""
        async with self.conectar_gateway() as gateway:
            resultado = await gateway.call_tool("contexto.consultar_rota", {})
        if resultado.is_error:
            raise RuntimeError(resultado.content[0].text if resultado.content else "consultar_rota falhou")
        return resultado.structured_content or {}

    async def entidade(self, ident: str) -> dict[str, Any]:
        """Atributos, estado vivo, proveniência e vizinhos de um nó do mapa."""
        async with self.conectar_gateway() as gateway:
            resultado = await gateway.call_tool("contexto.consultar_entidade", {"id": ident})
        if resultado.is_error:
            texto = resultado.content[0].text if resultado.content else ident
            raise EntidadeNaoEncontrada(PREFIXO_DO_SDK.sub("", texto))
        return resultado.structured_content or {}
