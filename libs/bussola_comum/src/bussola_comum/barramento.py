"""Acesso ao barramento de eventos (Redis Streams).

Na Fase 1 só existe a checagem de saúde; publicação e leitura de eventos
chegam na Fase 5. O pacote `redis` é dependência de quem usa este módulo.
"""

from bussola_comum.saude import Checagem


def checar_barramento(url: str) -> Checagem:
    async def checar() -> bool:
        from redis.asyncio import Redis

        cliente = Redis.from_url(url, socket_connect_timeout=2, socket_timeout=2)
        try:
            return bool(await cliente.ping())
        finally:
            await cliente.aclose()

    return checar
