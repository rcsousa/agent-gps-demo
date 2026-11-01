"""Cofre de consentimentos e bases legais (LGPD)."""

from datetime import date
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from bussola_comum import cadastro
from bussola_comum.dominio import ConfigDominio, agora, novo_id, preparar_dominio
from bussola_comum.estado_vivo import EstadoVivo
from bussola_comum.saude import Checagem

NOME = "consentimento-mcp"
COFRE = ("sistema-cofre-consentimentos", "O cofre de consentimentos")
FINALIDADES = {
    "finalidade-oferta-personalizada": "Oferta personalizada de seguros",
    "finalidade-compartilhamento-seguradoras": "Compartilhamento com seguradoras parceiras",
    "finalidade-cobranca": "Cobrança do prêmio",
}
# Cobrança se apoia na execução do contrato pedido pela cliente, não em consentimento.
BASE_LEGAL = {
    "finalidade-oferta-personalizada": "base-consentimento",
    "finalidade-compartilhamento-seguradoras": "base-consentimento",
    "finalidade-cobranca": "base-execucao-contrato",
}


class Config(ConfigDominio):
    servico_nome: str = NOME


def criar_servidor(
    estado: EstadoVivo | None = None, checagens: dict[str, Checagem] | None = None
) -> MCPServer:
    mcp, estado = preparar_dominio(NOME, "Bases legais e consentimentos (LGPD)", Config(), estado, checagens)

    def finalidade_valida(finalidade: str) -> None:
        if finalidade not in FINALIDADES:
            raise ToolError(f"Finalidade desconhecida: '{finalidade}'. Use uma de: {', '.join(FINALIDADES)}.")

    async def consentimento_de(cliente_id: str, finalidade: str) -> dict[str, Any] | None:
        cadastro.registro("clientes", cliente_id, "Cliente")
        for ident, c in cadastro.dados()["consentimentos"].items():
            if c["cliente"] == cliente_id and c["finalidade"] == finalidade:
                return await cadastro.atual(estado, "consentimentos", ident, "Consentimento")
        return None

    # --- Jornada -----------------------------------------------------------------

    @mcp.tool(
        description=(
            "Verifica se há base legal para usar os dados da cliente numa finalidade "
            "(ex.: finalidade-oferta-personalizada). Diz se o consentimento está vigente."
        )
    )
    async def verificar(cliente_id: str, finalidade: str) -> dict[str, Any]:
        finalidade_valida(finalidade)
        aviso = await estado.garantir_disponivel(*COFRE)
        base = BASE_LEGAL[finalidade]
        resposta: dict[str, Any] = {"cliente_id": cliente_id, "finalidade": finalidade, "base_legal": base}
        if base != "base-consentimento":
            cadastro.registro("clientes", cliente_id, "Cliente")
            resposta |= {
                "permitido": True,
                "motivo": "Uso necessário para executar o contrato pedido pela cliente.",
            }
        else:
            c = await consentimento_de(cliente_id, finalidade)
            if c is None:
                resposta |= {
                    "permitido": False,
                    "motivo": "A cliente não concedeu consentimento para esta finalidade.",
                }
            else:
                fim = c["estado"].get("vigencia_fim", c["fim"]) if c.get("estado") else c["fim"]
                vencido = c.get("estado", {}).get("status") == "fora" or fim < date.today().isoformat()
                resposta |= {
                    "consentimento_id": c["id"],
                    "vigencia": {"inicio": c["inicio"], "fim": fim},
                    "permitido": not vencido,
                    "motivo": (
                        f"Consentimento vencido em {fim}. É preciso pedir renovação à cliente."
                        if vencido
                        else "Consentimento vigente."
                    ),
                }
        return {**resposta, "aviso": aviso} if aviso else resposta

    @mcp.tool(
        description=(
            "Pede à cliente, pelo app, a renovação de um consentimento vencido. "
            "A cliente confirma em alguns segundos; depois, verifique de novo."
        )
    )
    async def solicitar_renovacao(cliente_id: str, finalidade: str) -> dict[str, Any]:
        finalidade_valida(finalidade)
        c = await consentimento_de(cliente_id, finalidade)
        if c is None:
            raise ToolError("Não há consentimento anterior para renovar; peça um novo consentimento.")
        pedido = {
            "pedido_id": novo_id("renovacao"),
            "cliente_id": cliente_id,
            "consentimento_id": c["id"],
            "finalidade": finalidade,
            "status": "aguardando_cliente",
            "criado_em": agora(),
        }
        await estado.salvar("renovacao", pedido["pedido_id"], pedido)
        return {**pedido, "mensagem": "Pedido enviado ao app da cliente."}

    # --- Distração ----------------------------------------------------------------

    @mcp.tool(description="Revoga um consentimento da cliente. Irreversível sem novo aceite.")
    async def revogar(consentimento_id: str) -> dict[str, Any]:
        cadastro.registro("consentimentos", consentimento_id, "Consentimento")
        await estado.salvar(
            "revogacao", consentimento_id, {"consentimento_id": consentimento_id, "em": agora()}
        )
        return {"consentimento_id": consentimento_id, "status": "revogado"}

    @mcp.tool(description="Histórico de consentimentos da cliente.")
    async def listar_historico(cliente_id: str) -> dict[str, Any]:
        cadastro.registro("clientes", cliente_id, "Cliente")
        itens = [
            {"id": ident, **c}
            for ident, c in cadastro.dados()["consentimentos"].items()
            if c["cliente"] == cliente_id
        ]
        return {"cliente_id": cliente_id, "consentimentos": itens}

    return mcp
