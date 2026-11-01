"""O mundo simulado: único escritor do estado vivo.

Aplica e remove incidentes (no grafo, via contexto-mcp, e no estado vivo lido
pelos domínios), decide o pedágio e confirma as renovações de consentimento.
"""

import json
import re
from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx

from bussola_comum.dominio import agora
from bussola_comum.estado_vivo import EstadoVivo
from simulator.incidentes import Acao, Grafo, catalogo, efeitos_concretos

CHAVE_ATIVOS = "bussola:simulacao:ativos"
STREAM = "bussola:simulacao"
PRAZO_APROVACAO_S = 30
PRAZO_RENOVACAO_S = 5
ESPECIALISTA_PADRAO = "especialista-marina"
NOME_TOOL = re.compile(r"[a-z]+\.[a-z_]+")


class GrafoHttp:
    def __init__(self, url: str, token: str) -> None:
        self.url, self.cabecalhos = url, {"Authorization": f"Bearer {token}"}

    async def aplicar(self, efeitos: list[dict[str, Any]]) -> None:
        async with httpx.AsyncClient(timeout=10) as cliente:
            resposta = await cliente.post(
                f"{self.url}/interno/estado", json={"efeitos": efeitos}, headers=self.cabecalhos
            )
        resposta.raise_for_status()

    async def reset(self) -> None:
        async with httpx.AsyncClient(timeout=30) as cliente:
            resposta = await cliente.post(f"{self.url}/interno/reset", headers=self.cabecalhos)
        resposta.raise_for_status()


def _idade_s(instante: str) -> float:
    return (datetime.now(UTC) - datetime.fromisoformat(instante)).total_seconds()


