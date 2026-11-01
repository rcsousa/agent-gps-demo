"""Provedor "roteiro": ensaio determinístico, sem LLM e sem chave.

Segue um script por modo e decide pelo resultado de cada tool (rota bloqueada,
API fora do ar, consentimento vencido, pedágio...). Não simula inteligência:
serve para ensaiar a demo sem rede e para os testes ponta a ponta. Os eventos
dizem claramente `provedor: roteiro`.
"""

import asyncio
import itertools
import json
from collections.abc import Generator
from typing import Any

from agent.llm.base import ChamadaTool, DefinicaoTool, Passo, ResultadoTool
from bussola_comum.dominio import reais

PRINCIPAL = "skill://contratacao-seguro-residencial/SKILL.md"
ORDEM_ROTAS = ["rota-rapida", "rota-economica", "rota-assistida"]
SEGURADORAS_DA_ROTA = {
    "rota-rapida": ["ancora"],
    "rota-economica": ["ancora", "farol", "horizonte"],
    "rota-assistida": ["farol"],
}
PRODUTO = {s: f"produto-residencial-{s}" for s in ("ancora", "farol", "horizonte")}
NOMES = {"ancora": "Âncora", "farol": "Farol", "horizonte": "Horizonte"}

# O mesmo roteiro, dito a quem está do outro lado em cada canal (as personas `canais.*` do gateway):
# no app, à própria Ana; na agência, ao gerente ao lado dela; na central, ao atendente ao telefone.
FALAS = {
    "imovel": {
        "app": "Para confirmar: o seguro é para o seu apartamento na Vila Mariana, em São Paulo?",
        "agencia": "Confirme com a Ana: o seguro é para o apartamento dela na Vila Mariana, em São Paulo?",
        "central": "Pergunte à Ana: o seguro é para o apartamento dela na Vila Mariana, em São Paulo?",
    },
    "renovacao": {
        "app": "Seu consentimento para ofertas venceu. Posso pedir a renovação pelo app?",
        "agencia": (
            "O consentimento da Ana para ofertas venceu. Confirme com ela se posso pedir a "
            "renovação pelo app."
        ),
        "central": (
            "Diga à Ana que o consentimento dela para ofertas venceu e pergunte se o banco pode "
            "pedir a renovação pelo app."
        ),
    },
    "aceite": {
        "app": "{resumo} Você aceita esta proposta?",
        "agencia": "Apresente a proposta à Ana: {resumo} Confirme com ela se aceita.",
        "central": (
            "Leia para a Ana: {resumo} Pergunte se ela aceita e confirme a resposta dela, palavra "
            "por palavra."
        ),
    },
    "emitida": {
        "app": (
            "Pronto, Ana! Sua apólice {numero} da {seguradora} está emitida, com prêmio de "
            "{premio} por ano e vigência a partir de hoje."
        ),
        "agencia": (
            "Pronto: a apólice {numero} da Ana, na {seguradora}, está emitida, com prêmio de "
            "{premio} por ano e vigência a partir de hoje. Entregue a ela o resumo da cobertura."
        ),
        "central": (
            "Pode avisar a Ana: a apólice dela, da {seguradora}, está emitida e vale a partir de "
            "hoje. O número é {numero} e o prêmio é de {premio} por ano."
        ),
    },
}


class Esperar:
    """Pausa do roteiro (ex.: aguardar a cliente confirmar no app)."""

    def __init__(self, segundos: float) -> None:
        self.segundos = segundos


class Fim:
    def __init__(self, texto: str) -> None:
        self.texto = texto


Acao = list[ChamadaTool] | Esperar | Fim
Roteiro = Generator[Acao, dict[str, ResultadoTool], None]


