"""Layout fixo da cidade, calculado uma vez e versionado em ontologia/layout.json.

A cidade é uma grade de quadras cortada por ruas (as avenidas são mais largas). Cada bairro
é uma região de quadras. Cada quadra tem lotes, e cada lugar do grafo (um sistema, um cliente,
uma regra) ocupa um lote do seu bairro, com a porta voltada para a rua: é até ela que o agente
anda no mapa. Lugares ligados ficam perto (layout de forças, semente fixa). As paradas da
jornada viram placas nas esquinas. As quadras que o rio cruza viram água.

Uso: ./scripts/gerar-layout.sh (roda `python -m contexto_mcp.layout` no container).
"""

import json
import math
import zlib
from pathlib import Path

import networkx as nx

from contexto_mcp.ontologia import PASTA_PADRAO, Ontologia, carregar_ontologia

ARQUIVO_LAYOUT = "layout.json"
VERSAO = 2
FOLGA_ENTRE_LOTES = 4
DISTANCIA_DO_RIO = 40  # quadras com o centro mais perto que isso do rio viram água
FOLGA_DE_LOTES = 1.4  # num bairro com poucos lugares, eles ocupam a área de ~1,4 lote cada
SEMENTE = 7
# Lugares que não são construções: as paradas viram placas; rotas e jornada não aparecem.
TIPOS_SEM_LOTE = {"Parada", "Rota", "Jornada"}

Ponto = tuple[float, float]


def _r(valor: float) -> float:
    return round(valor, 1)


def dentro(ponto: Ponto, retangulo: list[float]) -> bool:
    x0, y0, x1, y1 = retangulo
    return x0 <= ponto[0] <= x1 and y0 <= ponto[1] <= y1


def _distancia_ao_segmento(p: Ponto, a: Ponto, b: Ponto) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    t = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / (dx * dx + dy * dy or 1)))
    return math.dist(p, (a[0] + t * dx, a[1] + t * dy))


def _distancia_ao_rio(p: Ponto, rio: list[Ponto]) -> float:
    return min(
        (_distancia_ao_segmento(p, a, b) for a, b in zip(rio, rio[1:], strict=False)), default=math.inf
    )


class Grade:
    """A geometria da cidade: linhas das ruas, quadras e lotes."""

    def __init__(self, ontologia: Ontologia) -> None:
        c = ontologia.cidade
        self.colunas, self.linhas = c["colunas"], c["linhas"]
        self.lotes_x, self.lotes_y = c["lotes_por_quadra"]
        self.rua, self.avenida = c["rua"], c["avenida"]
        self.av_v, self.av_h = set(c["avenidas_verticais"]), set(c["avenidas_horizontais"])
        largura, altura = ontologia.mundo["largura"], ontologia.mundo["altura"]
        self.xs = [_r(k * largura / self.colunas) for k in range(self.colunas + 1)]
        self.ys = [_r(k * altura / self.linhas) for k in range(self.linhas + 1)]

    def largura_v(self, k: int) -> int:
        return self.avenida if k in self.av_v else self.rua

    def largura_h(self, k: int) -> int:
        return self.avenida if k in self.av_h else self.rua

    def quadra(self, i: int, j: int) -> list[float]:
        """Retângulo [x0, y0, x1, y1] da quadra (coluna i, linha j), entre as ruas."""
        return [
            _r(self.xs[i] + self.largura_v(i) / 2),
            _r(self.ys[j] + self.largura_h(j) / 2),
            _r(self.xs[i + 1] - self.largura_v(i + 1) / 2),
            _r(self.ys[j + 1] - self.largura_h(j + 1) / 2),
        ]

    def lotes(self, i: int, j: int) -> list[dict]:
        """Os lotes da quadra, cada um com o centro e a porta na rua de cima ou de baixo."""
        x0, y0, x1, y1 = self.quadra(i, j)
        lw = (x1 - x0 - (self.lotes_x - 1) * FOLGA_ENTRE_LOTES) / self.lotes_x
        lh = (y1 - y0 - (self.lotes_y - 1) * FOLGA_ENTRE_LOTES) / self.lotes_y
        saida = []
        for b in range(self.lotes_y):
            for a in range(self.lotes_x):
                cx = x0 + a * (lw + FOLGA_ENTRE_LOTES) + lw / 2
                cy = y0 + b * (lh + FOLGA_ENTRE_LOTES) + lh / 2
                # A porta dá para a rua mais próxima na vertical: a de cima ou a de baixo da quadra.
                rua_y = self.ys[j] if b < self.lotes_y / 2 else self.ys[j + 1]
                saida.append({"centro": (_r(cx), _r(cy)), "porta": (_r(cx), rua_y)})
        return saida

    def tamanho_do_lote(self) -> list[float]:
        x0, y0, x1, y1 = self.quadra(1, 1)
        lw = (x1 - x0 - (self.lotes_x - 1) * FOLGA_ENTRE_LOTES) / self.lotes_x
        lh = (y1 - y0 - (self.lotes_y - 1) * FOLGA_ENTRE_LOTES) / self.lotes_y
        return [_r(lw), _r(lh)]


