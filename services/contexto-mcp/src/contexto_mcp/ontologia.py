"""Carga e validação da ontologia versionada em ontologia/*.yaml.

A ontologia é a fonte única do mapa: o seed grava no Neo4j exatamente o que
passa por aqui. Erros saem em pt-BR, com arquivo e id, todos de uma vez.
"""

from datetime import date
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ValidationError

PASTA_PADRAO = Path(__file__).resolve().parents[2] / "ontologia"
LIMITES_NOS = (150, 300)
BAIRRO_VARIAVEL = "variavel"

Primitivo = str | int | float | bool
Atributo = Primitivo | list[Primitivo]


class ErroOntologia(Exception):
    def __init__(self, problemas: list[str]) -> None:
        self.problemas = problemas
        super().__init__("Ontologia inválida:\n" + "\n".join(f"  - {p}" for p in problemas))


class Proveniencia(BaseModel):
    fonte: str
    data: date
    responsavel: str
    confianca: Literal["alta", "média", "baixa"]


class Vigencia(BaseModel):
    inicio: date
    fim: date | None = None


class Estado(BaseModel):
    status: Literal["ok", "degradado", "fora"] | None = None
    latencia_ms: int | None = None
    custo_estimado: float | None = None
    vigencia: Vigencia | None = None


class Entidade(BaseModel):
    id: str
    tipo: str
    nome: str
    descricao: str
    bairro: str | None = None
    atributos: dict[str, Atributo] = {}
    estado: Estado | None = None
    proveniencia: Proveniencia
    arquivo: str = ""


class Relacao(BaseModel):
    de: str
    tipo: str
    para: str
    atributos: dict[str, Atributo] = {}
    proveniencia: Proveniencia
    arquivo: str = ""


class TipoEntidade(BaseModel):
    bairro: str
    exibicao: str


class TipoRelacao(BaseModel):
    descricao: str
    origem: list[str]
    destino: list[str]


class Bairro(BaseModel):
    id: str
    nome: str
    cor: str
    # Região de quadras da grade: [coluna inicial, linha inicial, coluna final, linha final).
    quadras: tuple[int, int, int, int]


class Ontologia(BaseModel):
    tipos: dict[str, TipoEntidade]
    tipos_relacao: dict[str, TipoRelacao]
    mundo: dict[str, int]
    cidade: dict
    bairros: list[Bairro]
    rio: list[tuple[float, float]]
    entidades: dict[str, Entidade]
    relacoes: list[Relacao]

    def bairro(self, id_bairro: str) -> Bairro:
        return next(b for b in self.bairros if b.id == id_bairro)


