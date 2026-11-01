"""Estado vivo do mundo simulado, guardado no barramento (Redis).

O simulador é o único escritor dos efeitos de incidente (`bussola:estado:<id>`).
Os servidores de domínio leem esses efeitos antes de agir, usando os mesmos
ids da ontologia, e guardam ali os seus registros mutáveis
(`bussola:dominio:<tipo>:<id>`): cotações, propostas, pagamentos, apólices...
"""

import asyncio
import json
from typing import Any

from mcp.server.mcpserver.exceptions import ToolError
from redis.asyncio import Redis

PREFIXO_ESTADO = "bussola:estado:"
PREFIXO_DOMINIO = "bussola:dominio:"
ATRASO_MAXIMO_S = 3.0


class EstadoVivo:
    def __init__(self, redis: Redis) -> None:
        self.redis = redis

    @classmethod
    def de_url(cls, url: str) -> "EstadoVivo":
        return cls(Redis.from_url(url, decode_responses=True))

    # --- Efeitos de incidente --------------------------------------------------

    async def efeito(self, entidade_id: str) -> dict[str, Any]:
        """Efeito ativo sobre a entidade: {"estado": {...}, "atributos": {...}, "proveniencia": {...}}."""
        bruto = await self.redis.get(PREFIXO_ESTADO + entidade_id)
        return json.loads(bruto) if bruto else {}

    async def gravar_efeito(self, entidade_id: str, efeito: dict[str, Any]) -> None:
        """Mescla o efeito com o que já existe para a entidade (vários incidentes podem somar)."""
        atual = await self.efeito(entidade_id)
        for parte in ("estado", "atributos", "proveniencia"):
            if efeito.get(parte):
                atual[parte] = {**atual.get(parte, {}), **efeito[parte]}
        await self.redis.set(PREFIXO_ESTADO + entidade_id, json.dumps(atual, ensure_ascii=False))

    async def limpar_efeitos(self) -> None:
        await self._apagar(PREFIXO_ESTADO + "*")

    async def garantir_disponivel(self, entidade_id: str, nome: str) -> str | None:
        """Barra a chamada se a entidade estiver fora; atrasa e avisa se estiver degradada."""
        estado = (await self.efeito(entidade_id)).get("estado", {})
        status = estado.get("status")
        if status == "fora":
            raise ToolError(f"{nome} está fora do ar no momento. Tente outra rota ou mais tarde.")
        if status == "degradado":
            latencia_ms = estado.get("latencia_ms", 0)
            await asyncio.sleep(min(latencia_ms / 1000, ATRASO_MAXIMO_S))
            return f"{nome} responde com lentidão agora (latência de {latencia_ms} ms)."
        return None

    # --- Registros mutáveis dos domínios --------------------------------------

    async def salvar(self, tipo: str, ident: str, dados: dict[str, Any]) -> None:
        await self.redis.set(f"{PREFIXO_DOMINIO}{tipo}:{ident}", json.dumps(dados, ensure_ascii=False))

    async def obter(self, tipo: str, ident: str) -> dict[str, Any] | None:
        bruto = await self.redis.get(f"{PREFIXO_DOMINIO}{tipo}:{ident}")
        return json.loads(bruto) if bruto else None

    async def listar(self, tipo: str) -> list[dict[str, Any]]:
        chaves = sorted([c async for c in self.redis.scan_iter(f"{PREFIXO_DOMINIO}{tipo}:*")])
        valores = await self.redis.mget(chaves) if chaves else []
        return [json.loads(v) for v in valores if v]

    async def limpar_dominio(self) -> None:
        await self._apagar(PREFIXO_DOMINIO + "*")

    async def _apagar(self, padrao: str) -> None:
        chaves = [c async for c in self.redis.scan_iter(padrao)]
        if chaves:
            await self.redis.delete(*chaves)


def aplicar_efeito(base: dict[str, Any], efeito: dict[str, Any]) -> dict[str, Any]:
    """Visão atual de um registro do cadastro: dados-base + atributos e proveniência do efeito."""
    atual = {**base, **efeito.get("atributos", {})}
    if efeito.get("proveniencia"):
        atual["proveniencia"] = {**base.get("proveniencia", {}), **efeito["proveniencia"]}
    if efeito.get("estado"):
        atual["estado"] = {**base.get("estado", {}), **efeito["estado"]}
    return atual
