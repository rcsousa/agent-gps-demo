"""Tools do host: executadas pelo próprio agente, não pelo gateway.

- agente.*      leitura de skills (SEP-2640), com verificação de digest;
- navegacao.*   narração da viagem para o mapa (route.planned, step.started...);
- conversa.*    perguntas à cliente, respondidas pelo apresentador.
"""

from agent.llm.base import DefinicaoTool


def _objeto(propriedades: dict, obrigatorias: list[str]) -> dict:
    return {
        "type": "object",
        "properties": propriedades,
        "required": obrigatorias,
        "additionalProperties": False,
    }


PERGUNTAR_CLIENTE = DefinicaoTool(
    "conversa.perguntar_cliente",
    "Pergunta algo a quem você atende (a cliente ou o atendente do canal) e espera a resposta. "
    "Ofereça opções curtas quando fizer sentido.",
    _objeto(
        {
            "pergunta": {"type": "string", "description": "A pergunta, em português, para quem você atende."},
            "opcoes": {"type": "array", "items": {"type": "string"}, "description": "Respostas sugeridas."},
        },
        ["pergunta"],
    ),
)

CARREGAR_SKILL = DefinicaoTool(
    "agente.carregar_skill",
    "Carrega uma skill pelo URI do SKILL.md e devolve as instruções. Depois disso, as tools permitidas "
    "pela skill ficam disponíveis.",
    _objeto(
        {"uri": {"type": "string", "description": "Ex.: skill://contratacao-seguro-residencial/SKILL.md"}},
        ["uri"],
    ),
)

LER_ARQUIVO_SKILL = DefinicaoTool(
    "agente.ler_arquivo_skill",
    "Lê um arquivo de apoio da skill carregada (ex.: references/elegibilidade.md), pela URI completa.",
    _objeto({"uri": {"type": "string"}}, ["uri"]),
)

PLANEJAR_ROTA = DefinicaoTool(
    "navegacao.planejar_rota",
    "Anuncia no mapa a rota escolhida (rota-rapida, rota-economica ou rota-assistida) e o motivo.",
    _objeto({"rota": {"type": "string"}, "motivo": {"type": "string"}}, ["rota", "motivo"]),
)

INICIAR_PARADA = DefinicaoTool(
    "navegacao.iniciar_parada",
    "Anuncia no mapa o início de uma parada: o número (1 a 9) ou o id de uma parada opcional "
    "(ex.: parada-aprovacao-humana, parada-vistoria).",
    _objeto({"parada": {"type": ["integer", "string"]}}, ["parada"]),
)

RECALCULAR_ROTA = DefinicaoTool(
    "navegacao.recalcular_rota",
    "Anuncia no mapa que o caminho mudou: o que mudou, qual regra da skill foi seguida e a rota a seguir.",
    _objeto(
        {"motivo": {"type": "string"}, "regra": {"type": "string"}, "nova_rota": {"type": "string"}},
        ["motivo", "regra", "nova_rota"],
    ),
)

TOOLS_DE_SKILL = [CARREGAR_SKILL]
TOOLS_DA_VIAGEM = [LER_ARQUIVO_SKILL, PLANEJAR_ROTA, INICIAR_PARADA, RECALCULAR_ROTA]
NOMES_DO_HOST = {t.nome for t in [PERGUNTAR_CLIENTE, *TOOLS_DE_SKILL, *TOOLS_DA_VIAGEM]}
