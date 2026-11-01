"""Contrato único dos provedores de LLM.

O motor de execução só conhece `SessaoLLM`: trocar Anthropic por Azure OpenAI
(ou pelo roteiro de ensaio) não muda nenhum fluxo. Cada sessão guarda o próprio
histórico no formato do seu provedor e só acrescenta a ele, nunca edita.
"""

from dataclasses import dataclass, field
from typing import Any, Protocol

SEPARADOR_API = "__"


def nome_para_api(nome: str) -> str:
    """`cliente.obter_perfil` → `cliente__obter_perfil` (as APIs não aceitam ponto em nome de tool)."""
    return nome.replace(".", SEPARADOR_API)


def nome_da_api(nome: str) -> str:
    return nome.replace(SEPARADOR_API, ".", 1)


@dataclass(frozen=True)
class DefinicaoTool:
    nome: str  # nome qualificado, com ponto: cliente.obter_perfil
    descricao: str
    esquema: dict[str, Any]


@dataclass(frozen=True)
class ChamadaTool:
    id: str
    nome: str  # nome qualificado, com ponto
    argumentos: dict[str, Any]


@dataclass
class Uso:
    entrada: int = 0
    saida: int = 0
    cache_leitura: int = 0
    cache_escrita: int = 0

    def somar(self, outro: "Uso") -> None:
        self.entrada += outro.entrada
        self.saida += outro.saida
        self.cache_leitura += outro.cache_leitura
        self.cache_escrita += outro.cache_escrita


@dataclass
class Passo:
    texto: str = ""
    chamadas: list[ChamadaTool] = field(default_factory=list)
    fim: bool = False
    motivo_parada: str = ""
    uso: Uso = field(default_factory=Uso)


@dataclass(frozen=True)
class ResultadoTool:
    id: str
    texto: str
    erro: bool = False


class SessaoLLM(Protocol):
    provedor: str
    modelo: str

    async def passo(self, tools: list[DefinicaoTool]) -> Passo:
        """Pede ao modelo o próximo passo, com as tools disponíveis agora."""
        ...

    def adicionar_resultados(self, resultados: list[ResultadoTool]) -> None:
        """Devolve ao modelo os resultados das chamadas do último passo."""
        ...


class ErroProvedor(RuntimeError):
    """Falha de configuração ou de chamada ao provedor, com mensagem em pt-BR."""
