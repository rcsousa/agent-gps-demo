"""Detecta, no resultado das tools, os incidentes que o agente encontrou no caminho.

Cada detecção vira um evento `incident.detected`, com a metáfora do mapa. O agente
não sabe o que o simulador fez: percebe o mundo pelas respostas, como na spec.
"""

import re
from typing import Any

PROVENIENCIA = "bussola/proveniencia"
# O SDK MCP prefixa erros de tool em inglês; para o mapa, só a mensagem do sistema interessa.
PREFIXO_SDK = re.compile(r"^Error executing tool [\w.]+: ")


def detectar(
    tool: str, dados: dict[str, Any], texto: str, erro: bool, meta: dict[str, Any]
) -> list[dict[str, Any]]:
    achados: list[dict[str, Any]] = []
    motivo = (meta.get(PROVENIENCIA) or {}).get("motivo")

    def achar(metafora: str, descricao: str, entidade: str | None = None) -> None:
        descricao = PREFIXO_SDK.sub("", descricao)
        achados.append({"metafora": metafora, "descricao": descricao, "tool": tool, "entidade": entidade})

    if erro and (motivo == "desligada" or "fora do ar" in texto or "interditado" in texto):
        achar("Rua interditada", texto)
    if dados.get("aviso") and "lentidão" in dados["aviso"]:
        achar("Congestionamento", dados["aviso"])
    if tool == "consentimento.verificar" and dados.get("permitido") is False:
        achar("Contramão", dados.get("motivo", "Consentimento sem validade."), dados.get("consentimento_id"))
    if tool == "risco.consultar_elegibilidade" and "regra-vistoria-area-risco" in dados.get("pendencias", []):
        achar(
            "Desvio por obra",
            "Imóvel em área de risco: a emissão exige vistoria prévia.",
            dados.get("imovel_id"),
        )
    if tool in ("risco.verificar_alcada", "seguradoras.gerar_proposta") and dados.get(
        "exige_aprovacao_humana"
    ):
        achar("Pedágio", "Acima da alçada automática: exige aprovação de um especialista.")
    if tool == "cliente.obter_imovel" and dados.get("proveniencia", {}).get("confianca") == "baixa":
        achar(
            "Ponte interditada",
            f"Dado de fonte pouco confiável: {dados['proveniencia'].get('fonte')}.",
            dados.get("id"),
        )
    if tool == "contexto.consultar_rota":
        for rota in dados.get("rotas", []):
            for alerta in rota.get("alertas", []):
                metafora = "Rua interditada" if alerta.get("status") == "fora" else "Congestionamento"
                achar(metafora, alerta.get("mensagem", ""), alerta.get("entidade", {}).get("id"))
    return achados
