"""Provedor Azure OpenAI: SDK `openai`, Chat Completions com tools.

Mesmo contrato do provedor Anthropic: o motor não percebe a troca.
"""

import json
from typing import Any

from openai import AsyncAzureOpenAI

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

MAX_TOKENS = 16000


class SessaoAzureOpenAI:
    provedor = "azure_openai"

    def __init__(
        self,
        sistema: str,
        pedido: str,
        *,
        endpoint: str = "",
        api_key: str = "",
        deployment: str = "",
        api_version: str = "",
        cliente: Any = None,
    ) -> None:
        if cliente is None and not (endpoint and api_key and deployment and api_version):
            raise ErroProvedor(
                "Azure OpenAI incompleto: preencha AZURE_OPENAI_ENDPOINT, _API_KEY, _DEPLOYMENT e "
                "_API_VERSION."
            )
        self.cliente = cliente or AsyncAzureOpenAI(
            azure_endpoint=endpoint, api_key=api_key, api_version=api_version
        )
        self.modelo = deployment
        self.mensagens: list[dict[str, Any]] = [
            {"role": "system", "content": sistema},
            {"role": "user", "content": pedido},
        ]

    async def passo(self, tools: list[DefinicaoTool]) -> Passo:
        parametros: dict[str, Any] = {
            "model": self.modelo,
            "messages": self.mensagens,
            "max_completion_tokens": MAX_TOKENS,
        }
        if tools:
            parametros["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": nome_para_api(t.nome),
                        "description": t.descricao,
                        "parameters": t.esquema,
                    },
                }
                for t in tools
            ]
        resposta = await self.cliente.chat.completions.create(**parametros)
        escolha = resposta.choices[0]
        mensagem = escolha.message
        chamadas_api = mensagem.tool_calls or []

        historico: dict[str, Any] = {"role": "assistant", "content": mensagem.content or ""}
        if chamadas_api:
            historico["tool_calls"] = [
                {
                    "id": c.id,
                    "type": "function",
                    "function": {"name": c.function.name, "arguments": c.function.arguments},
                }
                for c in chamadas_api
            ]
        self.mensagens.append(historico)

        detalhes = getattr(resposta.usage, "prompt_tokens_details", None)
        uso = Uso(
            entrada=resposta.usage.prompt_tokens or 0,
            saida=resposta.usage.completion_tokens or 0,
            cache_leitura=(getattr(detalhes, "cached_tokens", 0) or 0) if detalhes else 0,
        )
        texto = mensagem.content or ""
        if escolha.finish_reason == "content_filter":
            return Passo(
                texto=texto or "O provedor bloqueou a resposta.", fim=True, motivo_parada="recusa", uso=uso
            )
        if escolha.finish_reason == "length":
            return Passo(texto=texto, fim=True, motivo_parada="limite_de_tokens", uso=uso)

        chamadas = []
        for c in chamadas_api:
            try:
                argumentos = json.loads(c.function.arguments or "{}")
            except json.JSONDecodeError:
                argumentos = {"_erro": "argumentos em JSON inválido", "_bruto": c.function.arguments}
            chamadas.append(ChamadaTool(id=c.id, nome=nome_da_api(c.function.name), argumentos=argumentos))
        return Passo(
            texto=texto, chamadas=chamadas, fim=not chamadas, motivo_parada=escolha.finish_reason, uso=uso
        )

    def adicionar_resultados(self, resultados: list[ResultadoTool]) -> None:
        for r in resultados:
            self.mensagens.append({"role": "tool", "tool_call_id": r.id, "content": r.texto})
