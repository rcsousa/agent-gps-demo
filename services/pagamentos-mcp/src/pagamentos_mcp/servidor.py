"""Pagamentos: débito em conta, cartão e Pix."""

from typing import Any, Literal

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from bussola_comum import cadastro
from bussola_comum.dominio import ConfigDominio, agora, novo_id, preparar_dominio
from bussola_comum.estado_vivo import EstadoVivo
from bussola_comum.saude import Checagem

NOME = "pagamentos-mcp"
GATEWAY_PAGAMENTOS = ("sistema-gateway-pagamentos", "O gateway de pagamentos")
Meio = Literal["debito_em_conta", "cartao_credito", "pix"]


class Config(ConfigDominio):
    servico_nome: str = NOME


def criar_servidor(
    estado: EstadoVivo | None = None, checagens: dict[str, Checagem] | None = None
) -> MCPServer:
    mcp, estado = preparar_dominio(NOME, "Débito em conta e cartão", Config(), estado, checagens)

    def conta_do_cliente(cliente_id: str) -> dict[str, Any]:
        return cadastro.registro(
            "contas", cadastro.registro("clientes", cliente_id, "Cliente")["conta"], "Conta"
        )

    # --- Jornada -----------------------------------------------------------------

    @mcp.tool(
        description=(
            "Processa o pagamento do prêmio na conta da cliente (débito em conta, cartão ou Pix). "
            "Informe a proposta como referência."
        )
    )
    async def processar_pagamento(
        cliente_id: str, valor: float, referencia: str, meio: Meio = "debito_em_conta"
    ) -> dict[str, Any]:
        aviso = await estado.garantir_disponivel(*GATEWAY_PAGAMENTOS)
        conta = conta_do_cliente(cliente_id)
        if meio not in conta["meios"]:
            raise ToolError(
                f"A conta da cliente não permite {meio}. Meios disponíveis: {', '.join(conta['meios'])}."
            )
        if valor <= 0:
            raise ToolError("O valor do pagamento precisa ser positivo.")
        pagamento = {
            "pagamento_id": novo_id("pagamento"),
            "cliente_id": cliente_id,
            "conta_id": conta["id"],
            "meio": meio,
            "valor": round(valor, 2),
            "referencia": referencia,
            "status": "aprovado",
            "base_legal": "base-execucao-contrato",
            "processado_em": agora(),
        }
        await estado.salvar("pagamento", pagamento["pagamento_id"], pagamento)
        return {**pagamento, "aviso": aviso} if aviso else pagamento

    # --- Distração ----------------------------------------------------------------

    @mcp.tool(description="Estorna um pagamento aprovado. Devolve o valor à cliente.")
    async def estornar(pagamento_id: str) -> dict[str, Any]:
        pagamento = await estado.obter("pagamento", pagamento_id)
        if pagamento is None:
            raise ToolError(f"Pagamento '{pagamento_id}' não encontrado.")
        pagamento["status"] = "estornado"
        await estado.salvar("pagamento", pagamento_id, pagamento)
        return pagamento

    @mcp.tool(description="Extrato da conta corrente da cliente.")
    async def consultar_extrato(cliente_id: str) -> dict[str, Any]:
        conta = conta_do_cliente(cliente_id)
        pagamentos = [p for p in await estado.listar("pagamento") if p["cliente_id"] == cliente_id]
        return {"conta_id": conta["id"], "saldo": conta["saldo"], "pagamentos_recentes": pagamentos}

    @mcp.tool(description="Gera um boleto de cobrança para a cliente.")
    async def gerar_boleto(cliente_id: str, valor: float) -> dict[str, Any]:
        conta_do_cliente(cliente_id)
        return {"boleto": f"34191.79001 01043.510047 91020.150008 1 {int(valor * 100):010d}", "valor": valor}

    return mcp