def _ler_yaml(caminho: Path, problemas: list[str]) -> dict:
    try:
        return yaml.safe_load(caminho.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as erro:
        problemas.append(f"{caminho.name}: YAML inválido ({erro})")
        return {}


def _resumo_erro(erro: ValidationError) -> str:
    return "; ".join(f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in erro.errors())


def _normalizar_relacao(bruta: Any) -> dict:
    """Aceita a forma compacta [de, TIPO, para] ou o mapeamento completo."""
    if isinstance(bruta, list) and len(bruta) == 3:
        return {"de": bruta[0], "tipo": bruta[1], "para": bruta[2]}
    return dict(bruta) if isinstance(bruta, dict) else {"invalida": bruta}


def carregar_ontologia(
    pasta: Path = PASTA_PADRAO, limites: tuple[int, int] | None = LIMITES_NOS
) -> Ontologia:
    problemas: list[str] = []

    esquema = _ler_yaml(pasta / "esquema.yaml", problemas)
    cidade = _ler_yaml(pasta / "bairros.yaml", problemas)
    tipos = {k: TipoEntidade(**v) for k, v in esquema.get("tipos", {}).items()}
    tipos_relacao = {k: TipoRelacao(**v) for k, v in esquema.get("relacoes", {}).items()}
    bairros = [Bairro(**b) for b in cidade.get("bairros", [])]
    ids_bairros = {b.id for b in bairros}

    entidades: dict[str, Entidade] = {}
    relacoes: list[Relacao] = []

    for arquivo in sorted((pasta / "instancias").glob("*.yaml")):
        dados = _ler_yaml(arquivo, problemas)
        padrao = dados.get("proveniencia_padrao") or {}

        for bruta in dados.get("entidades") or []:
            ident = bruta.get("id", "?")
            try:
                entidade = Entidade(
                    **{**bruta, "proveniencia": {**padrao, **bruta.get("proveniencia", {})}},
                    arquivo=arquivo.name,
                )
            except ValidationError as erro:
                problemas.append(f"{arquivo.name} · {ident}: {_resumo_erro(erro)}")
                continue
            if entidade.id in entidades:
                problemas.append(
                    f"{arquivo.name} · {entidade.id}: id repetido "
                    f"(já existe em {entidades[entidade.id].arquivo})"
                )
                continue
            tipo = tipos.get(entidade.tipo)
            if tipo is None:
                problemas.append(f"{arquivo.name} · {entidade.id}: tipo desconhecido '{entidade.tipo}'")
                continue
            if tipo.bairro == BAIRRO_VARIAVEL:
                if entidade.bairro not in ids_bairros:
                    problemas.append(
                        f"{arquivo.name} · {entidade.id}: tipo {entidade.tipo} precisa de um bairro válido"
                    )
                    continue
            elif entidade.bairro not in (None, tipo.bairro):
                problemas.append(
                    f"{arquivo.name} · {entidade.id}: tipo {entidade.tipo} mora no bairro '{tipo.bairro}'"
                )
                continue
            else:
                entidade.bairro = tipo.bairro
            entidades[entidade.id] = entidade

        for bruta in dados.get("relacoes") or []:
            campos = _normalizar_relacao(bruta)
            try:
                relacao = Relacao(
                    **{**campos, "proveniencia": {**padrao, **campos.get("proveniencia", {})}},
                    arquivo=arquivo.name,
                )
            except ValidationError as erro:
                problemas.append(f"{arquivo.name} · relação {bruta}: {_resumo_erro(erro)}")
                continue
            relacoes.append(relacao)

    # Relações só depois de conhecer todas as entidades: os arquivos se referenciam.
    for r in relacoes:
        rotulo = f"{r.arquivo} · {r.de} -{r.tipo}-> {r.para}"
        regra = tipos_relacao.get(r.tipo)
        if regra is None:
            problemas.append(f"{rotulo}: tipo de relação desconhecido")
            continue
        origem, destino = entidades.get(r.de), entidades.get(r.para)
        if origem is None:
            problemas.append(f"{rotulo}: origem '{r.de}' não existe")
        if destino is None:
            problemas.append(f"{rotulo}: destino '{r.para}' não existe")
        if origem and "*" not in regra.origem and origem.tipo not in regra.origem:
            problemas.append(f"{rotulo}: {r.tipo} não aceita origem do tipo {origem.tipo}")
        if destino and "*" not in regra.destino and destino.tipo not in regra.destino:
            problemas.append(f"{rotulo}: {r.tipo} não aceita destino do tipo {destino.tipo}")

    if limites is not None:
        minimo, maximo = limites
        if not minimo <= len(entidades) <= maximo:
            problemas.append(f"a ontologia tem {len(entidades)} nós; o alvo é de {minimo} a {maximo}")
        vazios = ids_bairros - {e.bairro for e in entidades.values()}
        if vazios:
            problemas.append(f"bairros sem nenhuma entidade: {', '.join(sorted(vazios))}")

    if problemas:
        raise ErroOntologia(problemas)

    return Ontologia(
        tipos=tipos,
        tipos_relacao=tipos_relacao,
        mundo=cidade.get("mundo", {"largura": 1000, "altura": 700}),
        cidade=cidade.get("cidade", {}),
        bairros=bairros,
        rio=cidade.get("rio", []),
        entidades=entidades,
        relacoes=relacoes,
    )
