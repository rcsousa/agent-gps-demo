"""Eventos do barramento publicados pelo gateway (ponto de observação).

Formato de cada entrada no stream `bussola:eventos`:
  tipo (ex.: tool.called), origem, instante e dados (JSON).
"""

import json
import logging
from typing import Any, Protocol

from redis.asyncio import Redis

from bussola_comum.dominio import agora

STREAM = "bussola:eventos"
TAMANHO_MAXIMO = 10_000

log = logging.getLogger("mcp-gateway.eventos")


class Publicador(Protocol):
    async def publicar(self, tipo: str, dados: dict[str, Any]) -> None: ...


class PublicadorRedis:
    def __init__(self, redis: Redis, origem: str = "mcp-gateway") -> None:
        self.redis = redis
        self.origem = origem

    async def publicar(self, tipo: str, dados: dict[str, Any]) -> None:
        try:
            await self.redis.xadd(
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
