"""Motor de regras de risco: elegibilidade, adequação, alçadas e vistoria."""

from functools import cache
from pathlib import Path
from typing import Any

import yaml
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from bussola_comum import cadastro
from bussola_comum.dominio import ConfigDominio, agora, novo_id, preparar_dominio
from bussola_comum.estado_vivo import EstadoVivo
from bussola_comum.saude import Checagem

NOME = "risco-mcp"
MOTOR = ("sistema-motor-risco", "O motor de regras de risco")
VISTORIA = ("sistema-vistoria", "A plataforma de vistorias")
USOS_RESIDENCIAIS = {"residencial_habitual", "veraneio"}
LIMITE_RENDA_PREMIO = 0.03


class Config(ConfigDominio):
    servico_nome: str = NOME


@cache
def produtos() -> dict[str, dict[str, Any]]:
    arquivo = Path(__file__).resolve().parents[2] / "dados" / "produtos.yaml"
    return yaml.safe_load(arquivo.read_text(encoding="utf-8"))["produtos"]


def produto(produto_id: str) -> dict[str, Any]:
    if produto_id not in produtos():
        raise ToolError(f"Produto '{produto_id}' não está no motor de risco. Use um residencial do catálogo.")
    return produtos()[produto_id]


def regra(ident: str, nome: str, resultado: str, detalhe: str) -> dict[str, str]:
    return {"regra_id": ident, "nome": nome, "resultado": resultado, "detalhe": detalhe}


