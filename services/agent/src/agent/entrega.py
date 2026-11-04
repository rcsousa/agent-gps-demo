"""Entrega dos eventos de uma viagem ao navegador: SSE e, como alternativa, consulta periódica.

O SSE é o caminho principal. Em redes corporativas, porém, proxies e antivírus com inspeção de
HTTPS costumam segurar a resposta inteira antes de entregá-la, e um stream que só termina no fim
da viagem nunca chega ao navegador. Para isso o mapa tem uma alternativa: a consulta por lotes
(long-polling). Cada resposta termina, então passa por qualquer proxy, e os ids dos eventos são
os mesmos do SSE: o navegador troca de caminho sem perder nem repetir nada.
"""

import re
from typing import Any

from bussola_comum.eventos import STREAM, decodificar

# Cabeçalhos que pedem a proxies e antivírus para não guardar nem transformar o stream.
# O X-Accel-Buffering vale para nginx no caminho (o da demo já está sem buffer).
CABECALHOS_SSE = {"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"}

# Alguns filtros só repassam a resposta depois de juntar alguns KB. Um comentário inicial
# (ignorado por todo cliente SSE, inclusive o EventSource) enche esse buffer logo de saída.
PREENCHIMENTO = {"comment": " " * 2048}

# Quanto a consulta espera por eventos novos antes de responder vazia (abaixo do timeout do Redis).
ESPERA_DA_CONSULTA_MS = 1500
TAMANHO_DO_LOTE = 200

# Ids do stream do Redis: "<milissegundos>-<sequência>".
_ID_DO_STREAM = re.compile(r"^\d+-\d+$")


def cursor_valido(cursor: str) -> bool:
    return bool(_ID_DO_STREAM.match(cursor))


async def lote_da_execucao(
    redis: Any, ident: str, cursor: str, espera_ms: int = ESPERA_DA_CONSULTA_MS
) -> dict:
    """Os eventos da execução depois do cursor, esperando um pouco se ainda não há nenhum.

    Devolve {eventos: [{id, evento}], cursor, fim}. O cursor avança também sobre eventos de outras
    execuções, para a próxima consulta não relê-los. Com o run.finished, fim é verdadeiro e o lote
    para nele.
    """
    lotes = await redis.xread({STREAM: cursor}, block=espera_ms, count=TAMANHO_DO_LOTE)
    eventos: list[dict[str, Any]] = []
    fim = False
    for entrada, campos in lotes[0][1] if lotes else []:
        cursor = entrada
        evento = decodificar(campos)
        if evento["dados"].get("execucao_id") != ident:
            continue
        eventos.append({"id": entrada, "evento": evento})
        if evento["tipo"] == "run.finished":
            fim = True
            break
    return {"eventos": eventos, "cursor": cursor, "fim": fim}


def lote_da_gravacao(eventos: list[dict[str, Any]], esperas: list[float]) -> dict:
    """A gravação inteira de uma vez, com a pausa antes de cada evento: o navegador toca no ritmo."""
    return {
        "eventos": [
            {"id": str(indice), "espera": espera, "evento": evento}
            for indice, (evento, espera) in enumerate(zip(eventos, esperas, strict=True))
        ],
        "fim": True,
    }
