"""Canais de atendimento: a persona do agente em cada canal, como prompts MCP.

Cada arquivo em `prompts/` é um canal da ontologia (`canal-app`, `canal-agencia`...).
O frontmatter diz quem é o interlocutor; o corpo é a persona, em pt-BR. O agente
compõe o próprio system prompt com ela: o jeito de atender vem do banco, não do código.
"""

from dataclasses import dataclass
from pathlib import Path

from mcp.server.mcpserver import MCPServer

from bussola_comum import cadastro
from bussola_comum.dominio import ConfigDominio, preparar_dominio
from bussola_comum.estado_vivo import EstadoVivo
from bussola_comum.saude import Checagem
from bussola_comum.skills import ler_frontmatter

NOME = "canais-mcp"
PASTA_PADRAO = Path(__file__).resolve().parents[2] / "prompts"
CAMPOS = ("name", "canal", "title", "description", "interlocutor")


class Config(ConfigDominio):
    servico_nome: str = NOME


class PromptInvalido(ValueError):
    pass


@dataclass(frozen=True)
class PromptDeCanal:
    nome: str
    canal: str
    titulo: str
    descricao: str
    interlocutor: str
    corpo: str

    def renderizar(self, cliente_id: str) -> str:
        # Cliente fora do cadastro: a persona segue sem nome, em vez de inventar um.
        nome = cadastro.dados()["clientes"].get(cliente_id, {}).get("nome", "a cliente")
        return self.corpo.replace("{cliente_nome}", nome).replace("{cliente_id}", cliente_id)


def carregar_prompt(arquivo: Path) -> PromptDeCanal:
    texto = arquivo.read_text(encoding="utf-8")
    frontmatter = ler_frontmatter(texto)
    faltando = [c for c in CAMPOS if not frontmatter.get(c)]
    if faltando:
        raise PromptInvalido(f"{arquivo.name}: frontmatter sem {', '.join(faltando)}.")
    if frontmatter["name"] != f"atendimento_{arquivo.stem}":
        raise PromptInvalido(f"{arquivo.name}: name deve ser atendimento_{arquivo.stem}.")
    corpo = texto[texto.find("\n---\n", 4) + 5 :].strip()
    return PromptDeCanal(
        nome=frontmatter["name"],
        canal=frontmatter["canal"],
        titulo=frontmatter["title"],
        descricao=frontmatter["description"],
        interlocutor=frontmatter["interlocutor"],
        corpo=corpo,
    )


def carregar_prompts(pasta: Path = PASTA_PADRAO) -> dict[str, PromptDeCanal]:
    return {p.nome: p for p in map(carregar_prompt, sorted(pasta.glob("*.md")))}


def criar_servidor(
    estado: EstadoVivo | None = None,
    checagens: dict[str, Checagem] | None = None,
    pasta: Path = PASTA_PADRAO,
) -> MCPServer:
    mcp, _ = preparar_dominio(
        NOME, "Canais de atendimento: a persona do agente em cada canal", Config(), estado, checagens
    )

    def registrar(prompt: PromptDeCanal) -> None:
        def renderizar(cliente_id: str) -> str:
            return prompt.renderizar(cliente_id)

        mcp.prompt(
            name=prompt.nome,
            title=prompt.titulo,
            description=f"{prompt.descricao} Canal: {prompt.canal}. Interlocutor: {prompt.interlocutor}.",
        )(renderizar)

    for prompt in carregar_prompts(pasta).values():
        registrar(prompt)
    return mcp
