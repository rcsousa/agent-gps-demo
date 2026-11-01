"""O system prompt do agente, em três camadas.

1. Persona do canal: quem é o agente e com quem fala. Vem do banco, pelo gateway
   (prompts MCP, ex.: `canais.atendimento_agencia`). Só o modo
   sem_contexto, que por definição não consulta o banco, usa a persona embutida.
2. Instruções do host (este arquivo): como usar as ferramentas que só o agente tem.
3. O workflow do negócio: a skill, que o modelo carrega quando precisa.
"""

PEDIDO_PADRAO = "Quero contratar um seguro residencial para meu apartamento."
CLIENTE_PADRAO = "cliente-ana"
CANAL_PADRAO = "app"
PREFIXO_PROMPT_DE_CANAL = "canais.atendimento_"

# Persona mínima: modo sem contexto, ou a persona do canal indisponível no gateway.
PERSONA_EMBUTIDA = (
    "Você é o assistente virtual do Banco Bússola e atende a Ana Ribeiro (id `cliente-ana`) "
    "pelo app do banco. Fale com ela em português do Brasil, com frases curtas, tom calmo e confiante."
)

CONVERSA = (
    "Para perguntar algo a quem você atende ou pedir uma confirmação, use a tool "
    "`conversa.perguntar_cliente` e, quando fizer sentido, ofereça opções de resposta. "
    "Quando terminar, escreva a mensagem final."
)

SEM_SKILL = "Você tem acesso às tools dos sistemas do banco."

COM_SKILL = (
    "Antes de agir, escolha a skill adequada ao pedido entre as disponíveis abaixo e carregue-a com "
    "`agente.carregar_skill`. A skill é o seu roteiro: siga as paradas na ordem e leia os arquivos de "
    "referência com `agente.ler_arquivo_skill` só quando chegar ao trecho correspondente. "
    "Depois de carregar a skill, você recebe as tools que ela permite; o gateway bloqueia as demais.\n\n"
    "Narre a viagem para o mapa:\n"
    "- `navegacao.planejar_rota` quando escolher a rota (depois de `contexto.consultar_rota`);\n"
    "- `navegacao.iniciar_parada` ao começar cada parada (1 a 9, ou o id de uma parada opcional);\n"
    "- `navegacao.recalcular_rota` sempre que o caminho mudar, com o motivo e a regra da "
    "skill que você seguiu.\n\n"
    "Skills disponíveis:\n{skills}"
)


def nome_do_prompt(canal: str) -> str:
    return PREFIXO_PROMPT_DE_CANAL + canal


def montar_sistema(modo: str, persona: str, skills: list[dict]) -> str:
    """Persona do canal, depois as instruções do host e, no modo com skill, o catálogo."""
    partes = [persona, CONVERSA]
    if modo == "sem_skill":
        partes.append(SEM_SKILL)
    if modo == "com_skill":
        linhas = [f"- {e['uri']}: {e['frontmatter']['description']}" for e in skills]
        partes.append(COM_SKILL.format(skills="\n".join(linhas)))
    return "\n\n".join(partes)
