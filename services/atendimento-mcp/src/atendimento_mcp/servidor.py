"""Atendimento humano: a fila de especialistas que aprova acima da alçada (o pedágio)."""

from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from bussola_comum.dominio import ConfigDominio, agora, novo_id, preparar_dominio
from bussola_comum.estado_vivo import EstadoVivo
from bussola_comum.saude import Checagem

NOME = "atendimento-mcp"
FILA_ALCADA = ("fila-aprovacao-alcada", "A fila de aprovação de alçada")


class Config(ConfigDominio):
    servico_nome: str = NOME


def criar_servidor(
    estado: EstadoVivo | None = None, checagens: dict[str, Checagem] | None = None
) -> MCPServer:
    mcp, estado = preparar_dominio(
        NOME, "Fila de especialistas humanos (o pedágio)", Config(), estado, checagens
    )

    # --- Jornada -----------------------------------------------------------------

    @mcp.tool(
        description=(
            "Envia a proposta para aprovação de um especialista humano "
            "quando ela passa da alçada automática. "
            "Devolve um ticket; acompanhe com consultar_aprovacao."
        )
    )
    async def solicitar_aprovacao(proposta_id: str, motivo: str) -> dict[str, Any]:
        aviso = await estado.garantir_disponivel(*FILA_ALCADA)
        proposta = await estado.obter("proposta", proposta_id)
        if proposta is None:
            raise ToolError(f"Proposta '{proposta_id}' não encontrada.")
        ticket = {
            "ticket_id": novo_id("aprovacao"),
            "proposta_id": proposta_id,
            "cliente_id": proposta["cliente_id"],
            "premio_anual": proposta["premio_anual"],
            "importancia_segurada": proposta["importancia_segurada"],
            "motivo": motivo,
            "fila": "fila-aprovacao-alcada",
            "status": "pendente",
            "sla_minutos": 15,
            "criado_em": agora(),
        }
        await estado.salvar("aprovacao", ticket["ticket_id"], ticket)
        return {**ticket, "aviso": aviso} if aviso else ticket

    @mcp.tool(description="Situação de um ticket de aprovação: pendente, aprovada ou recusada, e por quem.")
    async def consultar_aprovacao(ticket_id: str) -> dict[str, Any]:
        ticket = await estado.obter("aprovacao", ticket_id)
        if ticket is None:
            raise ToolError(f"Ticket '{ticket_id}' não encontrado.")
        return ticket

    # --- Distração ----------------------------------------------------------------

    @mcp.tool(description="Abre um chamado de atendimento para a cliente.")
    async def abrir_chamado(cliente_id: str, assunto: str) -> dict[str, Any]:
        chamado = {
            "chamado_id": novo_id("chamado"),
            "cliente_id": cliente_id,
            "assunto": assunto,
            "em": agora(),
        }
        await estado.salvar("chamado", chamado["chamado_id"], chamado)
        return {**chamado, "status": "aberto", "fila": "fila-atendimento-geral"}

    @mcp.tool(description="Transfere a conversa da cliente para um atendente humano da central.")
    async def transferir_para_humano(cliente_id: str, motivo: str) -> dict[str, Any]:
        return {
            "cliente_id": cliente_id,
            "motivo": motivo,
            "status": "transferido",
            "atendente": "Tiago Mendes",
        }

    return mcp
