"""Consultas ao grafo. Único lugar do sistema que fala Cypher.

O agente nunca escreve Cypher: ele faz perguntas de negócio pelas tools,
e cada pergunta vira uma consulta conhecida aqui.
"""

from typing import Any

from neo4j import AsyncDriver, AsyncGraphDatabase

from contexto_mcp import modelos as m

TIPOS_REGRA = [
    "RegraElegibilidade",
    "RegraAdequacao",
    "LimiteAlcada",
    "Politica",
    "Norma",
    "BaseLegal",
    "ExigenciaRegistro",
]
NIVEIS_RISCO = ["baixo", "medio", "alto"]


class EntidadeNaoEncontrada(LookupError):
    pass


def _proveniencia(props: dict) -> m.Proveniencia:
    return m.Proveniencia(
        fonte=props["prov_fonte"],
        data=props["prov_data"],
        responsavel=props["prov_responsavel"],
        confianca=props["prov_confianca"],
    )


def _atributos(props: dict) -> dict[str, Any]:
    return {k.removeprefix("attr_"): v for k, v in sorted(props.items()) if k.startswith("attr_")}


def _estado(props: dict) -> m.Estado | None:
    campos = ("status", "latencia_ms", "custo_estimado", "vigencia_inicio", "vigencia_fim")
    valores = {c: props[c] for c in campos if props.get(c) is not None}
    return m.Estado(**valores) if valores else None


def resumo(props: dict) -> m.EntidadeResumo:
    return m.EntidadeResumo(
        id=props["id"],
        tipo=props["tipo"],
        tipo_exibicao=props["tipo_exibicao"],
        nome=props["nome"],
        bairro=props["bairro"],
    )


def entidade(props: dict) -> m.Entidade:
    return m.Entidade(
        **resumo(props).model_dump(),
        descricao=props["descricao"],
        atributos=_atributos(props),
        estado=_estado(props),
        proveniencia=_proveniencia(props),
    )


def item_estado(props: dict) -> m.ItemEstado:
    return m.ItemEstado(
        entidade=resumo(props), estado=_estado(props) or m.Estado(), proveniencia=_proveniencia(props)
    )


def tempo_texto(segundos: float) -> str:
    if segundos < 3600:
        return f"~{max(1, round(segundos / 60))} min"
    if segundos < 86400:
        return f"~{round(segundos / 3600)} h"
    return f"~{round(segundos / 86400)} dias"


