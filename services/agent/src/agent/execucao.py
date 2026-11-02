"""Motor de execução: o agente dirigindo a jornada da Ana pelo gateway.

Três modos, mesma tarefa:
- sem_contexto: nenhuma tool de negócio;
- sem_skill: as 41 tools do gateway, sem roteiro e sem governança por skill;
- com_skill: descobre as skills (SEP-2640), carrega a escolhida e só então recebe
  as tools que ela permite; cada chamada leva a skill ativa no `_meta`.

Tudo o que acontece vira evento no barramento, com o `execucao_id`.
"""

import asyncio
import json
import logging
import time
import uuid
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from mcp.client.client import Client
from redis.asyncio import Redis

from agent import prompts
from agent.config import Config
from agent.custos import custo
from agent.ferramentas import PERGUNTAR_CLIENTE, TOOLS_DA_VIAGEM, TOOLS_DE_SKILL
from agent.incidentes import detectar
from agent.llm.base import ChamadaTool, DefinicaoTool, ErroProvedor, ResultadoTool, SessaoLLM, Uso
from agent.llm.fabrica import criar_sessao, modelo_de
from bussola_comum.dominio import agora
from bussola_comum.eventos import STREAM, Publicador, decodificar
from bussola_comum.regras import caso_de, regras, resumo
from bussola_comum.skills import (
    CHAVE_EXECUCAO,
    CHAVE_SKILL_ATIVA,
    SkillNaoConfere,
    ler_arquivo,
    listar_skills,
    tools_da_skill,
    tools_permitidas,
)

log = logging.getLogger("agent.execucao")

# O registro das ações do simulador (incidentes aplicados e removidos) no barramento.
STREAM_SIMULACAO = "bussola:simulacao"

Modo = Literal["sem_contexto", "sem_skill", "com_skill"]
MODOS: tuple[str, ...] = ("sem_contexto", "sem_skill", "com_skill")
CHAVE = "bussola:execucoes:"
CHAVE_MODELO = "bussola:llm:modelo"
LISTA = "bussola:execucoes"
NOMES_DE_SKILL = tuple(t.nome for t in TOOLS_DE_SKILL)
MOTIVOS_DE_BLOQUEIO = {
    "fora_da_skill",
    "fora_de_ordem",
    "execucao_nao_identificada",
    "desligada",
    "skill_desconhecida",
}


@dataclass
class Metricas:
    passos: int = 0
    chamadas_tool: int = 0
    tools_distintas: list[str] = field(default_factory=list)
    tools_irrelevantes: list[str] = field(default_factory=list)
    bloqueios: int = 0
    erros: int = 0
    incidentes: int = 0
    tokens: dict[str, int] = field(default_factory=lambda: asdict(Uso()))
    duracao_s: float = 0.0
    # Custo em US$ pelos preços do modelo (None se o modelo não tem preço configurado).
    custo_usd: dict[str, Any] | None = None
    # Regras do banco cumpridas no caso da execução (bussola_comum.regras): a base do placar.
    caso: str = "caminho-feliz"
    regras: dict[str, Any] | None = None


@dataclass
class Execucao:
    id: str
    modo: str
    provedor: str
    pedido: str
    canal: str = prompts.CANAL_PADRAO
    status: str = "criada"  # criada, rodando, aguardando_cliente, concluida, interrompida, erro
    modelo: str = ""
    criada_em: str = field(default_factory=agora)
    cursor_eventos: str = "0-0"
    pergunta: dict[str, Any] | None = None
    skill: str | None = None
    rota: str | None = None
    mensagem_final: str = ""
    apolice: str | None = None
    erro: str | None = None
    metricas: Metricas = field(default_factory=Metricas)


def _texto_do_resultado(resultado: Any) -> str:
    if resultado.structured_content is not None:
        return json.dumps(resultado.structured_content, ensure_ascii=False)
    return "\n".join(getattr(c, "text", "") for c in resultado.content)


