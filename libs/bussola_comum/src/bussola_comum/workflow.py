"""Workflow de uma skill: pré-requisitos de negócio que o gateway transforma em lei.

O `workflow.yaml` da skill diz o que precisa ter acontecido, na mesma execução,
antes de cada tool. O gateway guarda os fatos (tool + resultado) de cada execução
e, com a skill ativa, bloqueia a chamada fora de ordem (contramão).

Formato:

    pre-requisitos:
      seguradoras.cotar_seguro:
        - risco.consultar_elegibilidade                  # a tool deu certo
        - consentimento.verificar: { permitido: true }   # e o resultado tinha estes campos
        - qualquer:                                      # uma das alternativas basta
            - seguradoras.gerar_proposta: { exige_aprovacao_humana: false }
            - atendimento.consultar_aprovacao: { status: aprovada }
    impedimentos:
      pagamentos.processar_pagamento: [risco.agendar_vistoria]   # depois desta, não pode
"""

from dataclasses import dataclass, field
from typing import Any

import yaml

ARQUIVO = "workflow.yaml"


class WorkflowInvalido(ValueError):
    pass


@dataclass(frozen=True)
class Condicao:
    tool: str
    campos: dict[str, Any] = field(default_factory=dict)

    def satisfeita(self, fatos: list[dict[str, Any]]) -> bool:
        return any(
            f["tool"] == self.tool
            and all((f.get("resultado") or {}).get(k) == v for k, v in self.campos.items())
            for f in fatos
        )

    def descrever(self) -> str:
        if not self.campos:
            return self.tool
        return f"{self.tool} com " + ", ".join(f"{k} = {_valor(v)}" for k, v in self.campos.items())


@dataclass(frozen=True)
class Requisito:
    alternativas: tuple[Condicao, ...]

    def satisfeito(self, fatos: list[dict[str, Any]]) -> bool:
        return any(c.satisfeita(fatos) for c in self.alternativas)

    def descrever(self) -> str:
        return " ou ".join(c.descrever() for c in self.alternativas)


@dataclass(frozen=True)
class Workflow:
    pre_requisitos: dict[str, tuple[Requisito, ...]]
    impedimentos: dict[str, tuple[str, ...]]

    def tools_citadas(self) -> set[str]:
        citadas = set(self.pre_requisitos) | set(self.impedimentos)
        for requisitos in self.pre_requisitos.values():
            citadas |= {c.tool for r in requisitos for c in r.alternativas}
        for impeditivas in self.impedimentos.values():
            citadas |= set(impeditivas)
        return citadas

    def faltando(self, tool: str, fatos: list[dict[str, Any]]) -> str | None:
        """Por que a tool não pode ser chamada agora, ou None se pode."""
        aconteceu = [i for i in self.impedimentos.get(tool, ()) if any(f["tool"] == i for f in fatos)]
        if aconteceu:
            return f"{tool} não pode ser chamada depois de {', '.join(aconteceu)}"
        pendentes = [r.descrever() for r in self.pre_requisitos.get(tool, ()) if not r.satisfeito(fatos)]
        if pendentes:
            return f"{tool} exige antes: {'; '.join(pendentes)}"
        return None


def _valor(v: Any) -> str:
    return {True: "true", False: "false"}.get(v, str(v)) if isinstance(v, bool) else str(v)


def _condicao(item: Any) -> Condicao:
    if isinstance(item, str):
        return Condicao(item)
    if isinstance(item, dict) and len(item) == 1:
        tool, campos = next(iter(item.items()))
        if isinstance(campos, dict):
            return Condicao(tool, campos)
    raise WorkflowInvalido(f"Condição inválida: {item!r}")


def _requisito(item: Any) -> Requisito:
    if isinstance(item, dict) and set(item) == {"qualquer"}:
        return Requisito(tuple(_condicao(c) for c in item["qualquer"]))
    return Requisito((_condicao(item),))


def carregar(texto: str) -> Workflow:
    dados = yaml.safe_load(texto) or {}
    if not isinstance(dados, dict) or set(dados) - {"pre-requisitos", "impedimentos"}:
        raise WorkflowInvalido("O workflow tem só `pre-requisitos` e `impedimentos`.")
    return Workflow(
        pre_requisitos={
            tool: tuple(_requisito(r) for r in requisitos)
            for tool, requisitos in (dados.get("pre-requisitos") or {}).items()
        },
        impedimentos={tool: tuple(lista) for tool, lista in (dados.get("impedimentos") or {}).items()},
    )