def gerar_layout(ontologia: Ontologia) -> dict:
    grade = Grade(ontologia)
    rio = [tuple(p) for p in ontologia.rio]
    regioes = {b.id: b.quadras for b in ontologia.bairros}

    quadras = []
    for j in range(grade.linhas):
        for i in range(grade.colunas):
            bairro = next(b for b, (c0, r0, c1, r1) in regioes.items() if c0 <= i < c1 and r0 <= j < r1)
            ret = grade.quadra(i, j)
            centro = ((ret[0] + ret[2]) / 2, (ret[1] + ret[3]) / 2)
            agua = _distancia_ao_rio(centro, rio) < DISTANCIA_DO_RIO
            quadras.append({"coluna": i, "linha": j, "bairro": bairro, "agua": agua, "retangulo": ret})

    nos: dict[str, list[float]] = {}
    portas: dict[str, list[float]] = {}
    esquinas_usadas: set[Ponto] = set()
    for bairro in sorted(ontologia.bairros, key=lambda b: b.id):
        c0, r0, c1, r1 = bairro.quadras
        x0, y0, x1, y1 = grade.xs[c0], grade.ys[r0], grade.xs[c1], grade.ys[r1]
        lotes = [
            lote
            for q in quadras
            if q["bairro"] == bairro.id and not q["agua"]
            for lote in grade.lotes(q["coluna"], q["linha"])
        ]
        entidades = [e for e in ontologia.entidades.values() if e.bairro == bairro.id]
        construcoes = sorted(e.id for e in entidades if e.tipo not in TIPOS_SEM_LOTE)
        if len(construcoes) > len(lotes):
            raise RuntimeError(f"o bairro {bairro.id} tem {len(construcoes)} lugares e só {len(lotes)} lotes")

        conjunto = set(construcoes)
        grafo = nx.Graph()
        grafo.add_nodes_from(construcoes)
        grafo.add_edges_from(
            sorted((r.de, r.para) for r in ontologia.relacoes if r.de in conjunto and r.para in conjunto)
        )
        posicoes = nx.spring_layout(
            grafo, seed=SEMENTE, k=1.2 / math.sqrt(max(len(construcoes), 1)), iterations=200
        )
        livres = list(lotes)
        # Bairro com poucos lugares: as construções se juntam em volta do centro da terra firme,
        # e os lotes da borda viram praças (em vez de construções soltas pelo bairro todo).
        terra = (
            sum(lote["centro"][0] for lote in lotes) / len(lotes),
            sum(lote["centro"][1] for lote in lotes) / len(lotes),
        )
        aperto = min(1.0, math.sqrt(len(construcoes) * FOLGA_DE_LOTES / len(lotes)))
        # Ordem estável: os lugares mais conectados escolhem lote primeiro.
        for ident in sorted(construcoes, key=lambda i: (-grafo.degree(i), i)):
            px, py = posicoes[ident]
            bruto = (x0 + (px + 1) / 2 * (x1 - x0), y0 + (py + 1) / 2 * (y1 - y0))
            alvo = (terra[0] + (bruto[0] - terra[0]) * aperto, terra[1] + (bruto[1] - terra[1]) * aperto)
            lote = min(livres, key=lambda lote: (math.dist(lote["centro"], alvo), lote["centro"]))
            livres.remove(lote)
            nos[ident] = list(lote["centro"])
            portas[ident] = list(lote["porta"])

        # Paradas: placas nas esquinas do bairro, a partir do centro, sem repetir esquina.
        centro = ((x0 + x1) / 2, (y0 + y1) / 2)
        esquinas = sorted(
            (
                (grade.xs[k], grade.ys[m])
                for k in range(max(c0, 1), min(c1, grade.colunas - 1) + 1)
                for m in range(max(r0, 1), min(r1, grade.linhas - 1) + 1)
            ),
            key=lambda p: (math.dist(p, centro), p),
        )
        paradas = sorted(
            (e for e in entidades if e.tipo == "Parada"),
            key=lambda e: (e.atributos.get("numero") or 99, e.id),
        )
        for parada in paradas:
            esquina = next(p for p in esquinas if p not in esquinas_usadas)
            esquinas_usadas.add(esquina)
            nos[parada.id] = list(esquina)
            portas[parada.id] = list(esquina)
        # Rotas e jornada não são lugares: ficam no centro do bairro, sem construção.
        for e in entidades:
            if e.tipo in TIPOS_SEM_LOTE - {"Parada"}:
                nos[e.id] = [_r(centro[0]), _r(centro[1])]

    return {
        "versao": VERSAO,
        "cidade": {
            "colunas": grade.colunas,
            "linhas": grade.linhas,
            "xs": grade.xs,
            "ys": grade.ys,
            "rua": grade.rua,
            "avenida": grade.avenida,
            "avenidas_verticais": sorted(grade.av_v),
            "avenidas_horizontais": sorted(grade.av_h),
            "lote": grade.tamanho_do_lote(),
        },
        "regioes": {
            b: [grade.xs[c0], grade.ys[r0], grade.xs[c1], grade.ys[r1]]
            for b, (c0, r0, c1, r1) in sorted(regioes.items())
        },
        "quadras": quadras,
        "nos": dict(sorted(nos.items())),
        "portas": dict(sorted(portas.items())),
    }