class SessaoRoteiro:
    provedor = "roteiro"
    modelo = "roteiro-de-ensaio"

    def __init__(self, modo: str, canal: str = "app", espera_s: float = 2.0) -> None:
        self._ids = itertools.count(1)
        self.canal = canal if canal in FALAS["imovel"] else "app"
        self.espera_s = espera_s
        self._roteiro = {"sem_contexto": self._sem_contexto, "sem_skill": self._sem_skill}.get(
            modo, self._com_skill
        )()
        self._resultados: dict[str, ResultadoTool] = {}
        self._iniciado = False

    # --- Contrato da sessão --------------------------------------------------------

    async def passo(self, tools: list[DefinicaoTool]) -> Passo:
        while True:
            try:
                acao = next(self._roteiro) if not self._iniciado else self._roteiro.send(self._resultados)
            except StopIteration:
                return Passo(fim=True, motivo_parada="fim_do_roteiro")
            self._iniciado = True
            self._resultados = {}
            if isinstance(acao, Esperar):
                await asyncio.sleep(acao.segundos)
                continue
            if isinstance(acao, Fim):
                return Passo(texto=acao.texto, fim=True, motivo_parada="fim_do_roteiro")
            return Passo(chamadas=acao, motivo_parada="tool_use")

    def adicionar_resultados(self, resultados: list[ResultadoTool]) -> None:
        self._resultados = {r.id: r for r in resultados}

    # --- Utilidades do script --------------------------------------------------------

    def _chamada(self, nome: str, **argumentos: Any) -> ChamadaTool:
        return ChamadaTool(id=f"roteiro-{next(self._ids)}", nome=nome, argumentos=argumentos)

    def _uma(self, nome: str, **argumentos: Any) -> Generator[Acao, dict[str, ResultadoTool], ResultadoTool]:
        chamada = self._chamada(nome, **argumentos)
        resultados = yield [chamada]
        return resultados[chamada.id]

    def _fala(self, chave: str, **valores: str) -> str:
        return FALAS[chave][self.canal].format(**valores)

    @staticmethod
    def _dados(resultado: ResultadoTool) -> dict[str, Any]:
        try:
            return json.loads(resultado.texto)
        except (json.JSONDecodeError, TypeError):
            return {}

    # --- Modo sem contexto: responde sem tools, sem base ------------------------------

    def _sem_contexto(self) -> Roteiro:
        yield Fim(
            "Claro, Ana! Contratei para você o Seguro Residencial Total por R$ 49,90 por mês, com cobertura "
            "contra incêndio, roubo, enchente e terremoto, sem franquia. A apólice já está ativa."
        )

    # --- Modo sem skill: explora o catálogo, fora de ordem e sem regras ----------------

    def _sem_skill(self) -> Roteiro:
        ana = {"cliente_id": "cliente-ana"}
        yield [
            self._chamada("cliente.obter_perfil", **ana),
            self._chamada("cliente.listar_transacoes", **ana),
        ]
        yield [
            self._chamada("risco.calcular_score_credito", **ana),
            self._chamada("consentimento.listar_historico", **ana),
        ]
        cotacao = self._dados((yield from self._uma("seguradoras.cotar_seguro", **ana, seguradora="ancora")))
        yield [
            self._chamada("seguradoras.listar_apolices", **ana),
            self._chamada("pagamentos.consultar_extrato", **ana),
        ]
        yield [
            self._chamada("cliente.consultar_limite_credito", **ana),
            self._chamada("risco.simular_emprestimo", **ana, valor=5000),
        ]
        if cotacao.get("cotacao_id"):
            yield from self._uma("seguradoras.gerar_proposta", cotacao_id=cotacao["cotacao_id"])
        yield Fim(
            "Ana, encontrei um seguro da Âncora e já gerei a proposta. Conferi também seu "
            "extrato, seu limite "
            "e simulei um empréstimo, caso precise."
        )

    # --- Modo com skill: a jornada guiada pela skill ----------------------------------

    def _com_skill(self) -> Roteiro:
        ana = {"cliente_id": "cliente-ana"}
        yield from self._uma("agente.carregar_skill", uri=PRINCIPAL)

        rotas = {
            r["id"]: r
            for r in self._dados((yield from self._uma("contexto.consultar_rota"))).get("rotas", [])
        }
        rota = next(
            (r for r in ORDEM_ROTAS if r in rotas and not rotas[r]["estimativa"]["bloqueada"]),
            "rota-assistida",
        )
        yield from self._uma(
            "navegacao.planejar_rota",
            rota=rota,
            motivo="Primeira rota livre na ordem rápida, econômica, assistida.",
        )

        # 1. Intenção
        yield from self._uma("navegacao.iniciar_parada", parada=1)
        confirmacao = yield from self._uma(
            "conversa.perguntar_cliente",
            pergunta=self._fala("imovel"),
            opcoes=["Sim, é esse apartamento", "Não, é outro imóvel"],
        )
        if "não" in confirmacao.texto.lower():
            yield Fim(
                "Entendi. Vou precisar dos dados do outro imóvel antes de seguir; um especialista "
                "entra em contato."
            )
            return

        # 2. Identificação
        yield from self._uma("navegacao.iniciar_parada", parada=2)
        yield [self._chamada("cliente.obter_perfil", **ana), self._chamada("cliente.listar_produtos", **ana)]

        # 3. Consentimento
        yield from self._uma("navegacao.iniciar_parada", parada=3)
        for finalidade in ("finalidade-oferta-personalizada", "finalidade-compartilhamento-seguradoras"):
            verificacao = self._dados(
                (yield from self._uma("consentimento.verificar", **ana, finalidade=finalidade))
            )
            if not verificacao.get("permitido"):
                resposta = yield from self._uma(
                    "conversa.perguntar_cliente",
                    pergunta=self._fala("renovacao"),
                    opcoes=["Pode pedir", "Não quero renovar"],
                )
                if "não" in resposta.texto.lower():
                    yield Fim("Sem o seu consentimento, não posso seguir com a oferta. Fico à disposição.")
                    return
                yield from self._uma("consentimento.solicitar_renovacao", **ana, finalidade=finalidade)
                for _ in range(10):
                    yield Esperar(self.espera_s)
                    if self._dados(
                        (yield from self._uma("consentimento.verificar", **ana, finalidade=finalidade))
                    ).get("permitido"):
                        break

        # 4. Elegibilidade
        yield from self._uma("navegacao.iniciar_parada", parada=4)
        yield from self._uma(
            "agente.ler_arquivo_skill",
            uri="skill://contratacao-seguro-residencial/references/elegibilidade.md",
        )
        imovel = self._dados((yield from self._uma("cliente.obter_imovel", **ana)))
        importancia = None
        if imovel.get("proveniencia", {}).get("confianca") != "alta":
            laudo = self._dados(
                (yield from self._uma("cliente.consultar_laudo_avaliacao", imovel_id="imovel-ana"))
            )
            importancia = laudo.get("valor_avaliado")
            yield from self._uma(
                "navegacao.recalcular_rota",
                motivo="O valor do imóvel no cadastro veio de fonte com confiança baixa.",
                regra="Ponte interditada: buscar a fonte autoritativa (laudo de avaliação).",
                nova_rota=rota,
            )
        seguradoras = list(SEGURADORAS_DA_ROTA[rota])
        elegibilidade = self._dados(
            (yield from self._uma("risco.consultar_elegibilidade", **ana, produto_id=PRODUTO[seguradoras[0]]))
        )
        if "regra-vistoria-area-risco" in elegibilidade.get("pendencias", []):
            yield from self._uma("risco.agendar_vistoria", imovel_id="imovel-ana")
            yield from self._uma(
                "navegacao.recalcular_rota",
                motivo="Nova política: imóveis na zona sul exigem vistoria prévia.",
                regra="Desvio por obra: inserir a parada de vistoria e recalcular o prazo.",
                nova_rota=rota,
            )
            yield Fim(
                "Ana, uma política nova exige vistoria para imóveis na zona sul. Já agendei: leva "
                "cerca de 3 dias. "
                "Assim que ela for concluída, sigo com a cotação e a emissão."
            )
            return

        # 5. Adequação
        yield from self._uma("navegacao.iniciar_parada", parada=5)
        yield from self._uma(
            "risco.avaliar_adequacao",
            **ana,
            produto_id=PRODUTO[seguradoras[0]],
            necessidade="Seguro residencial para o meu apartamento",
        )

        # 6. Cotação
        yield from self._uma("navegacao.iniciar_parada", parada=6)
        yield from self._uma(
            "agente.ler_arquivo_skill", uri="skill://contratacao-seguro-residencial/references/cotacao.md"
        )
        extra = {"importancia_segurada": importancia} if importancia else {}
        cotacoes = []
        for seguradora in seguradoras:
            resultado = yield from self._uma(
                "seguradoras.cotar_seguro", **ana, seguradora=seguradora, **extra
            )
            if not resultado.erro:
                cotacoes.append(self._dados(resultado))
        if not cotacoes:
            alternativas = [s for s in ("farol", "horizonte", "ancora") if s not in seguradoras]
            yield from self._uma(
                "agente.ler_arquivo_skill", uri="skill://contratacao-seguro-residencial/references/desvios.md"
            )
            yield from self._uma(
                "navegacao.recalcular_rota",
                motivo=f"A API de cotação da {NOMES[seguradoras[0]]} está fora do ar.",
                regra="Rua interditada: trocar para outra seguradora disponível e explicar a troca.",
                nova_rota="rota-economica",
            )
            for seguradora in alternativas:
                resultado = yield from self._uma(
                    "seguradoras.cotar_seguro", **ana, seguradora=seguradora, **extra
                )
                if not resultado.erro:
                    cotacoes.append(self._dados(resultado))
        if not cotacoes:
            yield Fim("Ana, nenhuma seguradora parceira está respondendo agora. Retomo assim que voltarem.")
            return
        escolhida = min(cotacoes, key=lambda c: c["premio_anual"])

        # 7. Proposta e aceite
        yield from self._uma("navegacao.iniciar_parada", parada=7)
        proposta = self._dados(
            (yield from self._uma("seguradoras.gerar_proposta", cotacao_id=escolhida["cotacao_id"]))
        )
        aceite = yield from self._uma(
            "conversa.perguntar_cliente",
            pergunta=self._fala("aceite", resumo=proposta.get("resumo", "")),
            opcoes=["Aceito", "Não aceito"],
        )
        if "não" in aceite.texto.lower():
            yield Fim("Tudo bem, Ana. A proposta fica guardada caso mude de ideia.")
            return
        yield from self._uma("seguradoras.registrar_aceite", proposta_id=proposta["proposta_id"])

        aprovacao_id = None
        if proposta.get("exige_aprovacao_humana"):
            yield from self._uma("navegacao.iniciar_parada", parada="parada-aprovacao-humana")
            yield from self._uma(
                "risco.verificar_alcada",
                premio_anual=proposta["premio_anual"],
                importancia_segurada=proposta["importancia_segurada"],
            )
            ticket = self._dados(
                (
                    yield from self._uma(
                        "atendimento.solicitar_aprovacao",
                        proposta_id=proposta["proposta_id"],
                        motivo="Importância segurada acima da alçada automática.",
                    )
                )
            )
            for _ in range(30):
                yield Esperar(self.espera_s)
                situacao = self._dados(
                    (yield from self._uma("atendimento.consultar_aprovacao", ticket_id=ticket["ticket_id"]))
                )
                if situacao.get("status") != "pendente":
                    break
            if situacao.get("status") != "aprovada":
                yield Fim(
                    "Ana, a especialista não aprovou esta proposta. Posso ajustar a cobertura para caber "
                    "na alçada."
                )
                return
            aprovacao_id = ticket["ticket_id"]

        # 8. Pagamento
        yield from self._uma("navegacao.iniciar_parada", parada=8)
        pagamento = self._dados(
            (
                yield from self._uma(
                    "pagamentos.processar_pagamento",
                    **ana,
                    valor=proposta["premio_anual"],
                    referencia=proposta["proposta_id"],
                )
            )
        )

        # 9. Emissão
        yield from self._uma("navegacao.iniciar_parada", parada=9)
        yield from self._uma(
            "agente.ler_arquivo_skill", uri="skill://contratacao-seguro-residencial/references/emissao.md"
        )
        argumentos = {
            "proposta_id": proposta["proposta_id"],
            "pagamento_id": pagamento.get("pagamento_id", ""),
        }
        if aprovacao_id:
            argumentos["aprovacao_id"] = aprovacao_id
        apolice = self._dados((yield from self._uma("seguradoras.emitir_apolice", **argumentos)))
        if not apolice.get("numero"):
            yield Fim(
                "Ana, a emissão não foi concluída. Já abri a verificação e te aviso assim que resolver."
            )
            return
        yield Fim(
            self._fala(
                "emitida",
                numero=apolice["numero"],
                seguradora=apolice["seguradora"],
                premio=reais(apolice["premio_anual"]),
            )
        )
