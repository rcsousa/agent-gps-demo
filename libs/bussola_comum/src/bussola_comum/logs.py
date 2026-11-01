"""Logging estruturado em JSON, uma linha por evento."""

import json
import logging
import sys
from datetime import UTC, datetime


class _FormatoJson(logging.Formatter):
    def __init__(self, servico: str) -> None:
        super().__init__()
        self.servico = servico

    def format(self, record: logging.LogRecord) -> str:
        dados = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "nivel": record.levelname,
            "servico": self.servico,
            "logger": record.name,
            "mensagem": record.getMessage(),
        }
        if record.exc_info:
            dados["erro"] = self.formatException(record.exc_info)
        return json.dumps(dados, ensure_ascii=False)


def configurar_logs(servico: str, nivel: str = "INFO") -> logging.Logger:
    manipulador = logging.StreamHandler(sys.stdout)
    manipulador.setFormatter(_FormatoJson(servico))
    raiz = logging.getLogger()
    raiz.handlers[:] = [manipulador]
    raiz.setLevel(nivel.upper())
    return logging.getLogger(servico)
