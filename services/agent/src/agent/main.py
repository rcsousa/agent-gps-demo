"""API do agente.

Regra de arquitetura: o agente conhece apenas o mcp-gateway (GATEWAY_URL)
e o barramento de eventos (BUS_URL). Nenhum servidor de domínio aparece aqui.
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from redis.asyncio import Redis
from sse_starlette.sse import EventSourceResponse

from agent import placar
from agent.catalogo import Catalogo, NaoEncontrado
from agent.config import Config
from agent.custos import precos_por_milhao
from agent.entrega import (
    CABECALHOS_SSE,
    PREENCHIMENTO,
    cursor_valido,
    lote_da_execucao,
    lote_da_gravacao,
)
from agent.execucao import MODOS, Motor
from agent.gravacoes import GravacaoInvalida, Gravacoes, esperas
from agent.llm.fabrica import PROVEDORES
from agent.mapa import EntidadeNaoEncontrada, Mapa
from bussola_comum.barramento import checar_barramento
from bussola_comum.cliente_mcp import conectar
from bussola_comum.eventos import STREAM, PublicadorRedis, decodificar
from bussola_comum.regras import caso_de
from bussola_comum.saude import Checagem, rota_saude

log = logging.getLogger("agent")


class PedidoExecucao(BaseModel):
    modo: str
    provedor: str | None = None
    pedido: str | None = None
    canal: str | None = None
    modelo: str | None = None
    # Incidentes ativos no mundo quando a viagem começou (o web sabe pelo simulador): o caso do placar.
    incidentes: list[str] = []


class PedidoDeGravacao(BaseModel):
    execucao: str
    nome: str | None = None  # padrão: cena-<n> ou o id da execução
    cena: str | None = None
    # Incidentes ativos durante a viagem: o replay os reaplica pelo simulador, para o mapa bater.
    incidentes: list[str] = []


class EscolhaDeModelo(BaseModel):
    modelo: str


class RespostaCliente(BaseModel):
    texto: str


def criar_app(
    config: Config | None = None,
    checagens: dict[str, Checagem] | None = None,
    motor: Motor | None = None,
    redis: Redis | None = None,
) -> FastAPI:
    config = config or Config()
    if checagens is None:
        checagens = {"bus": checar_barramento(config.bus_url)}
    if not config.llm_configurado:
        log.warning("Chave do provedor de LLM (%s) ausente: só o provedor roteiro roda.", config.llm_provider)
    redis = redis or Redis.from_url(config.bus_url, decode_responses=True)
    motor = motor or Motor(
        config,
        redis,
        PublicadorRedis(redis, "agent"),
        lambda: conectar(f"{config.gateway_url}/mcp", config.gateway_token),
    )

    async def saude_do_gateway() -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=4) as cliente:
            resposta = await cliente.get(
                f"{config.gateway_url}/saude/servicos",
                headers={"Authorization": f"Bearer {config.gateway_token}"},
            )
        resposta.raise_for_status()
        return resposta.json()

    catalogo = Catalogo(
        lambda: conectar(f"{config.gateway_url}/mcp", config.gateway_token), redis, saude_do_gateway
    )

    mapa = Mapa(lambda: conectar(f"{config.gateway_url}/mcp", config.gateway_token))

    app = FastAPI(title="agent")
    app.add_api_route("/saude", rota_saude(config.servico_nome, checagens), methods=["GET"])

    @app.get("/api/status")
    async def status() -> dict:
        """Estado da plataforma visto pelo agente: só pelo gateway."""
        gateway, servicos, ferramentas, ferramentas_fora, skills, prompts = "fora", [], 0, 0, 0, 0
        try:
            corpo = await saude_do_gateway()
            gateway, servicos = "ok", corpo["servicos"]
            ferramentas, ferramentas_fora = corpo.get("ferramentas", 0), corpo.get("ferramentas_fora", 0)
            skills, prompts = corpo.get("skills", 0), corpo.get("prompts", 0)
        except httpx.HTTPError:
            pass

        try:
            barramento = "ok" if await checagens["bus"]() else "fora"
        except Exception:
            barramento = "fora"

        return {
            "gateway": gateway,
            "barramento": barramento,
            "llm": {
                "provedor": config.llm_provider,
                "plataforma": config.anthropic_plataforma if config.llm_provider == "anthropic" else None,
                "modelo": await motor.modelo_atual()
                if config.llm_provider == "anthropic"
                else config.azure_openai_deployment,
                "configurado": config.llm_configurado,
                "modelos": config.modelos_anthropic if config.llm_provider == "anthropic" else [],
            },
            "servicos": servicos,
            "ferramentas": ferramentas,
            "ferramentas_fora": ferramentas_fora,
            "skills": skills,
            "prompts": prompts,
        }

    # --- Mapa da cidade (Modo Mapa) ------------------------------------------------

    @app.get("/api/mapa")
    async def ver_mapa() -> dict:
        """A cidade desenhada a partir do grafo, com o trânsito (status vivo) de cada nó."""
        try:
            return await mapa.cidade()
        except Exception as erro:  # noqa: BLE001
            raise HTTPException(503, "A camada de contexto não respondeu.") from erro

    @app.get("/api/mapa/rotas")
    async def ver_rotas() -> dict:
        try:
            return await mapa.rotas()
        except Exception as erro:  # noqa: BLE001
            raise HTTPException(503, "As rotas não puderam ser consultadas.") from erro

    @app.get("/api/mapa/entidade/{ident}")
    async def ver_entidade(ident: str) -> dict:
        try:
            return await mapa.entidade(ident)
        except EntidadeNaoEncontrada as erro:
            raise HTTPException(404, str(erro)) from erro

    # --- Modelo das próximas execuções (escolhido no painel) ---------------------------

    @app.get("/api/llm/modelo")
    async def ver_modelo() -> dict:
        """O modelo atual e os permitidos, com o preço por milhão de tokens de cada um."""
        return {
            "modelo": await motor.modelo_atual(),
            "padrao": config.anthropic_model,
            "modelos": [{"id": m, "precos": precos_por_milhao(config, m)} for m in config.modelos_anthropic],
            "cache": {"leitura": config.cache_leitura_fator, "escrita": config.cache_escrita_fator},
        }

    @app.put("/api/llm/modelo")
    async def escolher_modelo(escolha: EscolhaDeModelo) -> dict:
        try:
            await motor.definir_modelo(escolha.modelo)
        except ValueError as erro:
            raise HTTPException(400, str(erro)) from erro
        return await ver_modelo()

    # --- Catálogo (dashboard de status) ---------------------------------------------

    @app.get("/api/catalogo")
    async def ver_catalogo() -> dict:
        """Tools, skills e prompts do gateway, com contrato e quem usa o quê."""
        try:
            return await catalogo.montar()
        except (httpx.HTTPError, OSError) as erro:
            raise HTTPException(503, "O gateway não respondeu.") from erro

    @app.get("/api/catalogo/fonte")
    async def ver_fonte(uri: str = Query(...)) -> dict:
        """O código de uma tool ou prompt, servido pelo próprio servidor MCP."""
        try:
            return await catalogo.fonte(uri)
        except ValueError as erro:
            raise HTTPException(400, str(erro)) from erro
        except NaoEncontrado as erro:
            raise HTTPException(404, str(erro)) from erro

    @app.get("/api/catalogo/skill")
    async def ver_arquivo_de_skill(uri: str = Query(...)) -> dict:
        """Um arquivo da skill, com tamanho e digest verificados."""
        try:
            return await catalogo.arquivo_de_skill(uri)
        except ValueError as erro:
            raise HTTPException(400, str(erro)) from erro
        except NaoEncontrado as erro:
            raise HTTPException(404, str(erro)) from erro

    @app.get("/api/catalogo/prompt/{nome}/previa")
    async def ver_previa(nome: str) -> dict:
        try:
            return await catalogo.previa_de_prompt(nome)
        except NaoEncontrado as erro:
            raise HTTPException(404, str(erro)) from erro

    @app.get("/api/catalogo/chamadas")
    async def ver_chamadas(
        tool: str | None = None, prompt: str | None = None, skill: str | None = None
    ) -> list:
        if not (tool or prompt or skill):
            raise HTTPException(400, "Informe tool, prompt ou skill.")
        return await catalogo.chamadas(tool=tool, prompt=prompt, skill=skill)

    # --- Execuções ------------------------------------------------------------------

    @app.post("/api/execucoes", status_code=201)
    async def iniciar(pedido: PedidoExecucao) -> dict:
        if pedido.modo not in MODOS:
            raise HTTPException(400, f"Modo desconhecido: {pedido.modo}. Use um de: {', '.join(MODOS)}.")
        if pedido.provedor and pedido.provedor not in PROVEDORES:
            raise HTTPException(
                400, f"Provedor desconhecido: {pedido.provedor}. Use um de: {', '.join(PROVEDORES)}."
            )
        if pedido.canal:
            try:
                canais = await motor.canais()
            except Exception:  # noqa: BLE001
                canais = None  # Gateway sem resposta: a execução segue com a persona embutida.
            if canais is not None and pedido.canal not in canais:
                raise HTTPException(
                    400, f"Canal desconhecido: {pedido.canal}. Use um de: {', '.join(canais)}."
                )
        if pedido.modelo:
            provedor = pedido.provedor or config.llm_provider
            if provedor != "anthropic":
                raise HTTPException(400, "A escolha de modelo vale só para o provedor anthropic.")
            permitidos = config.modelos_anthropic
            if pedido.modelo not in permitidos:
                raise HTTPException(
                    400, f"Modelo não permitido: {pedido.modelo}. Use um de: {', '.join(permitidos)}."
                )
        execucao = await motor.iniciar(
            pedido.modo,
            pedido.provedor,
            pedido.pedido,
            pedido.canal,
            pedido.modelo,
            caso_de(pedido.incidentes),
        )
        return {
            "id": execucao.id,
            "modo": execucao.modo,
            "canal": execucao.canal,
            "provedor": execucao.provedor,
        }

    @app.get("/api/execucoes")
    async def listar() -> list[dict]:
        return await motor.listar()

    @app.get("/api/placar")
    async def ver_placar() -> dict:
        """Regras cumpridas, tempo e custo: a sessão da demo e a referência do experimento."""
        return placar.montar(await motor.listar())

    @app.get("/api/execucoes/{ident}")
    async def obter(ident: str) -> dict:
        execucao = await motor.obter(ident)
        if execucao is None:
            raise HTTPException(404, "Execução não encontrada.")
        return execucao

    @app.post("/api/execucoes/{ident}/resposta")
    async def responder(ident: str, resposta: RespostaCliente) -> dict:
        """O apresentador responde pela cliente."""
        if not motor.responder(ident, resposta.texto):
            raise HTTPException(409, "Não há pergunta pendente para esta execução.")
        return {"ok": True}

    gravacoes = Gravacoes(Path(config.gravacoes_dir))

    @app.get("/api/gravacoes")
    async def listar_gravacoes() -> list[dict]:
        return gravacoes.listar()

    @app.post("/api/gravacoes")
    async def gravar(pedido: PedidoDeGravacao) -> dict:
        """Grava os eventos de uma execução terminada, para tocar depois sem rede nem LLM."""
        execucao = await motor.obter(pedido.execucao)
        if execucao is None:
            raise HTTPException(404, "Execução não encontrada.")
        eventos = await motor.eventos_da_execucao(execucao["id"], execucao["cursor_eventos"])
        nome = pedido.nome or (f"cena-{pedido.cena}" if pedido.cena else execucao["id"])
        try:
            return gravacoes.salvar(nome, execucao, eventos, cena=pedido.cena, incidentes=pedido.incidentes)
        except GravacaoInvalida as erro:
            raise HTTPException(409, str(erro)) from erro

    @app.delete("/api/gravacoes/{nome}")
    async def apagar_gravacao(nome: str) -> dict:
        try:
            gravacoes.apagar(nome)
        except (GravacaoInvalida, FileNotFoundError) as erro:
            raise HTTPException(404, "Gravação não encontrada.") from erro
        return {"apagada": nome}

    @app.get("/api/gravacoes/{nome}/eventos")
    async def tocar(nome: str) -> EventSourceResponse:
        """O replay: os eventos gravados, no ritmo original (com teto), no mesmo formato do ao vivo."""
        try:
            _, eventos = gravacoes.carregar(nome)
        except (GravacaoInvalida, FileNotFoundError) as erro:
            raise HTTPException(404, "Gravação não encontrada.") from erro

        async def fluxo() -> Any:
            yield PREENCHIMENTO
            for indice, (evento, espera) in enumerate(zip(eventos, esperas(eventos), strict=True)):
                if espera:
                    await asyncio.sleep(espera)
                yield {
                    "event": evento["tipo"],
                    "id": str(indice),
                    "data": json.dumps(evento, ensure_ascii=False),
                }

        return EventSourceResponse(fluxo(), headers=CABECALHOS_SSE)

    @app.get("/api/gravacoes/{nome}/eventos/lote")
    async def tocar_por_consulta(nome: str) -> dict:
        """A alternativa ao SSE do replay: a gravação inteira, com as pausas, para o navegador tocar."""
        try:
            _, eventos = gravacoes.carregar(nome)
        except (GravacaoInvalida, FileNotFoundError) as erro:
            raise HTTPException(404, "Gravação não encontrada.") from erro
        return lote_da_gravacao(eventos, esperas(eventos))

    @app.get("/api/execucoes/{ident}/eventos/lote")
    async def eventos_por_consulta(ident: str, apos: str | None = Query(default=None)) -> dict:
        """A alternativa ao SSE, para redes que seguram o stream: um lote de eventos por consulta.

        Sem `apos`, começa do início da execução, como o SSE. Os ids são os mesmos do SSE.
        """
        execucao = await motor.obter(ident)
        if execucao is None:
            raise HTTPException(404, "Execução não encontrada.")
        cursor = apos or execucao["cursor_eventos"]
        if not cursor_valido(cursor):
            raise HTTPException(400, "Cursor inválido.")
        return await lote_da_execucao(redis, ident, cursor)

    @app.get("/api/execucoes/{ident}/eventos")
    async def eventos(ident: str) -> EventSourceResponse:
        """Eventos da execução desde o início, e depois ao vivo, até o run.finished."""
        execucao = await motor.obter(ident)
        if execucao is None:
            raise HTTPException(404, "Execução não encontrada.")

        async def fluxo() -> Any:
            yield PREENCHIMENTO
            cursor = execucao["cursor_eventos"]
            while True:
                # Bloqueio curto (menor que o timeout de leitura do Redis); volta vazia vira keep-alive.
                lotes = await redis.xread({STREAM: cursor}, block=2000, count=100)
                if not lotes:
                    yield {"comment": "aguardando"}
                    continue
                for cursor, campos in lotes[0][1]:
                    evento = decodificar(campos)
                    if evento["dados"].get("execucao_id") != ident:
                        continue
                    yield {
                        "event": evento["tipo"],
                        "id": cursor,
                        "data": json.dumps(evento, ensure_ascii=False),
                    }
                    if evento["tipo"] == "run.finished":
                        return

        return EventSourceResponse(fluxo(), headers=CABECALHOS_SSE)

    return app
