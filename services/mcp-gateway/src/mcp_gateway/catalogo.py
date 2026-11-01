"""Catálogo agregado: tools e resources de todos os servidores atrás do gateway."""

import logging
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass, field

from mcp import types
from mcp.client.client import Client

from mcp_gateway.upstreams import Upstream

log = logging.getLogger("mcp-gateway.catalogo")

# Abre uma sessão MCP com um upstream. Nos testes, vira um servidor em memória.
Conector = Callable[[Upstream], AbstractAsyncContextManager[Client]]
TOOLS_OCULTAS = {"ping"}


def conector_http(upstream: Upstream) -> AbstractAsyncContextManager[Client]:
    return Client(upstream.url_mcp, read_timeout_seconds=30)


@dataclass
class ToolRoteada:
    upstream: Upstream
    nome_original: str
    tool: types.Tool


@dataclass
class Catalogo:
    upstreams: list[Upstream]
    conectar: Conector = conector_http
    tools: dict[str, ToolRoteada] = field(default_factory=dict)
    resources: dict[str, tuple[Upstream, types.Resource]] = field(default_factory=dict)
    disponiveis: dict[str, bool] = field(default_factory=dict)
    # Tudo o que cada servidor oferece, inclusive o que o gateway não expõe (ex.: ping).
    brutas: dict[str, list[str]] = field(default_factory=dict)

    def upstream(self, nome: str) -> Upstream | None:
        return next((u for u in self.upstreams if u.nome == nome), None)

    def ferramentas_de(self, upstream: Upstream, fora: set[str]) -> list[dict]:
        """Tools do servidor e como aparecem no gateway: qualificadas, ocultas ou fora do ar."""
        itens = []
        for nome in self.brutas.get(upstream.nome, []):
            qualificado = f"{upstream.prefixo}.{nome}" if nome not in TOOLS_OCULTAS else None
            itens.append(
                {
                    "nome": nome,
                    "qualificado": qualificado,
                    "visivel": qualificado is not None,
                    "fora": qualificado in fora,
                }
            )
        return itens

    async def atualizar(self) -> None:
        """Relê tools e resources. Upstream fora mantém o que já se sabia dele:
        a rua continua no mapa, interditada, em vez de sumir."""
        for upstream in self.upstreams:
            try:
                async with self.conectar(upstream) as cliente:
                    tools = (await cliente.list_tools()).tools
                    resources = (await cliente.list_resources()).resources
            except Exception as erro:  # noqa: BLE001
                if self.disponiveis.get(upstream.nome, True):
                    log.warning("Não foi possível listar %s: %s", upstream.nome, erro)
                self.disponiveis[upstream.nome] = False
                continue
            self.disponiveis[upstream.nome] = True
            self.brutas[upstream.nome] = sorted(t.name for t in tools)
            self.tools = {n: t for n, t in self.tools.items() if t.upstream.nome != upstream.nome}
            for tool in tools:
                if tool.name in TOOLS_OCULTAS:
                    continue
                qualificado = f"{upstream.prefixo}.{tool.name}"
                self.tools[qualificado] = ToolRoteada(
                    upstream=upstream,
                    nome_original=tool.name,
                    tool=tool.model_copy(
                        update={
                            "name": qualificado,
                            "description": f"[{upstream.prefixo}] {tool.description or ''}",
                        }
                    ),
                )
            self.resources = {u: r for u, r in self.resources.items() if r[0].nome != upstream.nome}
            for resource in resources:
                self.resources[str(resource.uri)] = (upstream, resource)