def criar_servidor(
    estado: EstadoVivo | None = None, checagens: dict[str, Checagem] | None = None
) -> MCPServer:
    mcp, estado = preparar_dominio(NOME, "Elegibilidade, adequação e alçadas", Config(), estado, checagens)

    async def contexto_do_cliente(cliente_id: str) -> tuple[dict, dict, dict]:
        cliente = await cadastro.atual(estado, "clientes", cliente_id, "Cliente")
        imovel = await cadastro.imovel_atual(estado, cliente["imovel"])
        area = await cadastro.atual(estado, "areas", imovel["area_risco"], "Área de risco")
        return cliente, imovel, area

    def alcada_para(premio_anual: float, importancia_segurada: float) -> dict[str, Any]:
        alcadas = cadastro.dados()["alcadas"]
        for ident in ("alcada-automatica", "alcada-especialista"):
            limite = alcadas[ident]
            if (
                premio_anual <= limite["premio_anual_maximo"]
                and importancia_segurada <= limite["importancia_segurada_maxima"]
            ):
                return {"alcada_id": ident, **limite}
        return {"alcada_id": "alcada-comite", **alcadas["alcada-comite"]}

    # --- Jornada -----------------------------------------------------------------

    @mcp.tool(
        description=(
            "Avalia se a cliente e o imóvel são elegíveis a um produto residencial: uso do imóvel, região "
            "atendida, valor máximo, restrição cadastral, construção e vistoria em área de risco."
        )
    )
    async def consultar_elegibilidade(cliente_id: str, produto_id: str) -> dict[str, Any]:
        aviso = await estado.garantir_disponivel(*MOTOR)
        p = produto(produto_id)
        cliente, imovel, area = await contexto_do_cliente(cliente_id)
        regras = [
            regra(
                "regra-imovel-residencial",
                "Imóvel de uso residencial",
                "ok" if imovel["uso"] in USOS_RESIDENCIAIS else "falhou",
                f"Uso declarado: {imovel['uso']}.",
            ),
            regra(
                "regra-regiao-atendida",
                "Região atendida pela seguradora",
                "ok" if imovel["uf"] in p["ufs_atendidas"] else "falhou",
                f"Imóvel em {imovel['uf']}; a seguradora atende {', '.join(p['ufs_atendidas'])}.",
            ),
            regra(
                "regra-valor-maximo-imovel",
                "Valor máximo do imóvel",
                "ok" if imovel["importancia_segurada"] <= p["importancia_segurada_maxima"] else "falhou",
                f"Importância segurada de R$ {imovel['importancia_segurada']:,.0f}; "
                f"máximo do produto R$ {p['importancia_segurada_maxima']:,.0f}.",
            ),
            regra(
                "regra-sem-restricao-cadastral",
                "Sem restrição cadastral",
                "falhou" if cliente["restricao_cadastral"] else "ok",
                "Cliente com restrição ativa."
                if cliente["restricao_cadastral"]
                else "Nenhuma restrição ativa.",
            ),
        ]
        if p["exige_alvenaria"]:
            regras.append(
                regra(
                    "regra-construcao-alvenaria",
                    "Construção em alvenaria",
                    "ok" if imovel["construcao"] == "alvenaria" else "falhou",
                    f"Construção: {imovel['construcao']}.",
                )
            )
        vistoria_ok = await estado.obter("vistoria", imovel["id"])
        if area["nivel"] == "alto":
            regras.append(
                regra(
                    "regra-vistoria-area-risco",
                    "Vistoria em área de risco",
                    "ok" if vistoria_ok and vistoria_ok["status"] == "concluida" else "pendente",
                    f"{area['nome']} é área de risco alto ({', '.join(area['fatores'])}): "
                    "a emissão exige vistoria prévia.",
                )
            )
        pendencias = [r["regra_id"] for r in regras if r["resultado"] == "pendente"]
        falhas = [r["regra_id"] for r in regras if r["resultado"] == "falhou"]
        resposta = {
            "cliente_id": cliente_id,
            "produto_id": produto_id,
            "imovel_id": imovel["id"],
            "elegivel": not falhas and not pendencias,
            "regras": regras,
            "falhas": falhas,
            "pendencias": pendencias,
            "proveniencia_dados": imovel["proveniencia"],
        }
        return {**resposta, "aviso": aviso} if aviso else resposta

    @mcp.tool(
        description=(
            "Avalia se a oferta é adequada ao perfil e à necessidade que a cliente declarou: "
            "cobertura compatível com o imóvel, prêmio compatível com a renda e sem duplicidade."
        )
    )
    async def avaliar_adequacao(
        cliente_id: str, produto_id: str, necessidade: str, premio_anual: float | None = None
    ) -> dict[str, Any]:
        aviso = await estado.garantir_disponivel(*MOTOR)
        produto(produto_id)
        cliente, imovel, _ = await contexto_do_cliente(cliente_id)
        texto = necessidade.lower()
        criterios = [
            regra(
                "adequacao-necessidade-declarada",
                "Necessidade declarada",
                "ok"
                if any(p in texto for p in ("resid", "apart", "casa", "imóvel", "imovel", "lar"))
                else "falhou",
                f"Necessidade: “{necessidade}”.",
            ),
            regra(
                "adequacao-sem-duplicidade",
                "Sem cobertura duplicada",
                "ok"
                if not any(p.get("ramo") == "residencial" for p in cliente.get("produtos", []))
                else "falhou",
                "A cliente não tem seguro residencial ativo.",
            ),
            regra(
                "adequacao-cliente-vulneravel",
                "Cuidado com cliente vulnerável",
                "atencao" if cliente["idade"] >= 70 else "ok",
                "Explicação reforçada recomendada."
                if cliente["idade"] >= 70
                else "Sem fator de vulnerabilidade.",
            ),
        ]
        if premio_anual is not None:
            limite = cliente["renda_mensal"] * 12 * LIMITE_RENDA_PREMIO
            criterios.append(
                regra(
                    "adequacao-renda-x-premio",
                    "Prêmio compatível com a renda",
                    "ok" if premio_anual <= limite else "falhou",
                    f"Prêmio de R$ {premio_anual:,.2f} para limite de R$ {limite:,.2f} (3% da renda anual).",
                )
            )
        resposta = {
            "cliente_id": cliente_id,
            "produto_id": produto_id,
            "adequado": all(c["resultado"] != "falhou" for c in criterios),
            "criterios": criterios,
            "importancia_segurada_sugerida": imovel["importancia_segurada"],
        }
        return {**resposta, "aviso": aviso} if aviso else resposta

    @mcp.tool(
        description=(
            "Diz qual alçada pode aprovar a contratação, a partir do prêmio anual e da importância segurada. "
            "Acima da alçada automática, é obrigatório um especialista humano antes de emitir."
        )
    )
    async def verificar_alcada(premio_anual: float, importancia_segurada: float) -> dict[str, Any]:
        alcada = alcada_para(premio_anual, importancia_segurada)
        humana = alcada["alcada_id"] != "alcada-automatica"
        return {
            "alcada": alcada,
            "exige_aprovacao_humana": humana,
            "motivo": (
                "Dentro da alçada automática: pode seguir sem aprovação humana."
                if not humana
                else f"Acima da alçada automática: exige aprovação da {alcada['nome'].lower()}."
            ),
        }

    @mcp.tool(
        description="Agenda a vistoria prévia do imóvel com uma empresa credenciada. Prazo típico de 3 dias."
    )
    async def agendar_vistoria(imovel_id: str) -> dict[str, Any]:
        aviso = await estado.garantir_disponivel(*VISTORIA)
        cadastro.registro("imoveis", imovel_id, "Imóvel")
        vistoria = {
            "vistoria_id": novo_id("vistoria"),
            "imovel_id": imovel_id,
            "status": "agendada",
            "prazo_dias": 3,
            "agendada_em": agora(),
        }
        await estado.salvar("vistoria", imovel_id, vistoria)
        return {**vistoria, "aviso": aviso} if aviso else vistoria

    # --- Distração ----------------------------------------------------------------

    @mcp.tool(description="Calcula o score de crédito da cliente (0 a 1000).")
    async def calcular_score_credito(cliente_id: str) -> dict[str, Any]:
        cliente = cadastro.registro("clientes", cliente_id, "Cliente")
        score = min(1000, 500 + cliente["anos_de_relacionamento"] * 40 + cliente["renda_mensal"] // 1000)
        return {"cliente_id": cliente_id, "score": int(score), "modelo": "score-credito v7.1"}

    @mcp.tool(description="Simula um empréstimo pessoal para a cliente.")
    async def simular_emprestimo(cliente_id: str, valor: float, parcelas: int = 24) -> dict[str, Any]:
        cadastro.registro("clientes", cliente_id, "Cliente")
        taxa = 0.0189
        parcela = valor * taxa / (1 - (1 + taxa) ** -parcelas)
        return {"cliente_id": cliente_id, "valor": valor, "parcelas": parcelas, "parcela": round(parcela, 2)}

    return mcp
