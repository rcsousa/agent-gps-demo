"""O gerador de diagramas acompanha o repositório: nada que existe fica de fora."""

import os
from pathlib import Path

import yaml

import diagramas

# No build do docs, o repositório é copiado para /repo; fora dele, é a raiz do checkout.
RAIZ = Path(os.environ.get("RAIZ_DO_REPOSITORIO") or Path(__file__).parents[3])


def test_arquitetura_tem_todos_os_servicos_do_compose():
    dot = diagramas.arquitetura(RAIZ)
    compose = yaml.safe_load((RAIZ / "docker-compose.yml").read_text(encoding="utf-8"))
    for nome, servico in compose["services"].items():
        if not servico.get("profiles"):
            assert f'"{nome}"' in dot, nome
    assert '"mcp-gateway" -> "cliente-mcp"' in dot


def test_ordem_da_skill_tem_todas_as_tools_do_workflow():
    pasta = RAIZ / "services/skills-mcp/skills/contratacao-seguro-residencial"
    dot = diagramas.skill(pasta)
    workflow = yaml.safe_load((pasta / "workflow.yaml").read_text(encoding="utf-8"))
    for tool in [*workflow["pre-requisitos"], *workflow["impedimentos"]]:
        assert f'"{tool}"' in dot, tool
    assert "impede" in dot


def test_ontologia_e_rotas():
    ontologia = diagramas.ontologia(RAIZ)
    assert "Consentimento" in ontologia and "Regulatório" in ontologia
    rotas = diagramas.rotas(RAIZ)
    assert "Rota assistida" in rotas and "9 · Emissão" in rotas