class Motor:
    def __init__(
        self,
        config: Config,
        redis: Redis,
        publicador: Publicador,
        conectar_gateway: Callable[[], AbstractAsyncContextManager[Client]],
        fabrica_sessao: Callable[..., SessaoLLM] = criar_sessao,
    ) -> None:
        self.config = config
        self.redis = redis
        self.publicador = publicador
        self.conectar_gateway = conectar_gateway
        self.fabrica_sessao = fabrica_sessao
        self.tarefas: dict[str, asyncio.Task] = {}
        self.respostas: dict[str, asyncio.Future[str]] = {}

    # --- Ciclo de vida -------------------------------------------------------------

    async def iniciar(
        self,
        modo: str,
        provedor: str | None = None,
        pedido: str | None = None,
        canal: str | None = None,
        modelo: str | None = None,
        caso: str = "caminho-feliz",
    ) -> Execucao:
        if modo not in MODOS:
            raise ValueError(f"Modo desconhecido: {modo}. Use um de: {', '.join(MODOS)}.")
        ultimo = await self.redis.xrevrange(STREAM, count=1)
        provedor = provedor or self.config.llm_provider
        if not modelo and provedor == "anthropic":
            modelo = await self.modelo_atual()
        execucao = Execucao(
            id=uuid.uuid4().hex[:10],
            modo=modo,
            provedor=provedor,
            pedido=pedido or prompts.PEDIDO_PADRAO,
            canal=canal or prompts.CANAL_PADRAO,
            modelo=modelo or "",
            cursor_eventos=ultimo[0][0] if ultimo else "0-0",
        )
        execucao.metricas.caso = caso
        await self.salvar(execucao)
        await self.redis.lpush(LISTA, execucao.id)
        await self.redis.ltrim(LISTA, 0, 49)
        self.tarefas[execucao.id] = asyncio.create_task(self._rodar(execucao))
        return execucao

    async def canais(self) -> list[str]:
        """Canais com persona no gateway (prompts `canais.atendimento_*`): o agente não os traz embutidos."""
        async with self.conectar_gateway() as gateway:
            nomes = [p.name for p in (await gateway.list_prompts()).prompts]
        prefixo = prompts.PREFIXO_PROMPT_DE_CANAL
        return sorted(n.removeprefix(prefixo) for n in nomes if n.startswith(prefixo))

    async def modelo_atual(self) -> str:
        """O modelo das próximas execuções: o escolhido no painel, ou o padrão do .env."""
        try:
            escolhido = await self.redis.get(CHAVE_MODELO)
        except Exception:  # noqa: BLE001
            escolhido = None
        return escolhido if escolhido in self.config.modelos_anthropic else self.config.anthropic_model

    async def definir_modelo(self, modelo: str) -> None:
        if modelo not in self.config.modelos_anthropic:
            raise ValueError(
                f"Modelo não permitido: {modelo}. Use um de: {', '.join(self.config.modelos_anthropic)}."
            )
        await self.redis.set(CHAVE_MODELO, modelo)

    async def salvar(self, execucao: Execucao) -> None:
        await self.redis.set(CHAVE + execucao.id, json.dumps(asdict(execucao), ensure_ascii=False))

    async def obter(self, ident: str) -> dict[str, Any] | None:
        bruto = await self.redis.get(CHAVE + ident)
        return json.loads(bruto) if bruto else None

    async def listar(self) -> list[dict[str, Any]]:
        ids = await self.redis.lrange(LISTA, 0, 19)
        return [e for e in [await self.obter(i) for i in ids] if e]

    def responder(self, ident: str, texto: str) -> bool:
        """O apresentador responde pela cliente. Falso se não há pergunta pendente."""
        futuro = self.respostas.get(ident)
        if futuro is None or futuro.done():
            return False
        futuro.set_result(texto)
        return True

    async def eventos_da_execucao(self, ident: str, cursor: str) -> list[dict[str, Any]]:
        """Os eventos da execução no barramento (do agente e do gateway), em ordem, a partir do cursor."""
        eventos: list[dict[str, Any]] = []
        while True:
            lote = await self.redis.xrange(STREAM, min=f"({cursor}", count=500)
            if not lote:
                return eventos
            for entrada, campos in lote:
                evento = decodificar(campos)
                if evento["dados"].get("execucao_id") == ident:
                    eventos.append(evento)
                cursor = entrada

    async def _conferir_regras(self, execucao: Execucao) -> dict[str, Any] | None:
        try:
            eventos = await self.eventos_da_execucao(execucao.id, execucao.cursor_eventos)
        except Exception:  # noqa: BLE001
            log.warning("Regras da execução %s não conferidas: barramento indisponível", execucao.id)
            return None
        if execucao.metricas.caso == "caminho-feliz":
            # Um incidente aplicado durante a viagem (cena 6) também define o caso: o registro do
            # simulador no barramento diz o que mudou no mundo, sem o agente falar com o simulador.
            execucao.metricas.caso = caso_de(await self._incidentes_durante(execucao))
        fim = {"tipo": "run.finished", "dados": {"apolice": execucao.apolice}}
        return resumo(regras(execucao.metricas.caso, [*eventos, fim]))

    async def _incidentes_durante(self, execucao: Execucao) -> list[str]:
        inicio = execucao.cursor_eventos.split("-")[0]  # ids do Redis: milissegundos
        aplicados = []
        for _, campos in await self.redis.xrange(STREAM_SIMULACAO, min=f"{inicio}-0", count=1000):
            if campos.get("acao") == "aplicado":
                aplicados.append(json.loads(campos["dados"]).get("incidente"))
        return [a for a in aplicados if a]

    async def aguardar(self, ident: str) -> None:
        if tarefa := self.tarefas.get(ident):
            await tarefa

    # --- A viagem ----------------------------------------------------------------------

    async def _rodar(self, execucao: Execucao) -> None:
        inicio = time.perf_counter()
        viagem = _Viagem(self, execucao)
        try:
            await viagem.dirigir()
        except Exception as erro:  # noqa: BLE001
            causa = _causa(erro)
            if isinstance(causa, ErroProvedor):
                execucao.status, execucao.erro = "erro", str(causa)
            else:
                log.exception("Execução %s falhou", execucao.id)
                execucao.status, execucao.erro = "erro", f"{type(causa).__name__}: {causa}"
        finally:
            execucao.pergunta = None
            execucao.metricas.duracao_s = round(time.perf_counter() - inicio, 2)
            execucao.metricas.custo_usd = custo(self.config, execucao.modelo, execucao.metricas.tokens)
            execucao.metricas.regras = await self._conferir_regras(execucao)
            await self.salvar(execucao)
            await viagem.publicar(
                "run.finished",
                {
                    "status": execucao.status,
                    "erro": execucao.erro,
                    "mensagem_final": execucao.mensagem_final,
                    "apolice": execucao.apolice,
                    "metricas": asdict(execucao.metricas),
                },
            )
            self.respostas.pop(execucao.id, None)


