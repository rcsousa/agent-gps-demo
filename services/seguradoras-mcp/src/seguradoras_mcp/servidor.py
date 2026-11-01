"""Seguradoras parceiras Âncora, Farol e Horizonte: cotação, proposta, aceite e emissão."""

import unicodedata
from functools import cache
from pathlib import Path
from typing import Any

import yaml
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from bussola_comum import cadastro
from bussola_comum.dominio import ConfigDominio, agora, novo_id, preparar_dominio, reais
from bussola_comum.estado_vivo import EstadoVivo
from bussola_comum.saude import Checagem

NOME = "seguradoras-mcp"
REGISTRO = ("sistema-registro-operacoes", "O sistema de registro de operações")


class Config(ConfigDominio):
    servico_nome: str = NOME


@cache
def catalogo() -> dict[str, Any]:
    arquivo = Path(__file__).resolve().parents[2] / "dados" / "seguradoras.yaml"
    return yaml.safe_load(arquivo.read_text(encoding="utf-8"))


def chave_seguradora(nome: str) -> str:
    """Aceita 'farol', 'seguradora-farol' ou 'Farol Seguros'."""
    sem_acento = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode().lower()
    for chave in catalogo()["seguradoras"]:
        if chave in sem_acento:
            return chave
    raise ToolError(f"Seguradora desconhecida: '{nome}'. Parceiras: Âncora, Farol e Horizonte.")


def acima_da_alcada_automatica(premio_anual: float, importancia_segurada: float) -> bool:
    limite = cadastro.dados()["alcadas"]["alcada-automatica"]
    return (
        premio_anual > limite["premio_anual_maximo"]
        or importancia_segurada > limite["importancia_segurada_maxima"]
    )


