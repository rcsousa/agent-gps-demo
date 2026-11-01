"""Catálogo de skills lido de skills/<nome>/ e montado no formato da SEP-2640.

Cada skill é uma pasta com SKILL.md (frontmatter YAML + instruções) e arquivos
de apoio. Cada arquivo vira um resource `skill://<nome>/<caminho>`, com digest
SHA-256 e tamanho em bytes, que o host verifica ao ler.
"""

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

PASTA_PADRAO = Path(__file__).resolve().parents[2] / "skills"
ESQUEMA = "skill://"


class ErroSkill(Exception):
    pass


@dataclass(frozen=True)
class Arquivo:
    uri: str
    conteudo: bytes

    @property
    def digest(self) -> str:
        return "sha256:" + hashlib.sha256(self.conteudo).hexdigest()

    @property
    def texto(self) -> str:
        return self.conteudo.decode("utf-8")

    def descritor(self) -> dict[str, Any]:
        return {"uri": self.uri, "digest": self.digest, "size": len(self.conteudo)}


@dataclass(frozen=True)
class Skill:
    nome: str
    frontmatter: dict[str, Any]
    arquivos: tuple[Arquivo, ...]

    @property
    def uri(self) -> str:
        return f"{ESQUEMA}{self.nome}/SKILL.md"

    def entrada(self) -> dict[str, Any]:
        """Entrada de skills/list e skills/get: {uri, frontmatter, resources}."""
        return {
            "uri": self.uri,
            "frontmatter": self.frontmatter,
            "resources": [a.descritor() for a in self.arquivos],
        }


def ler_frontmatter(texto: str) -> dict[str, Any]:
    """Frontmatter YAML entre as duas primeiras linhas `---` do SKILL.md."""
    if not texto.startswith("---\n"):
        raise ErroSkill("SKILL.md precisa começar com frontmatter YAML (---).")
    fim = texto.find("\n---\n", 4)
    if fim < 0:
        raise ErroSkill("Frontmatter do SKILL.md sem a linha de fechamento (---).")
    dados = yaml.safe_load(texto[4:fim])
    if not isinstance(dados, dict):
        raise ErroSkill("Frontmatter do SKILL.md precisa ser um mapeamento YAML.")
    return dados


def carregar_skill(pasta: Path) -> Skill:
    skill_md = pasta / "SKILL.md"
    if not skill_md.exists():
        raise ErroSkill(f"{pasta.name}: falta o SKILL.md.")
    frontmatter = ler_frontmatter(skill_md.read_text(encoding="utf-8"))
    for campo in ("name", "description"):
        if not frontmatter.get(campo):
            raise ErroSkill(f"{pasta.name}: o frontmatter precisa de `{campo}`.")
    if frontmatter["name"] != pasta.name:
        raise ErroSkill(f"{pasta.name}: `name` ({frontmatter['name']}) precisa ser igual ao nome da pasta.")
    caminhos = sorted(p for p in pasta.rglob("*") if p.is_file())
    # SKILL.md primeiro; os demais em ordem estável.
    caminhos.sort(key=lambda p: (p.name != "SKILL.md" or p.parent != pasta, p.relative_to(pasta).as_posix()))
    arquivos = tuple(
        Arquivo(uri=f"{ESQUEMA}{pasta.name}/{p.relative_to(pasta).as_posix()}", conteudo=p.read_bytes())
        for p in caminhos
    )
    return Skill(nome=pasta.name, frontmatter=frontmatter, arquivos=arquivos)


def carregar_catalogo(pasta: Path = PASTA_PADRAO) -> dict[str, Skill]:
    """Skills por URI do SKILL.md."""
    skills = [carregar_skill(p) for p in sorted(pasta.iterdir()) if p.is_dir()]
    return {s.uri: s for s in skills}
