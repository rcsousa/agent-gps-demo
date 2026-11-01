"""Layout fixo da cidade, calculado uma vez e versionado em ontologia/layout.json.

Cada bairro tem um polígono curado. Dentro dele, os nós são distribuídos por
layout de forças (semente fixa), encaixados numa grade de quadras e afastados
das bordas. Relações entre bairros viram avenidas.

Uso: ./scripts/gerar-layout.sh (roda `python -m contexto_mcp.layout` no container).
"""

import json
import math
from collections import Counter
from pathlib import Path

import networkx as nx

from contexto_mcp.ontologia import PASTA_PADRAO, Ontologia, carregar_ontologia

ARQUIVO_LAYOUT = "layout.json"
GRADE = 20  # tamanho da quadra, em unidades do mundo
MARGEM = 12  # distância mínima entre um nó e a borda do bairro
SEMENTE = 7

Ponto = tuple[float, float]


def dentro(ponto: Ponto, poligono: list[Ponto]) -> bool:
    """Ray casting: o ponto está dentro do polígono?"""
    x, y = ponto
    resultado = False
    for (x1, y1), (x2, y2) in zip(poligono, poligono[1:] + poligono[:1], strict=True):
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            resultado = not resultado
    return resultado


def dentro_com_margem(ponto: Ponto, poligono: list[Ponto], margem: float = MARGEM) -> bool:
    x, y = ponto
    return all(
        dentro((x + dx, y + dy), poligono)
        for dx, dy in ((0, 0), (margem, 0), (-margem, 0), (0, margem), (0, -margem))
    )


def _celula_livre(alvo: Ponto, poligono: list[Ponto], ocupadas: set[Ponto]) -> Ponto:
    """A célula da grade mais próxima do alvo que está livre e dentro do bairro."""
    cx, cy = round(alvo[0] / GRADE), round(alvo[1] / GRADE)
    for raio in range(0, 60):
        candidatas = [
            (cx + dx, cy + dy)
            for dx in range(-raio, raio + 1)
            for dy in range(-raio, raio + 1)
            if max(abs(dx), abs(dy)) == raio
        ]
        candidatas.sort(key=lambda c: (math.dist(c, (alvo[0] / GRADE, alvo[1] / GRADE)), c))
        for gx, gy in candidatas:
            ponto = (gx * GRADE, gy * GRADE)
            if ponto not in ocupadas and dentro_com_margem(ponto, poligono):
                return ponto
    raise RuntimeError("bairro sem espaço livre para todos os nós; aumente o polígono")


def gerar_layout(ontologia: Ontologia) -> dict:
    nos: dict[str, list[int]] = {}
    for bairro in sorted(ontologia.bairros, key=lambda b: b.id):
        ids = sorted(e.id for e in ontologia.entidades.values() if e.bairro == bairro.id)
        conjunto = set(ids)
        grafo = nx.Graph()
        grafo.add_nodes_from(ids)
        grafo.add_edges_from(
            sorted((r.de, r.para) for r in ontologia.relacoes if r.de in conjunto and r.para in conjunto)
        )
        posicoes = nx.spring_layout(grafo, seed=SEMENTE, k=1.2 / math.sqrt(max(len(ids), 1)), iterations=200)

        xs = [p[0] for p in bairro.poligono]
        ys = [p[1] for p in bairro.poligono]
        x0, x1 = min(xs) + 2 * MARGEM, max(xs) - 2 * MARGEM
        y0, y1 = min(ys) + 2 * MARGEM, max(ys) - 2 * MARGEM

        ocupadas: set[Ponto] = set()
        # Ordem estável: nós mais conectados escolhem célula primeiro.
        for ident in sorted(ids, key=lambda i: (-grafo.degree(i), i)):
            px, py = posicoes[ident]
            alvo = (x0 + (px + 1) / 2 * (x1 - x0), y0 + (py + 1) / 2 * (y1 - y0))
            ponto = _celula_livre(alvo, bairro.poligono, ocupadas)
            ocupadas.add(ponto)
            nos[ident] = [int(ponto[0]), int(ponto[1])]

    pares = Counter(
        tuple(sorted((ontologia.entidades[r.de].bairro, ontologia.entidades[r.para].bairro)))
        for r in ontologia.relacoes
        if ontologia.entidades[r.de].bairro != ontologia.entidades[r.para].bairro
    )
    avenidas = [{"de": a, "para": b, "relacoes": n} for (a, b), n in sorted(pares.items())]

    return {"versao": 1, "grade": GRADE, "nos": dict(sorted(nos.items())), "avenidas": avenidas}


def serializar(layout: dict) -> str:
    return json.dumps(layout, ensure_ascii=False, indent=1) + "\n"


def carregar_layout(pasta: Path = PASTA_PADRAO) -> dict:
    return json.loads((pasta / ARQUIVO_LAYOUT).read_text(encoding="utf-8"))


def main() -> None:
    ontologia = carregar_ontologia()
    layout = gerar_layout(ontologia)
    (PASTA_PADRAO / ARQUIVO_LAYOUT).write_text(serializar(layout), encoding="utf-8")
    print(f"Layout gerado: {len(layout['nos'])} nós, {len(layout['avenidas'])} avenidas.")


if __name__ == "__main__":
    main()
