"""Seed do grafo: apaga tudo e recarrega o estado-base a partir da ontologia.

Roda a cada `docker compose up` (serviço `seed`), para todo ensaio começar
do mesmo ponto. Uso: python -m contexto_mcp.seed
"""

import logging
import sys
from itertools import groupby

from neo4j import Driver, GraphDatabase

from bussola_comum.logs import configurar_logs
from contexto_mcp.config import Config
from contexto_mcp.layout import carregar_layout
from contexto_mcp.ontologia import Entidade, Ontologia, Proveniencia, Relacao, carregar_ontologia

log = logging.getLogger("seed")


def _proveniencia(p: Proveniencia) -> dict:
    return {
        "prov_fonte": p.fonte,
        "prov_data": p.data.isoformat(),
        "prov_responsavel": p.responsavel,
        "prov_confianca": p.confianca,
    }


def _atributos(atributos: dict) -> dict:
    # O Neo4j não guarda listas vazias de forma útil; elas simplesmente não entram.
    return {f"attr_{k}": v for k, v in atributos.items() if v != []}


def propriedades_no(e: Entidade, ontologia: Ontologia, posicao: list[int]) -> dict:
    props = {
        "id": e.id,
        "tipo": e.tipo,
        "tipo_exibicao": ontologia.tipos[e.tipo].exibicao,
        "nome": e.nome,
        "descricao": e.descricao,
        "bairro": e.bairro,
        "x": posicao[0],
        "y": posicao[1],
        **_proveniencia(e.proveniencia),
        **_atributos(e.atributos),
    }
    if e.estado:
        estado = {
            "status": e.estado.status,
            "latencia_ms": e.estado.latencia_ms,
            "custo_estimado": e.estado.custo_estimado,
        }
        if e.estado.vigencia:
            estado["vigencia_inicio"] = e.estado.vigencia.inicio.isoformat()
            if e.estado.vigencia.fim:
                estado["vigencia_fim"] = e.estado.vigencia.fim.isoformat()
        props.update({k: v for k, v in estado.items() if v is not None})
    return props


def propriedades_relacao(r: Relacao) -> dict:
    return {"tipo": r.tipo, **_proveniencia(r.proveniencia), **_atributos(r.atributos)}


def validar_layout(ontologia: Ontologia, layout: dict) -> None:
    faltam = set(ontologia.entidades) - set(layout["nos"])
    sobram = set(layout["nos"]) - set(ontologia.entidades)
    if faltam or sobram:
        raise SystemExit(
            "Layout desatualizado em relação à ontologia.\n"
            "Rode ./scripts/gerar-layout.sh e versione o resultado.\n"
            f"  sem posição: {sorted(faltam)}\n  sobrando: {sorted(sobram)}"
        )


def aplicar_seed(driver: Driver, ontologia: Ontologia, layout: dict) -> tuple[int, int]:
    validar_layout(ontologia, layout)

    # Os rótulos e tipos de relação vêm do esquema validado, nunca de entrada externa.
    entidades = sorted(ontologia.entidades.values(), key=lambda e: e.tipo)
    relacoes = sorted(ontologia.relacoes, key=lambda r: r.tipo)

    def escrever(tx) -> None:
        tx.run("MATCH (n) DETACH DELETE n")
        for tipo, grupo in groupby(entidades, key=lambda e: e.tipo):
            linhas = [propriedades_no(e, ontologia, layout["nos"][e.id]) for e in grupo]
            tx.run(f"UNWIND $linhas AS l CREATE (n:Entidade:`{tipo}`) SET n = l", linhas=linhas)
        for tipo, grupo in groupby(relacoes, key=lambda r: r.tipo):
            linhas = [{"de": r.de, "para": r.para, "props": propriedades_relacao(r)} for r in grupo]
            tx.run(
                "UNWIND $linhas AS l "
                "MATCH (a:Entidade {id: l.de}) MATCH (b:Entidade {id: l.para}) "
                f"CREATE (a)-[r:`{tipo}`]->(b) SET r = l.props",
                linhas=linhas,
            )

    with driver.session() as sessao:
        sessao.run(
            "CREATE CONSTRAINT entidade_id IF NOT EXISTS FOR (n:Entidade) REQUIRE n.id IS UNIQUE"
        ).consume()
        sessao.execute_write(escrever)
        nos = sessao.run("MATCH (n:Entidade) RETURN count(n) AS n").single()["n"]
        arestas = sessao.run("MATCH ()-[r]->() RETURN count(r) AS n").single()["n"]
    return nos, arestas


def main() -> int:
    config = Config(servico_nome="seed")
    configurar_logs("seed", config.log_level)
    ontologia = carregar_ontologia()
    layout = carregar_layout()
    with GraphDatabase.driver(config.neo4j_uri, auth=(config.neo4j_user, config.neo4j_password)) as driver:
        driver.verify_connectivity()
        nos, arestas = aplicar_seed(driver, ontologia, layout)
    log.info("Grafo recarregado: %d nós e %d relações, em %d bairros.", nos, arestas, len(ontologia.bairros))
    return 0


if __name__ == "__main__":
    sys.exit(main())