class _Viagem:
    """Estado de uma execução em andamento: sessão do LLM, gateway, skill e rota."""

    def __init__(self, motor: Motor, execucao: Execucao) -> None:
        self.motor = motor
        self.execucao = execucao
        self.gateway: Client | None = None
        self.tools_gateway: dict[str, DefinicaoTool] = {}
        self.skills: dict[str, dict[str, Any]] = {}
        self.permitidas: set[str] = set()
        self.paradas: list[dict[str, Any]] = []
        self.incidentes_vistos: set[tuple] = set()
        self.relevantes: set[str] = set()

    async def publicar(self, tipo: str, dados: dict[str, Any]) -> None:
        await self.motor.publicador.publicar(tipo, {"execucao_id": self.execucao.id, **dados})

    def _meta(self) -> dict[str, str]:
        """O `_meta` de toda requisição ao gateway: a execução e, se houver, a skill ativa."""
        meta = {CHAVE_EXECUCAO: self.execucao.id}
        if self.execucao.skill:
            meta[CHAVE_SKILL_ATIVA] = self.execucao.skill
        return meta

    async def dirigir(self) -> None:
        execucao, config = self.execucao, self.motor.config
        # run.started é sempre o primeiro evento da execução, antes de qualquer conversa com o gateway.
        execucao.modelo, execucao.status = modelo_de(execucao.provedor, config, execucao.modelo), "rodando"
        await self.motor.salvar(execucao)
        await self.publicar(
            "run.started",
            {
                "modo": execucao.modo,
                "canal": execucao.canal,
                "provedor": execucao.provedor,
                "modelo": execucao.modelo,
                "pedido": execucao.pedido,
            },
        )
        async with self.motor.conectar_gateway() as gateway:
            self.gateway = gateway
            self.tools_gateway = {
                t.name: DefinicaoTool(t.name, t.description or "", t.input_schema)
                for t in (await gateway.list_tools(meta=self._meta())).tools
            }
            self.skills = {e["uri"]: e for e in await listar_skills(gateway, self._meta())}
            # Tools de alguma skill; as demais são "irrelevantes" para a jornada (métrica do placar).
            self.relevantes = set().union(*(tools_permitidas(e["frontmatter"]) for e in self.skills.values()))

            persona, evento_persona = await self._carregar_persona()
            await self.publicar("prompt.loaded", evento_persona)
            sistema = prompts.montar_sistema(execucao.modo, persona, list(self.skills.values()))
            sessao = self.motor.fabrica_sessao(
                execucao.provedor,
                execucao.modo,
                sistema,
                execucao.pedido,
                config,
                canal=execucao.canal,
                modelo=execucao.modelo,
            )
            execucao.modelo = sessao.modelo
            await self.motor.salvar(execucao)

            for numero in range(1, config.max_passos + 1):
                inicio = time.perf_counter()
                passo = await sessao.passo(self._tools_disponiveis())
                # Cada chamada ao modelo vira um evento: tokens e latência ao vivo no Raio-X.
                await self.publicar(
                    "model.step",
                    {
                        "passo": numero,
                        "modelo": sessao.modelo,
                        "tokens": asdict(passo.uso),
                        "duracao_ms": round((time.perf_counter() - inicio) * 1000),
                        "tools_pedidas": [c.nome for c in passo.chamadas],
                        "motivo_parada": passo.motivo_parada,
                    },
                )
                execucao.metricas.passos += 1
                tokens = Uso(**execucao.metricas.tokens)
                tokens.somar(passo.uso)
                execucao.metricas.tokens = asdict(tokens)
                if passo.texto:
                    await self.publicar("agent.message", {"texto": passo.texto, "final": passo.fim})
                if passo.fim:
                    execucao.mensagem_final = passo.texto
                    execucao.status = (
                        "concluida"
                        if passo.motivo_parada not in ("recusa", "limite_de_tokens")
                        else "interrompida"
                    )
                    if execucao.status == "interrompida":
                        execucao.erro = f"Parada: {passo.motivo_parada}"
                    return
                if passo.chamadas:
                    resultados = [await self._executar(c) for c in passo.chamadas]
                    sessao.adicionar_resultados(resultados)
                await self.motor.salvar(execucao)
            execucao.status, execucao.erro = "interrompida", f"Limite de {config.max_passos} passos atingido."

    async def _carregar_persona(self) -> tuple[str, dict[str, Any]]:
        """A persona do canal vem do banco, pelo gateway. Sem ela, a persona embutida, com aviso."""
        execucao = self.execucao
        nome = prompts.nome_do_prompt(execucao.canal)
        evento: dict[str, Any] = {"nome": nome, "canal": execucao.canal}
        if execucao.modo == "sem_contexto":
            persona = prompts.PERSONA_EMBUTIDA
            evento |= {"origem": "embutido", "motivo": "O modo sem contexto não consulta o banco."}
        else:
            try:
                resultado = await self.gateway.get_prompt(
                    nome, {"cliente_id": prompts.CLIENTE_PADRAO}, meta=self._meta()
                )
                persona = "\n\n".join(getattr(m.content, "text", "") for m in resultado.messages)
                evento["origem"] = "gateway"
            except Exception as erro:  # noqa: BLE001
                persona = prompts.PERSONA_EMBUTIDA
                motivo = getattr(erro, "message", None) or str(erro)
                evento |= {"origem": "embutido", "motivo": f"Persona do canal indisponível: {motivo}"}
        return persona, {**evento, "tamanho": len(persona)}

    def _tools_disponiveis(self) -> list[DefinicaoTool]:
        modo = self.execucao.modo
        if modo == "sem_contexto":
            return [PERGUNTAR_CLIENTE]
        if modo == "sem_skill":
            return [PERGUNTAR_CLIENTE, *self.tools_gateway.values()]
        # A lista não muda durante a conversa: mudar as tools invalida o raciocínio já feito
        # (pensamento preservado). Por isso o modelo vê, desde o início, as tools de alguma skill;
        # o host as recusa até a skill ser carregada, e o gateway aplica a skill e a ordem depois.
        relevantes = [t for n, t in sorted(self.tools_gateway.items()) if n in self.relevantes]
        return [PERGUNTAR_CLIENTE, *TOOLS_DE_SKILL, *TOOLS_DA_VIAGEM, *relevantes]

    # --- Execução de cada chamada -------------------------------------------------------

    async def _executar(self, chamada: ChamadaTool) -> ResultadoTool:
        tratadores = {
            "conversa.perguntar_cliente": self._perguntar_cliente,
            "agente.carregar_skill": self._carregar_skill,
            "agente.ler_arquivo_skill": self._ler_arquivo_skill,
            "navegacao.planejar_rota": self._planejar_rota,
            "navegacao.iniciar_parada": self._iniciar_parada,
            "navegacao.recalcular_rota": self._recalcular_rota,
        }
        sem_skill_ainda = self.execucao.modo == "com_skill" and self.execucao.skill is None
        if sem_skill_ainda and chamada.nome not in ("conversa.perguntar_cliente", *NOMES_DE_SKILL):
            return ResultadoTool(
                chamada.id,
                f"{chamada.nome} ainda não está disponível: carregue a skill antes, "
                "com agente.carregar_skill.",
                erro=True,
            )
        try:
            if chamada.nome in tratadores:
                texto = await tratadores[chamada.nome](**chamada.argumentos)
                return ResultadoTool(chamada.id, texto)
            return await self._chamar_gateway(chamada)
        except (TypeError, KeyError, ValueError, SkillNaoConfere) as erro:
            return ResultadoTool(chamada.id, f"Chamada inválida para {chamada.nome}: {erro}", erro=True)

    async def _chamar_gateway(self, chamada: ChamadaTool) -> ResultadoTool:
        metricas = self.execucao.metricas
        if chamada.nome not in self.tools_gateway:
            metricas.erros += 1
            return ResultadoTool(chamada.id, f"Tool desconhecida: {chamada.nome}.", erro=True)
        resultado = await self.gateway.call_tool(chamada.nome, chamada.argumentos, meta=self._meta())
        texto = _texto_do_resultado(resultado)
        meta_resposta = resultado.meta or {}

        metricas.chamadas_tool += 1
        if chamada.nome not in metricas.tools_distintas:
            metricas.tools_distintas.append(chamada.nome)
        if chamada.nome not in self.relevantes and chamada.nome not in metricas.tools_irrelevantes:
            metricas.tools_irrelevantes.append(chamada.nome)
        if (meta_resposta.get("bussola/proveniencia") or {}).get("motivo") in MOTIVOS_DE_BLOQUEIO:
            metricas.bloqueios += 1
        if resultado.is_error:
            metricas.erros += 1

        dados = resultado.structured_content or {}
        for achado in detectar(chamada.nome, dados, texto, resultado.is_error, meta_resposta):
            chave = (achado["metafora"], achado["entidade"], achado["descricao"])
            if chave not in self.incidentes_vistos:
                self.incidentes_vistos.add(chave)
                metricas.incidentes += 1
                await self.publicar("incident.detected", achado)
        if chamada.nome == "atendimento.solicitar_aprovacao" and not resultado.is_error:
            await self.publicar(
                "human.required", {"ticket_id": dados.get("ticket_id"), "motivo": dados.get("motivo")}
            )
        # A apólice conta mesmo quando sai pelo atalho legado: o placar mostra a regra quebrada.
        if (
            chamada.nome in ("seguradoras.emitir_apolice", "seguradoras.contratacao_expressa")
            and not resultado.is_error
        ):
            self.execucao.apolice = dados.get("numero")
        return ResultadoTool(chamada.id, texto, erro=resultado.is_error)

    # --- Conversa com a cliente -------------------------------------------------------

    async def _perguntar_cliente(self, pergunta: str, opcoes: list[str] | None = None) -> str:
        execucao = self.execucao
        futuro: asyncio.Future[str] = asyncio.get_running_loop().create_future()
        self.motor.respostas[execucao.id] = futuro
        execucao.status, execucao.pergunta = (
            "aguardando_cliente",
            {"pergunta": pergunta, "opcoes": opcoes or []},
        )
        await self.motor.salvar(execucao)
        await self.publicar("client.asked", execucao.pergunta)
        resposta = await futuro
        execucao.status, execucao.pergunta = "rodando", None
        await self.motor.salvar(execucao)
        await self.publicar("client.answered", {"texto": resposta})
        return resposta

    # --- Skills (SEP-2640) --------------------------------------------------------------

    async def _carregar_skill(self, uri: str) -> str:
        if self.execucao.modo != "com_skill":
            raise ValueError("skills só estão disponíveis no modo com_skill")
        entrada = self.skills.get(uri)
        if entrada is None:
            raise ValueError(f"skill desconhecida: {uri}")
        texto = await ler_arquivo(self.gateway, uri, entrada, self._meta())
        if self.execucao.skill is None:
            # A primeira skill carregada guia a viagem; as que ela reutiliza entram nas permissões.
            self.execucao.skill = uri
            self.permitidas = tools_da_skill(self.skills, uri) or set()
            await self.motor.salvar(self.execucao)
            await self.publicar(
                "skill.loaded",
                {
                    "uri": uri,
                    "nome": entrada["frontmatter"]["name"],
                    "tools_permitidas": sorted(self.permitidas),
                },
            )
        return texto

    async def _ler_arquivo_skill(self, uri: str) -> str:
        raiz = "/".join(uri.split("/")[:3]) + "/SKILL.md"
        entrada = self.skills.get(raiz)
        if entrada is None:
            raise ValueError(f"arquivo fora das skills conhecidas: {uri}")
        return await ler_arquivo(self.gateway, uri, entrada, self._meta())

    # --- Navegação: o que o mapa desenha ----------------------------------------------------

    async def _consultar_rota(self, rota: str) -> dict[str, Any]:
        resposta = await self._chamar_gateway(
            ChamadaTool("interno", "contexto.consultar_rota", {"rota": rota})
        )
        if resposta.erro:
            raise ValueError(resposta.texto)
        dados = json.loads(resposta.texto)["rotas"][0]
        self.paradas = dados["paradas"]
        return dados

    async def _planejar_rota(self, rota: str, motivo: str) -> str:
        dados = await self._consultar_rota(rota)
        self.execucao.rota = rota
        await self.publicar(
            "route.planned",
            {
                "rota": rota,
                "nome": dados["nome"],
                "motivo": motivo,
                "estimativa": dados["estimativa"],
                "paradas": _paradas(dados),
            },
        )
        estimativa = dados["estimativa"]
        return f"Rota {dados['nome']} planejada: {estimativa['tempo_texto']}, risco {estimativa['risco']}."

    async def _iniciar_parada(self, parada: int | str) -> str:
        alvo = next(
            (
                p
                for p in self.paradas
                if p["numero"] == parada or p["id"] == parada or str(p["numero"]) == str(parada)
            ),
            None,
        )
        dados = (
            {"numero": alvo["numero"], "id": alvo["id"], "nome": alvo["nome"], "bairro": alvo["bairro"]}
            if alvo
            else {"id": str(parada)}
        )
        await self.publicar("step.started", dados)
        return f"Parada {dados.get('nome', parada)} iniciada."

    async def _recalcular_rota(self, motivo: str, regra: str, nova_rota: str) -> str:
        dados = await self._consultar_rota(nova_rota)
        anterior, self.execucao.rota = self.execucao.rota, nova_rota
        await self.publicar(
            "route.recalculated",
            {
                "de": anterior,
                "para": nova_rota,
                "motivo": motivo,
                "regra": regra,
                "estimativa": dados["estimativa"],
                "paradas": _paradas(dados),
            },
        )
        return f"Rota recalculada para {dados['nome']}: {dados['estimativa']['tempo_texto']}."


def _causa(erro: BaseException) -> BaseException:
    """A conexão MCP roda num grupo de tarefas: o erro real chega dentro de ExceptionGroup."""
    while isinstance(erro, BaseExceptionGroup) and erro.exceptions:
        erro = erro.exceptions[0]
    return erro


def _paradas(rota: dict[str, Any]) -> list[dict[str, Any]]:
    return [{k: p[k] for k in ("ordem", "numero", "id", "nome", "bairro")} for p in rota["paradas"]]
