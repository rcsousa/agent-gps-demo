"""Provedor Anthropic: SDK oficial, laço manual de tools.

As tools chegam do MCP gateway, por isso o laço é manual (o motor executa cada
chamada pelo gateway e devolve o resultado). O histórico guarda os blocos de
conteúdo exatamente como a API os devolveu e só cresce: é o que o pensamento
preservado dos modelos atuais exige.
"""

import asyncio
import logging
from typing import Any

from anthropic import AsyncAnthropic, AsyncAnthropicFoundry, RateLimitError

from agent.llm.base import (
    ChamadaTool,
    DefinicaoTool,
    ErroProvedor,
    Passo,
    ResultadoTool,
    Uso,
    nome_da_api,
    nome_para_api,
)

BETA_FALLBACK = "server-side-fallback-2026-07-01"
MAX_TOKENS = 16000
# Limite de tokens por minuto (comum em deployments do Foundry): espera o que a API pedir e tenta de novo.
TENTATIVAS_NO_LIMITE = 4
ESPERA_PADRAO_S = 60

log = logging.getLogger("agent.llm.anthropic")


class SessaoAnthropic:
    provedor = "anthropic"

    def __init__(
        self,
        sistema: str,
        pedido: str,
        *,
        modelo: str,
        esforco: str,
        fallbacks: bool,
        api_key: str = "",
        plataforma: str = "api",
        foundry_base_url: str = "",
        foundry_api_key: str = "",
        cliente: Any = None,
        dormir: Any = asyncio.sleep,
    ) -> None:
        self.plataforma = plataforma
        self.dormir = dormir
        if cliente is None and plataforma == "foundry":
            if not (foundry_base_url and foundry_api_key):
                raise ErroProvedor(
                    "Microsoft Foundry incompleto: preencha ANTHROPIC_FOUNDRY_BASE_URL e "
                    "ANTHROPIC_FOUNDRY_API_KEY no .env, ou use o provedor roteiro."
                )
            cliente = AsyncAnthropicFoundry(api_key=foundry_api_key, base_url=foundry_base_url)
        if cliente is None and not api_key:
            raise ErroProvedor(
                "ANTHROPIC_API_KEY não configurada. Use o provedor roteiro ou preencha o .env."
            )
        self.cliente = cliente or AsyncAnthropic(api_key=api_key)
        self.modelo = modelo
        self.esforco = esforco
        # O Foundry não oferece fallback do lado do servidor: lá ele fica sempre desligado.
        self.fallbacks = fallbacks and plataforma != "foundry"
        # O system prompt não muda durante a execução: fica em cache.
        self.sistema = [{"type": "text", "text": sistema, "cache_control": {"type": "ephemeral"}}]
        self.mensagens: list[dict[str, Any]] = [{"role": "user", "content": pedido}]

    async def passo(self, tools: list[DefinicaoTool]) -> Passo:
        parametros: dict[str, Any] = {
            "model": self.modelo,
            "max_tokens": MAX_TOKENS,
            "system": self.sistema,
            "messages": self.mensagens,
            "output_config": {"effort": self.esforco},
            # Cache automático no último bloco: o histórico, que cresce a cada passo, também é reaproveitado.
            "cache_control": {"type": "ephemeral"},
        }
        if tools:
            parametros["tools"] = [
                {"name": nome_para_api(t.nome), "description": t.descricao, "input_schema": t.esquema}
                for t in tools
            ]
        if self.fallbacks:
            # Se o modelo recusar, o servidor tenta outro modelo adequado à categoria da recusa.
            parametros |= {"betas": [BETA_FALLBACK], "fallbacks": "default"}

        resposta = await self._criar(parametros)
        self.mensagens.append({"role": "assistant", "content": resposta.content})

        uso = Uso(
            entrada=resposta.usage.input_tokens or 0,
            saida=resposta.usage.output_tokens or 0,
            cache_leitura=resposta.usage.cache_read_input_tokens or 0,
            cache_escrita=resposta.usage.cache_creation_input_tokens or 0,
        )
        texto = "".join(b.text for b in resposta.content if b.type == "text")
        motivo = resposta.stop_reason

        if motivo == "refusal":
            return Passo(
                texto=texto or "O modelo recusou a tarefa.", fim=True, motivo_parada="recusa", uso=uso
            )
        if motivo == "pause_turn":
            # Turno pausado do lado do servidor: o próximo passo continua de onde parou.
            return Passo(texto=texto, motivo_parada="pausa", uso=uso)
        if motivo == "max_tokens":
            return Passo(texto=texto, fim=True, motivo_parada="limite_de_tokens", uso=uso)

        chamadas = [
            ChamadaTool(id=b.id, nome=nome_da_api(b.name), argumentos=dict(b.input or {}))
            for b in resposta.content
            if b.type == "tool_use"
        ]
        return Passo(texto=texto, chamadas=chamadas, fim=not chamadas, motivo_parada=motivo or "", uso=uso)

    async def _criar(self, parametros: dict[str, Any]) -> Any:
        for tentativa in range(TENTATIVAS_NO_LIMITE + 1):
            try:
                return await self.cliente.beta.messages.create(**parametros)
            except RateLimitError as erro:
                if tentativa == TENTATIVAS_NO_LIMITE:
                    raise
                espera = _segundos_de_espera(erro)
                log.warning("Limite de tokens atingido; nova tentativa em %s s.", espera)
                await self.dormir(espera)
        raise AssertionError("inalcançável")

    def adicionar_resultados(self, resultados: list[ResultadoTool]) -> None:
        # Todos os resultados de um passo voltam numa única mensagem.
        self.mensagens.append(
            {
                "role": "user",
                "content": [
                    {"type": "tool_result", "tool_use_id": r.id, "content": r.texto, "is_error": r.erro}
                    for r in resultados
                ],
            }
        )


def _segundos_de_espera(erro: RateLimitError) -> float:
    cabecalhos = getattr(getattr(erro, "response", None), "headers", None) or {}
    try:
        return min(float(cabecalhos.get("retry-after", ESPERA_PADRAO_S)), 120.0)
    except ValueError:
        return ESPERA_PADRAO_S
