import json
from typing import Annotated

import anyio
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from neo4j import AsyncGraphDatabase, GraphDatabase
from pydantic import Field
from starlette.requests import Request
from starlette.responses import JSONResponse

from bussola_comum.mcp_servidor import criar_servidor_mcp
from bussola_comum.saude import Checagem
from contexto_mcp import modelos as m
from contexto_mcp.config import NOME, Config
from contexto_mcp.grafo import EntidadeNaoEncontrada, RepositorioGrafo
from contexto_mcp.layout import carregar_layout
from contexto_mcp.ontologia import carregar_ontologia
from contexto_mcp.seed import aplicar_seed

JORNADA_PADRAO = "contratacao-seguro-residencial"


def checar_grafo(config: Config) -> Checagem:
    async def checar() -> bool:
        async with AsyncGraphDatabase.driver(
            config.neo4j_uri,
            auth=(config.neo4j_user, config.neo4j_password),
            connection_timeout=2,
        ) as driver:
            await driver.verify_connectivity()
        return True

    return checar


def criar_servidor(checagens: dict[str, Checagem] | None = None, config: Config | None = None) -> MCPServer:
    config = config or Config()
    if checagens is None:
        checagens = {"graph": checar_grafo(config)}
    mcp = criar_servidor_mcp(
        NOME,
        "Camada de contexto: ontologia, estado vivo, regras e proveniência",
        checagens,
    )
    repo = RepositorioGrafo(config.neo4j_uri, config.neo4j_user, config.neo4j_password)
    ontologia = carregar_ontologia()
    layout = carregar_layout()

    async def _executar(consulta):
        try:
            return await consulta
        except EntidadeNaoEncontrada as erro:
            raise ToolError(str(erro)) from erro

    @mcp.tool(description="Busca entidades do mapa por texto, tipo ou bairro. Devolve um resumo de cada uma.")
    async def buscar_entidades(
        texto: Annotated[str | None, Field(description="Trecho do nome, da descrição ou do id.")] = None,
        tipo: Annotated[str | None, Field(description="Tipo da ontologia, por exemplo Seguradora.")] = None,
        bairro: Annotated[
            str | None,
            Field(description="Bairro: cliente, produtos, risco, regulatorio, parceiros ou canais."),
        ] = None,
        limite: Annotated[int, Field(ge=1, le=50)] = 20,
    ) -> m.RespostaBusca:
        return await _executar(repo.buscar(texto, tipo, bairro, limite))

    @mcp.tool(
        description="Detalha uma entidade: atributos, estado vivo, proveniência e relações com vizinhos."
    )
    async def consultar_entidade(id: str) -> m.RespostaEntidade:
        return await _executar(repo.entidade(id))

    @mcp.tool(
        description=(
            "Lista as regras, políticas, limites de alçada, normas e bases legais "
            "que se aplicam a uma entidade "
            "(produto, parada, área de risco...), com o caminho no grafo e a proveniência de cada uma."
        )
    )
    async def consultar_regras(id: str) -> m.RespostaRegras:
        return await _executar(repo.regras(id))

    @mcp.tool(description="Estado vivo (o trânsito): status, latência e custo. Filtre por ids ou por tipo.")
    async def consultar_estado(ids: list[str] | None = None, tipo: str | None = None) -> m.RespostaEstado:
        return await _executar(repo.estado(ids, tipo))

    @mcp.tool(
        description=(
            "Origem de uma informação: fonte, data, responsável e confiança de uma entidade. "
            "Com `relacionado_a`, inclui a proveniência das relações entre as duas entidades."
        )
    )
    async def consultar_proveniencia(id: str, relacionado_a: str | None = None) -> m.RespostaProveniencia:
        return await _executar(repo.proveniencia(id, relacionado_a))

    @mcp.tool(
        description=(
            "Rotas de uma jornada, com paradas em ordem, o que cada parada usa "
            "e a estimativa de tempo, custo e "
            "risco calculada com o estado vivo atual. Alertas mostram trechos degradados ou interditados."
        )
    )
    async def consultar_rota(jornada: str = JORNADA_PADRAO, rota: str | None = None) -> m.RespostaRota:
        return await _executar(repo.rotas(jornada, rota))

    @mcp.resource(
        "contexto://mapa",
        name="mapa",
        description=(
            "Mapa completo da cidade para desenho: bairros, rio, avenidas, nós com posição e estado, arestas."
        ),
        mime_type="application/json",
    )
    async def mapa() -> str:
        grafo = await repo.mapa()
        return json.dumps(
            {
                "mundo": ontologia.mundo,
                "bairros": [b.model_dump() for b in ontologia.bairros],
                "rio": ontologia.rio,
                "avenidas": layout["avenidas"],
                **grafo,
            },
            ensure_ascii=False,
        )

    registrar_rotas_internas(mcp, repo, config, set(ontologia.tipos_relacao))
    return mcp


def registrar_rotas_internas(mcp: MCPServer, repo: RepositorioGrafo, config: Config, tipos: set[str]) -> None:
    """Rotas HTTP usadas só pelo simulador para mudar o estado vivo do grafo.

    Não são tools MCP: o gateway não as enxerga e o agente não as alcança.
    """

    def autorizado(request: Request) -> JSONResponse | None:
        if not config.simulador_token:
            return JSONResponse(
                {"erro": "Rotas internas desligadas (SIMULADOR_TOKEN vazio)."}, status_code=503
            )
        if request.headers.get("authorization") != f"Bearer {config.simulador_token}":
            return JSONResponse({"erro": "Token do simulador inválido ou ausente."}, status_code=401)
        return None

    @mcp.custom_route("/interno/estado", methods=["POST"], include_in_schema=False)
    async def aplicar_estado(request: Request) -> JSONResponse:
        if negado := autorizado(request):
            return negado
        corpo = await request.json()
        try:
            alterados = await repo.aplicar_efeitos(corpo.get("efeitos", []), tipos)
        except EntidadeNaoEncontrada as erro:
            return JSONResponse({"erro": str(erro)}, status_code=404)
        except ValueError as erro:
            return JSONResponse({"erro": str(erro)}, status_code=400)
        return JSONResponse({"alterados": alterados})

    @mcp.custom_route("/interno/reset", methods=["POST"], include_in_schema=False)
    async def reset(request: Request) -> JSONResponse:
        if negado := autorizado(request):
            return negado

        def reaplicar_seed() -> tuple[int, int]:
            with GraphDatabase.driver(
                config.neo4j_uri, auth=(config.neo4j_user, config.neo4j_password)
            ) as driver:
                return aplicar_seed(driver, carregar_ontologia(), carregar_layout())

        nos, arestas = await anyio.to_thread.run_sync(reaplicar_seed)
        return JSONResponse({"nos": nos, "relacoes": arestas})
