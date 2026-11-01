"""Provedor Anthropic: SDK oficial, laço manual de tools.

As tools chegam do MCP gateway, por isso o laço é manual (o motor executa cada
chamada pelo gateway e devolve o resultado). O histórico guarda os blocos de
conteúdo exatamente como a API os devolveu e só cresce: é o que o pensamento
preservado dos modelos atuais exige.
"""

from typing import Any

from anthropic import AsyncAnthropic

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
        cliente: Any = None,
    ) -> None:
        if cliente is None and not api_key:
            raise ErroProvedor(
                "ANTHROPIC_API_KEY não configurada. Use o provedor roteiro ou preencha o .env."
            )
        self.cliente = cliente or AsyncAnthropic(api_key=api_key)
        self.modelo = modelo
        self.esforco = esforco
        self.fallbacks = fallbacks
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
        }
        if tools:
            parametros["tools"] = [
                {"name": nome_para_api(t.nome), "description": t.descricao, "input_schema": t.esquema}
                for t in tools
            ]
        if self.fallbacks:
            # Se o modelo recusar, o servidor tenta outro modelo adequado à categoria da recusa.
            parametros |= {"betas": [BETA_FALLBACK], "fallbacks": "default"}

        resposta = await self.cliente.beta.messages.create(**parametros)
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
