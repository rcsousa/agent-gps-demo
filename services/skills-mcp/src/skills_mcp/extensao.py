"""Extensão io.modelcontextprotocol/skills (SEP-2640) sobre o SDK MCP v2.

O SDK traz o mecanismo genérico de extensões (SEP-2133); aqui ficam os dois
métodos que a SEP-2640 exige (`skills/list`, `skills/get`) e os arquivos de
cada skill como resources legíveis por `resources/read`.
"""

from mcp.server.extension import Extension, MethodBinding, ResourceBinding
from mcp.server.mcpserver.resources import TextResource
from mcp.shared.exceptions import MCPError

from bussola_comum.skills import IDENTIFICADOR, ParamsListar, ParamsObter, ResultadoListar, ResultadoObter
from skills_mcp.catalogo import Skill

PARAMETROS_INVALIDOS = -32602


class ExtensaoSkills(Extension):
    identifier = IDENTIFICADOR

    def __init__(self, skills: dict[str, Skill]) -> None:
        self.skills = skills

    def methods(self) -> list[MethodBinding]:
        async def listar(ctx, params: ParamsListar) -> ResultadoListar:
            # São poucas skills: tudo cabe numa página, e `cursor` é aceito e ignorado.
            return ResultadoListar(skills=[s.entrada() for s in self.skills.values()])

        async def obter(ctx, params: ParamsObter) -> ResultadoObter:
            skill = self.skills.get(params.uri)
            if skill is None:
                raise MCPError(code=PARAMETROS_INVALIDOS, message=f"Skill desconhecida: {params.uri}")
            return ResultadoObter(skill=skill.entrada())

        return [
            MethodBinding("skills/list", ParamsListar, listar),
            MethodBinding("skills/get", ParamsObter, obter),
        ]

    def resources(self) -> list[ResourceBinding]:
        vinculos = []
        for skill in self.skills.values():
            for arquivo in skill.arquivos:
                eh_skill_md = arquivo.uri == skill.uri
                vinculos.append(
                    ResourceBinding(
                        TextResource(
                            uri=arquivo.uri,
                            name=skill.nome if eh_skill_md else arquivo.uri.removeprefix("skill://"),
                            description=skill.frontmatter["description"] if eh_skill_md else None,
                            mime_type="text/markdown" if arquivo.uri.endswith(".md") else "text/plain",
                            text=arquivo.texto,
                        )
                    )
                )
        return vinculos