# Estilo da construção de cada lugar: vem do bairro (e, em alguns, do tipo).
# A forma de cada construção vem do tipo (e, em alguns casos, do id). Tipos sem
# forma própria ganham uma variante do bairro, sorteada com semente pelo id:
# o bairro tem cara de bairro, mas as construções não são todas iguais.
ESTILO_POR_ID = {
    "canal-app": "torre",
    "canal-internet-banking": "torre",
    "canal-agencia": "agencia",
    "canal-central": "escritorio",
    "sistema-crm": "sede",
    "sistema-core-bancario": "sede",
    "sistema-motor-risco": "central",
    "sistema-cofre-consentimentos": "central",
    "sistema-registro-operacoes": "central",
    "sistema-gateway-pagamentos": "datacenter",
    "sistema-vistoria": "oficina",
}
ESTILO_POR_TIPO: dict[str, str | None] = {
    "Cliente": "casa",
    "Politica": "publico",
    "BaseLegal": "publico",
    "Norma": "cupula",
    "ProdutoSeguro": "shopping",
    "Seguradora": "torre",
    "ApiCotacao": "tecnico",
    "SLA": "tecnico",
    "Especialista": "escritorio",
    "Fila": "escritorio",
    "MeioPagamento": "agencia",
    "ApiEmissao": "cartorio",
    "Parada": "placa",
    "Rota": None,
    "Jornada": None,
}
VARIANTES_DO_BAIRRO = {
    "cliente": ("casa", "sobrado", "residencial"),
    "governanca": ("escritorio", "publico", "escritorio"),
    "produtos": ("loja", "galeria", "loja"),
    "parceiros": ("escritorio", "tecnico"),
    "pagamentos": ("agencia", "escritorio"),
}
# Imóveis: a forma segue o que a cliente tem (apartamento, casa, sobrado...).
IMOVEL = (("apartamento", "residencial"), ("cobertura", "residencial"), ("sobrado", "sobrado"))


def estilo(ident: str, tipo: str, bairro: str, nome: str = "") -> str | None:
    if ident in ESTILO_POR_ID:
        return ESTILO_POR_ID[ident]
    if tipo in ESTILO_POR_TIPO:
        return ESTILO_POR_TIPO[tipo]
    if tipo == "Imovel":
        return next((forma for chave, forma in IMOVEL if chave in nome.lower()), "casa")
    variantes = VARIANTES_DO_BAIRRO.get(bairro, ("escritorio",))
    return variantes[zlib.crc32(ident.encode()) % len(variantes)]


def serializar(layout: dict) -> str:
    return json.dumps(layout, ensure_ascii=False, indent=1) + "\n"


def carregar_layout(pasta: Path = PASTA_PADRAO) -> dict:
    return json.loads((pasta / ARQUIVO_LAYOUT).read_text(encoding="utf-8"))


def main() -> None:
    ontologia = carregar_ontologia()
    layout = gerar_layout(ontologia)
    (PASTA_PADRAO / ARQUIVO_LAYOUT).write_text(serializar(layout), encoding="utf-8")
    construcoes = sum(1 for e in ontologia.entidades.values() if e.tipo not in TIPOS_SEM_LOTE)
    lotes = sum(1 for q in layout["quadras"] if not q["agua"]) * 4
    print(f"Layout gerado: {construcoes} construções em {lotes} lotes, {len(layout['quadras'])} quadras.")


if __name__ == "__main__":
    main()