def criar_servidor(
    estado: EstadoVivo | None = None, checagens: dict[str, Checagem] | None = None
) -> MCPServer:
    mcp, estado = preparar_dominio(
        NOME,
        "Seguradoras parceiras Âncora, Farol e Horizonte: cotação e emissão",
        Config(),
        estado,
        checagens,
    )

    async def registro_obrigatorio(tipo: str, ident: str, rotulo: str) -> dict[str, Any]:
        item = await estado.obter(tipo, ident)
        if item is None:
            raise ToolError(f"{rotulo} '{ident}' não encontrado.")
        return item

    # --- Jornada -----------------------------------------------------------------

    @mcp.tool(
        description=(
            "Cota o seguro residencial da cliente numa seguradora parceira (ancora, farol ou horizonte). "
            "Por padrão usa a importância segurada do cadastro. Com `usar_laudo: true`, usa o laudo de "
            "avaliação do imóvel e herda a proveniência dele (confiança alta). `importancia_segurada` "
            "informa outro valor, que fica registrado com confiança média."
        )
    )
    async def cotar_seguro(
        cliente_id: str,
        seguradora: str,
        importancia_segurada: float | None = None,
        usar_laudo: bool = False,
    ) -> dict[str, Any]:
        chave = chave_seguradora(seguradora)
        s = catalogo()["seguradoras"][chave]
        aviso = await estado.garantir_disponivel(s["api_cotacao"], f"A API de cotação da {s['nome']}")
        imovel = await cadastro.imovel_atual(estado, cadastro.imovel_do_cliente(cliente_id))
        area = await cadastro.atual(estado, "areas", imovel["area_risco"], "Área de risco")
        if usar_laudo and importancia_segurada is not None:
            raise ToolError("Use `usar_laudo` ou `importancia_segurada`, não os dois.")
        if usar_laudo:
            laudo = cadastro.laudo(imovel["id"])
            if laudo is None:
                raise ToolError(f"Não há laudo de avaliação para o imóvel {imovel['id']}.")
            # O valor vem com a proveniência do laudo: a fonte autoritativa, sem precisar provar nada.
            valor, origem = laudo["valor_avaliado"], laudo["proveniencia"]
        elif importancia_segurada is None:
            valor, origem = imovel["importancia_segurada"], imovel["proveniencia"]
        else:
            valor = importancia_segurada
            origem = {
                "fonte": "Informado na chamada",
                "data": agora()[:10],
                "responsavel": "Agente",
                "confianca": "media",
            }
        fator = catalogo()["fator_area"][area["nivel"]]
        premio = round(valor * s["taxa"] * fator, 2)
        cotacao = {
            "cotacao_id": novo_id("cotacao"),
            "cliente_id": cliente_id,
            "seguradora": s["id"],
            "seguradora_nome": s["nome"],
            "produto_id": s["produto"],
            "produto_nome": s["produto_nome"],
            "importancia_segurada": valor,
            "premio_anual": premio,
            "premio_mensal": round(premio / 12, 2),
            "coberturas": s["coberturas"],
            "assistencias": s["assistencias"],
            "franquias": s["franquias"],
            "base_calculo": {
                "area_risco": area["id"],
                "nivel_risco": area["nivel"],
                "fator": fator,
                "origem_valor": origem,
            },
            "criada_em": agora(),
        }
        await estado.salvar("cotacao", cotacao["cotacao_id"], cotacao)
        return {**cotacao, "aviso": aviso} if aviso else cotacao

    @mcp.tool(
        description="Gera a proposta a partir de uma cotação, com resumo das coberturas para a cliente."
    )
    async def gerar_proposta(cotacao_id: str) -> dict[str, Any]:
        cotacao = await registro_obrigatorio("cotacao", cotacao_id, "Cotação")
        proposta = {
            "proposta_id": novo_id("proposta"),
            "cotacao_id": cotacao_id,
            "cliente_id": cotacao["cliente_id"],
            "seguradora": cotacao["seguradora"],
            "produto_nome": cotacao["produto_nome"],
            "premio_anual": cotacao["premio_anual"],
            "importancia_segurada": cotacao["importancia_segurada"],
            "resumo": (
                f"{cotacao['produto_nome']}: {reais(cotacao['premio_anual'])} por ano "
                f"({reais(cotacao['premio_mensal'])} por mês), cobrindo "
                + ", ".join(cotacao["coberturas"])
                + "."
            ),
            "exige_aprovacao_humana": acima_da_alcada_automatica(
                cotacao["premio_anual"], cotacao["importancia_segurada"]
            ),
            "status": "aguardando_aceite",
            "criada_em": agora(),
        }
        await estado.salvar("proposta", proposta["proposta_id"], proposta)
        return proposta

    @mcp.tool(description="Registra o aceite da cliente na proposta, com data, canal e versão.")
    async def registrar_aceite(proposta_id: str, canal: str = "app-bussola") -> dict[str, Any]:
        aviso = await estado.garantir_disponivel(*REGISTRO)
        proposta = await registro_obrigatorio("proposta", proposta_id, "Proposta")
        proposta |= {"status": "aceita", "aceite": {"canal": canal, "em": agora(), "versao_proposta": 1}}
        await estado.salvar("proposta", proposta_id, proposta)
        return {**proposta, "aviso": aviso} if aviso else proposta

    @mcp.tool(
        description=(
            "Emite a apólice com a seguradora. Exige proposta aceita e pagamento aprovado; acima da alçada "
            "automática, exige também `aprovacao_id` de um especialista. Imóvel em área de risco alto exige "
            "vistoria concluída."
        )
    )
    async def emitir_apolice(
        proposta_id: str, pagamento_id: str, aprovacao_id: str | None = None
    ) -> dict[str, Any]:
        proposta = await registro_obrigatorio("proposta", proposta_id, "Proposta")
        if proposta["status"] != "aceita":
            raise ToolError("A proposta ainda não foi aceita pela cliente.")
        pagamento = await registro_obrigatorio("pagamento", pagamento_id, "Pagamento")
        if pagamento["status"] != "aprovado":
            raise ToolError("O pagamento não está aprovado.")
        if proposta["exige_aprovacao_humana"]:
            ticket = await estado.obter("aprovacao", aprovacao_id) if aprovacao_id else None
            if not ticket or ticket["proposta_id"] != proposta_id or ticket["status"] != "aprovada":
                raise ToolError(
                    "Proposta acima da alçada automática: a emissão exige aprovação de um especialista "
                    "(atendimento.solicitar_aprovacao)."
                )
        imovel = await cadastro.imovel_atual(estado, cadastro.imovel_do_cliente(proposta["cliente_id"]))
        area = await cadastro.atual(estado, "areas", imovel["area_risco"], "Área de risco")
        vistoria = await estado.obter("vistoria", imovel["id"])
        if area["nivel"] == "alto" and not (vistoria and vistoria["status"] == "concluida"):
            raise ToolError("Imóvel em área de risco alto: a emissão exige vistoria prévia concluída.")

        s = catalogo()["seguradoras"][chave_seguradora(proposta["seguradora"])]
        aviso = await estado.garantir_disponivel(s["api_emissao"], f"A API de emissão da {s['nome']}")
        apolice = {
            "numero": f"{chave_seguradora(s['id']).upper()[:3]}-{novo_id('ap').split('-')[1].upper()}",
            "proposta_id": proposta_id,
            "cliente_id": proposta["cliente_id"],
            "seguradora": s["nome"],
            "produto_nome": proposta["produto_nome"],
            "premio_anual": proposta["premio_anual"],
            "vigencia": {"inicio": agora()[:10], "meses": 12},
            "status": "emitida",
            "emitida_em": agora(),
        }
        await estado.salvar("apolice", apolice["numero"], apolice)
        proposta["status"] = "emitida"
        await estado.salvar("proposta", proposta_id, proposta)
        return {**apolice, "aviso": aviso} if aviso else apolice

    # --- Distração ----------------------------------------------------------------

    @mcp.tool(description="Cancela uma apólice emitida. Irreversível.")
    async def cancelar_apolice(numero: str) -> dict[str, Any]:
        apolice = await registro_obrigatorio("apolice", numero, "Apólice")
        apolice["status"] = "cancelada"
        await estado.salvar("apolice", numero, apolice)
        return apolice

    @mcp.tool(description="Lista as apólices emitidas para a cliente.")
    async def listar_apolices(cliente_id: str) -> dict[str, Any]:
        apolices = [a for a in await estado.listar("apolice") if a["cliente_id"] == cliente_id]
        return {"cliente_id": cliente_id, "apolices": apolices}

    @mcp.tool(description="Abre um aviso de sinistro numa apólice.")
    async def abrir_sinistro(numero_apolice: str, descricao: str) -> dict[str, Any]:
        await registro_obrigatorio("apolice", numero_apolice, "Apólice")
        sinistro = {
            "sinistro_id": novo_id("sinistro"),
            "apolice": numero_apolice,
            "descricao": descricao,
            "em": agora(),
        }
        await estado.salvar("sinistro", sinistro["sinistro_id"], sinistro)
        return sinistro

    return mcp
