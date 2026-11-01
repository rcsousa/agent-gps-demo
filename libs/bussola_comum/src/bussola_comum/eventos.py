"""Barramento de eventos (Redis Streams): o que o Mapa e o Raio-X desenham.

Cada entrada do stream `bussola:eventos` tem: tipo (ex.: tool.called,
step.started), origem (mcp-gateway, agent), instante e dados (JSON).
Toda animação na tela corresponde a uma entrada daqui.
"""

import json
import logging
from typing import Any, Protocol

from redis.asyncio import Redis

from bussola_comum.dominio import agora

STREAM = "bussola:eventos"
TAMANHO_MAXIMO = 10_000

log = logging.getLogger("bussola.eventos")


class Publicador(Protocol):
    async def publicar(self, tipo: str, dados: dict[str, Any]) -> str | None: ...


class PublicadorRedis:
    def __init__(self, redis: Redis, origem: str) -> None:
        self.redis = redis
        self.origem = origem

    async def publicar(self, tipo: str, dados: dict[str, Any]) -> str | None:
        """Publica e devolve o id da entrada no stream (None se o barramento falhar)."""
        try:
            return await self.redis.xadd(
                STREAM,
                {
                    "tipo": tipo,
                    "origem": self.origem,
                    "instante": agora(),
                    "dados": json.dumps(dados, ensure_ascii=False),
                },
                maxlen=TAMANHO_MAXIMO,
                approximate=True,
            )
        except Exception as erro:  # noqa: BLE001
            # Observação nunca derruba a chamada: o evento se perde, a viagem segue.
            log.warning("Evento %s não publicado: %s", tipo, erro)
            return None


def decodificar(campos: dict[str, str]) -> dict[str, Any]:
    """Entrada crua do stream → {tipo, origem, instante, dados}."""
    return {
        "tipo": campos["tipo"],
        "origem": campos["origem"],
        "instante": campos["instante"],
        "dados": json.loads(campos["dados"]),
    }
