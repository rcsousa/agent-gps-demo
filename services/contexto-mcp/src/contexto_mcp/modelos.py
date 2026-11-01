"""Modelos de resposta das tools contexto.*.

Toda entidade e toda relação devolvida carrega a sua proveniência:
a proveniência governa a consequência.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field


class Proveniencia(BaseModel):
    fonte: str
    data: str
    responsavel: str
    confianca: str


class Estado(BaseModel):
    status: str | None = None
    latencia_ms: int | None = None
    custo_estimado: float | None = None
    vigencia_inicio: str | None = None
    vigencia_fim: str | None = None


class EntidadeResumo(BaseModel):
    id: str
    tipo: str
    tipo_exibicao: str
    nome: str
    bairro: str


class Entidade(EntidadeResumo):
    descricao: str
    atributos: dict[str, Any]
    estado: Estado | None
    proveniencia: Proveniencia


class Relacao(BaseModel):
    tipo: str
    sentido: Literal["saida", "entrada"]
    entidade: EntidadeResumo
    atributos: dict[str, Any]
    proveniencia: Proveniencia


class RespostaEntidade(BaseModel):
    entidade: Entidade
    relacoes: list[Relacao]


class RespostaBusca(BaseModel):
    total: int
    entidades: list[EntidadeResumo]


class RegraAplicavel(BaseModel):
    regra: Entidade
    distancia: int = Field(description="Quantos saltos separam a regra do alvo.")
    caminho: list[str] = Field(description="Tipos de relação percorridos até a regra.")


class RespostaRegras(BaseModel):
    alvo: EntidadeResumo
    regras: list[RegraAplicavel]


class ItemEstado(BaseModel):
    entidade: EntidadeResumo
    estado: Estado
    proveniencia: Proveniencia


class RespostaEstado(BaseModel):
    itens: list[ItemEstado]


class ProvenienciaRelacao(BaseModel):
    tipo: str
    de: str
    para: str
    proveniencia: Proveniencia


class RespostaProveniencia(BaseModel):
    alvo: EntidadeResumo
    proveniencia: Proveniencia
    relacoes: list[ProvenienciaRelacao] = []


class ParadaRota(BaseModel):
    ordem: int
    numero: int | None
    id: str
    nome: str
    bairro: str
    tempo_base_s: int
    usa: list[ItemEstado]


class Alerta(BaseModel):
    entidade: EntidadeResumo
    status: str
    mensagem: str


class Estimativa(BaseModel):
    tempo_s: int
    tempo_texto: str
    custo_operacional: float
    risco: Literal["baixo", "medio", "alto"]
    premio_anual_referencia: float | None
    bloqueada: bool


class Rota(BaseModel):
    id: str
    nome: str
    descricao: str
    criterio: str
    paradas: list[ParadaRota]
    apis: list[ItemEstado]
    estimativa: Estimativa
    alertas: list[Alerta]


class RespostaRota(BaseModel):
    jornada: EntidadeResumo
    rotas: list[Rota]