class RepositorioGrafo:
    def __init__(self, uri: str, usuario: str, senha: str) -> None:
        self._credenciais = (uri, usuario, senha)
        self._driver: AsyncDriver | None = None

    @property
    def driver(self) -> AsyncDriver:
        # Criado no primeiro uso, dentro do loop de eventos do servidor.
        if self._driver is None:
            uri, usuario, senha = self._credenciais
            self._driver = AsyncGraphDatabase.driver(uri, auth=(usuario, senha))
        return self._driver

    async def fechar(self) -> None:
        if self._driver is not None:
            await self._driver.close()
            self._driver = None

    async def _consultar(self, cypher: str, **parametros) -> list[dict]:
        resultado = await self.driver.execute_query(cypher, parametros, routing_="r")
        return [r.data() for r in resultado.records]

    async def _no(self, ident: str) -> dict:
        linhas = await self._consultar("MATCH (n:Entidade {id: $id}) RETURN properties(n) AS n", id=ident)
        if not linhas:
            raise EntidadeNaoEncontrada(f"Não existe entidade com id '{ident}' no mapa.")
        return linhas[0]["n"]

    async def buscar(
        self, texto: str | None, tipo: str | None, bairro: str | None, limite: int
    ) -> m.RespostaBusca:
        linhas = await self._consultar(
            """
            MATCH (n:Entidade)
            WHERE ($tipo IS NULL OR n.tipo = $tipo)
              AND ($bairro IS NULL OR n.bairro = $bairro)
              AND ($texto IS NULL
                   OR toLower(n.nome) CONTAINS toLower($texto)
                   OR toLower(n.descricao) CONTAINS toLower($texto)
                   OR n.id CONTAINS toLower($texto))
            RETURN properties(n) AS n ORDER BY n.bairro, n.tipo, n.id
            """,
            texto=texto,
            tipo=tipo,
            bairro=bairro,
        )
        return m.RespostaBusca(total=len(linhas), entidades=[resumo(linha["n"]) for linha in linhas[:limite]])

    async def entidade(self, ident: str) -> m.RespostaEntidade:
        no = await self._no(ident)
        linhas = await self._consultar(
            """
            MATCH (n:Entidade {id: $id})-[r]-(o:Entidade)
            RETURN type(r) AS tipo, startNode(r) = n AS saida, properties(r) AS r, properties(o) AS o
            ORDER BY tipo, o.id
            """,
            id=ident,
        )
        relacoes = [
            m.Relacao(
                tipo=linha["tipo"],
                sentido="saida" if linha["saida"] else "entrada",
                entidade=resumo(linha["o"]),
                atributos=_atributos(linha["r"]),
                proveniencia=_proveniencia(linha["r"]),
            )
            for linha in linhas
        ]
        return m.RespostaEntidade(entidade=entidade(no), relacoes=relacoes)

    async def regras(self, ident: str) -> m.RespostaRegras:
        alvo = await self._no(ident)
        linhas = await self._consultar(
            """
            MATCH p = (a:Entidade {id: $id})-[:EXIGE|REQUER|SUJEITA_A|REGIDO_POR*1..2]->(b:Entidade)
            WHERE b.tipo IN $tipos AND b <> a
            WITH b, p ORDER BY length(p)
            WITH b, collect(p)[0] AS menor
            RETURN properties(b) AS b, length(menor) AS distancia,
                   [r IN relationships(menor) | type(r)] AS caminho
            ORDER BY distancia, b.tipo, b.id
            """,
            id=ident,
            tipos=TIPOS_REGRA,
        )
        regras = [
            m.RegraAplicavel(
                regra=entidade(linha["b"]), distancia=linha["distancia"], caminho=linha["caminho"]
            )
            for linha in linhas
        ]
        return m.RespostaRegras(alvo=resumo(alvo), regras=regras)

    async def estado(self, ids: list[str] | None, tipo: str | None) -> m.RespostaEstado:
        linhas = await self._consultar(
            """
            MATCH (n:Entidade)
            WHERE n.status IS NOT NULL
              AND ($ids IS NULL OR n.id IN $ids)
              AND ($tipo IS NULL OR n.tipo = $tipo)
            RETURN properties(n) AS n ORDER BY n.bairro, n.id
            """,
            ids=ids,
            tipo=tipo,
        )
        return m.RespostaEstado(itens=[item_estado(linha["n"]) for linha in linhas])

    async def proveniencia(self, ident: str, relacionado_a: str | None) -> m.RespostaProveniencia:
        no = await self._no(ident)
        relacoes: list[m.ProvenienciaRelacao] = []
        if relacionado_a:
            await self._no(relacionado_a)
            linhas = await self._consultar(
                """
                MATCH (a:Entidade {id: $a})-[r]-(b:Entidade {id: $b})
                RETURN type(r) AS tipo, startNode(r).id AS de, endNode(r).id AS para, properties(r) AS r
                ORDER BY tipo
                """,
                a=ident,
                b=relacionado_a,
            )
            relacoes = [
                m.ProvenienciaRelacao(
                    tipo=linha["tipo"],
                    de=linha["de"],
                    para=linha["para"],
                    proveniencia=_proveniencia(linha["r"]),
                )
                for linha in linhas
            ]
        return m.RespostaProveniencia(alvo=resumo(no), proveniencia=_proveniencia(no), relacoes=relacoes)

    async def rotas(self, jornada: str, rota: str | None) -> m.RespostaRota:
        no_jornada = await self._no(jornada)
        linhas = await self._consultar(
            """
            MATCH (:Jornada {id: $jornada})-[:TEM_ROTA]->(r:Rota)
            WHERE $rota IS NULL OR r.id = $rota
            MATCH (r)-[pp:PASSA_POR]->(p:Parada)
            OPTIONAL MATCH (p)-[:USA|TOCA]->(u:Entidade)
            WITH r, pp, p, [x IN collect(properties(u)) WHERE x IS NOT NULL] AS usa
            ORDER BY pp.attr_ordem
            WITH r, collect({ordem: pp.attr_ordem, parada: properties(p), usa: usa}) AS paradas
            OPTIONAL MATCH (r)-[:USA]->(api:Entidade)
            RETURN properties(r) AS rota, paradas, [a IN collect(properties(api)) WHERE a IS NOT NULL] AS apis
            ORDER BY rota.id
            """,
            jornada=jornada,
            rota=rota,
        )
        if rota and not linhas:
            raise EntidadeNaoEncontrada(f"A jornada '{jornada}' não tem a rota '{rota}'.")
        return m.RespostaRota(
            jornada=resumo(no_jornada), rotas=[self._montar_rota(linha) for linha in linhas]
        )

    @staticmethod
    def _montar_rota(linha: dict) -> m.Rota:
        rota = linha["rota"]
        paradas = [
            m.ParadaRota(
                ordem=p["ordem"],
                numero=p["parada"].get("attr_numero"),
                id=p["parada"]["id"],
                nome=p["parada"]["nome"],
                bairro=p["parada"]["bairro"],
                tempo_base_s=p["parada"].get("attr_tempo_base_s", 0),
                usa=[item_estado(u) for u in sorted(p["usa"], key=lambda u: u["id"])],
            )
            for p in linha["paradas"]
        ]
        apis = [item_estado(a) for a in sorted(linha["apis"], key=lambda a: a["id"])]

        # Tudo que a rota percorre, sem repetir: é aqui que o trânsito pesa.
        percorridos = {i.entidade.id: i for p in paradas for i in p.usa} | {i.entidade.id: i for i in apis}
        latencia_s = sum((i.estado.latencia_ms or 0) for i in percorridos.values()) / 1000
        tempo = sum(p.tempo_base_s for p in paradas) + rota.get("attr_tempo_adicional_s", 0) + latencia_s
        custo = sum((i.estado.custo_estimado or 0) for i in percorridos.values())

        alertas = [
            m.Alerta(
                entidade=i.entidade,
                status=i.estado.status,
                mensagem=(
                    f"{i.entidade.nome} está fora do ar: trecho interditado."
                    if i.estado.status == "fora"
                    else f"{i.entidade.nome} está degradado: espere atraso."
                ),
            )
            for i in sorted(percorridos.values(), key=lambda i: i.entidade.id)
            if i.estado.status in ("degradado", "fora")
        ]
        nivel = NIVEIS_RISCO.index(rota.get("attr_risco_base", "baixo"))
        if any(a.status == "degradado" for a in alertas):
            nivel = min(nivel + 1, 2)
        bloqueada = any(a.status == "fora" for a in alertas)
        if bloqueada:
            nivel = 2

        return m.Rota(
            id=rota["id"],
            nome=rota["nome"],
            descricao=rota["descricao"],
            criterio=rota.get("attr_criterio", ""),
            paradas=paradas,
            apis=apis,
            estimativa=m.Estimativa(
                tempo_s=round(tempo),
                tempo_texto=tempo_texto(tempo),
                custo_operacional=round(custo, 2),
                risco=NIVEIS_RISCO[nivel],
                premio_anual_referencia=rota.get("attr_premio_anual_referencia"),
                bloqueada=bloqueada,
            ),
            alertas=alertas,
        )

    async def mapa(self) -> dict:
        nos = await self._consultar(
            """
            MATCH (n:Entidade)
            RETURN n.id AS id, n.tipo AS tipo, n.tipo_exibicao AS tipo_exibicao, n.nome AS nome,
                   n.bairro AS bairro, n.x AS x, n.y AS y, n.status AS status
            ORDER BY id
            """
        )
        arestas = await self._consultar(
            "MATCH (a:Entidade)-[r]->(b:Entidade) "
            "RETURN a.id AS de, type(r) AS tipo, b.id AS para ORDER BY de, tipo, para"
        )
        return {"nos": nos, "arestas": arestas}
