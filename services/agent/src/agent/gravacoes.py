"""Gravações de execuções reais, para o replay offline (sem rede, sem chave, sem LLM).

Cada gravação é um `gravacoes/<nome>.jsonl` versionado no repositório: a primeira linha é o
cabeçalho (cena, modo, canal, modelo, incidentes ativos, data) e as demais são os eventos da
execução, como saíram do barramento. O replay toca esses eventos no ritmo original; o mapa
mostra o selo "Replay" o tempo todo, para ninguém confundir com uma viagem ao vivo.
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from bussola_comum.dominio import agora

NOME = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
ESPERA_MAXIMA_S = 3.0  # no replay, nenhuma pausa entre eventos passa disso


class GravacaoInvalida(ValueError):
    pass


class Gravacoes:
    def __init__(self, pasta: Path) -> None:
        self.pasta = pasta

    def _arquivo(self, nome: str) -> Path:
        if not NOME.fullmatch(nome):
            raise GravacaoInvalida(f"Nome inválido: '{nome}'. Use letras minúsculas, números e hífens.")
        return self.pasta / f"{nome}.jsonl"

    def salvar(
        self, nome: str, execucao: dict[str, Any], eventos: list[dict[str, Any]], **extra: Any
    ) -> dict:
        if not eventos or eventos[-1]["tipo"] != "run.finished":
            raise GravacaoInvalida("Só dá para gravar uma execução terminada.")
        cabecalho = {
            "nome": nome,
            "execucao_id": execucao["id"],
            "modo": execucao["modo"],
            "canal": execucao["canal"],
            "provedor": execucao["provedor"],
            "modelo": execucao.get("modelo") or execucao["provedor"],
            "status": execucao["status"],
            "apolice": execucao.get("apolice"),
            "gravado_em": agora(),
            "eventos": len(eventos),
            **extra,
        }
        self.pasta.mkdir(parents=True, exist_ok=True)
        linhas = [json.dumps(cabecalho, ensure_ascii=False)] + [
            json.dumps(e, ensure_ascii=False) for e in eventos
        ]
        self._arquivo(nome).write_text("\n".join(linhas) + "\n", encoding="utf-8")
        return cabecalho

    def carregar(self, nome: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        arquivo = self._arquivo(nome)
        if not arquivo.exists():
            raise FileNotFoundError(nome)
        linhas = [json.loads(linha) for linha in arquivo.read_text(encoding="utf-8").splitlines() if linha]
        return linhas[0], linhas[1:]

    def listar(self) -> list[dict[str, Any]]:
        if not self.pasta.exists():
            return []
        cabecalhos = []
        for arquivo in sorted(self.pasta.glob("*.jsonl")):
            with arquivo.open(encoding="utf-8") as f:
                cabecalhos.append(json.loads(f.readline()))
        return cabecalhos

    def apagar(self, nome: str) -> None:
        arquivo = self._arquivo(nome)
        if not arquivo.exists():
            raise FileNotFoundError(nome)
        arquivo.unlink()


def esperas(eventos: list[dict[str, Any]]) -> list[float]:
    """Quanto esperar antes de cada evento, pelo instante original (com teto)."""
    resultado, anterior = [], None
    for evento in eventos:
        instante = datetime.fromisoformat(evento["instante"])
        espera = 0.0 if anterior is None else (instante - anterior).total_seconds()
        resultado.append(min(max(espera, 0.0), ESPERA_MAXIMA_S))
        anterior = instante
    return resultado