class Mundo:
    def __init__(self, estado: EstadoVivo, grafo: Grafo) -> None:
        self.estado, self.grafo = estado, grafo

    async def _registrar(self, acao: Acao, dados: dict[str, Any]) -> None:
        await self.estado.redis.xadd(
            STREAM,
            {"acao": acao, "instante": agora(), "dados": json.dumps(dados, ensure_ascii=False)},
            maxlen=5000,
        )

    async def ativos(self) -> list[str]:
        return sorted(await self.estado.redis.smembers(CHAVE_ATIVOS))

    async def listar(self) -> list[dict[str, Any]]:
        ativos = set(await self.ativos())
        return [
            {
                "id": i.id,
                "nome": i.nome,
                "metafora": i.metafora,
                "reacao_esperada": i.reacao_esperada,
                "ativo": i.id in ativos,
            }
            for i in catalogo().values()
        ]

    async def _efetivar(self, incidente_id: str) -> list[dict[str, Any]]:
        efeitos = efeitos_concretos(catalogo()[incidente_id])
        for efeito in efeitos:
            await self.estado.gravar_efeito(efeito["entidade"], efeito)
        await self.grafo.aplicar(efeitos)
        return efeitos

    async def aplicar(self, incidente_id: str) -> dict[str, Any]:
        if incidente_id not in catalogo():
            raise KeyError(incidente_id)
        efeitos = await self._efetivar(incidente_id)
        await self.estado.redis.sadd(CHAVE_ATIVOS, incidente_id)
        await self._registrar("aplicado", {"incidente": incidente_id, "efeitos": efeitos})
        return {"incidente": incidente_id, "ativo": True, "efeitos": efeitos}

    async def remover(self, incidente_id: str) -> dict[str, Any]:
        """Volta ao estado-base e reaplica os outros incidentes ativos: nunca sobra estado parcial."""
        if incidente_id not in catalogo():
            raise KeyError(incidente_id)
        await self.estado.redis.srem(CHAVE_ATIVOS, incidente_id)
        restantes = await self.ativos()
        await self.estado.limpar_efeitos()
        await self.grafo.reset()
        for outro in restantes:
            await self._efetivar(outro)
        await self._registrar("removido", {"incidente": incidente_id, "ainda_ativos": restantes})
        return {"incidente": incidente_id, "ativo": False, "ainda_ativos": restantes}

    async def reset(self, grafo: bool = True) -> None:
        """Estado-base completo: sem incidentes, sem cotações, propostas, pagamentos ou apólices."""
        await self.estado.redis.delete(CHAVE_ATIVOS)
        await self.estado.limpar_efeitos()
        await self.estado.limpar_dominio()
        await self.estado.religar_todas()
        if grafo:
            await self.grafo.reset()
        await self._registrar("reset", {"grafo": grafo})

    # --- Tools fora do ar ----------------------------------------------------------

    async def tools_fora(self) -> list[str]:
        return sorted(await self.estado.tools_fora())

    async def mudar_tool(self, nome: str, no_ar: bool) -> dict[str, Any]:
        """Desliga ou religa uma tool pelo nome qualificado (ex.: seguradoras.cotar_seguro)."""
        if not NOME_TOOL.fullmatch(nome):
            raise ValueError(
                f"Nome de tool inválido: '{nome}'. Use prefixo.tool, como seguradoras.cotar_seguro."
            )
        if no_ar:
            await self.estado.religar_tool(nome)
        else:
            await self.estado.desligar_tool(nome)
        await self._registrar("tool", {"tool": nome, "no_ar": no_ar})
        return {"tool": nome, "no_ar": no_ar, "fora": await self.tools_fora()}

    async def religar_todas(self) -> dict[str, Any]:
        await self.estado.religar_todas()
        await self._registrar("tool", {"tool": "*", "no_ar": True})
        return {"fora": []}

    # --- Pedágio -------------------------------------------------------------------

    async def aprovacoes(self) -> list[dict[str, Any]]:
        return await self.estado.listar("aprovacao")

    async def decidir(self, ticket_id: str, aprovar: bool, por: str = "apresentador") -> dict[str, Any]:
        ticket = await self.estado.obter("aprovacao", ticket_id)
        if ticket is None:
            raise KeyError(ticket_id)
        if ticket["status"] != "pendente":
            return ticket
        ticket |= {
            "status": "aprovada" if aprovar else "recusada",
            "decidido_por": por,
            "decidido_em": agora(),
        }
        await self.estado.salvar("aprovacao", ticket_id, ticket)
        await self._registrar("aprovacao", ticket)
        return ticket

    # --- Passagem do tempo -----------------------------------------------------------

    async def tique(self) -> None:
        """Chamado a cada segundo: o mundo reage sozinho quando ninguém age."""
        for ticket in await self.aprovacoes():
            if ticket["status"] == "pendente" and _idade_s(ticket["criado_em"]) >= PRAZO_APROVACAO_S:
                await self.decidir(ticket["ticket_id"], aprovar=True, por=ESPECIALISTA_PADRAO)

        for pedido in await self.estado.listar("renovacao"):
            if (
                pedido["status"] == "aguardando_cliente"
                and _idade_s(pedido["criado_em"]) >= PRAZO_RENOVACAO_S
            ):
                await self.confirmar_renovacao(pedido)

    async def confirmar_renovacao(self, pedido: dict[str, Any]) -> None:
        """A cliente aceitou no app: o consentimento volta a valer por um ano."""
        hoje = date.today()
        efeito = {
            "entidade": pedido["consentimento_id"],
            "estado": {
                "status": "ok",
                "vigencia_inicio": hoje.isoformat(),
                "vigencia_fim": (hoje + timedelta(days=365)).isoformat(),
            },
            "proveniencia": {
                "fonte": "Cofre de consentimentos (aceite no app)",
                "data": hoje.isoformat(),
                "responsavel": "Encarregado de Dados (DPO)",
                "confianca": "alta",
            },
        }
        await self.estado.gravar_efeito(efeito["entidade"], efeito)
        await self.grafo.aplicar([efeito])
        pedido |= {"status": "confirmado", "confirmado_em": agora()}
        await self.estado.salvar("renovacao", pedido["pedido_id"], pedido)
        await self.estado.redis.srem(CHAVE_ATIVOS, "consentimento-ana-expirado")
        await self._registrar("renovacao", pedido)
