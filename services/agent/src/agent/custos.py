"""Custo de uma execução em US$, pelos preços por token de cada modelo (LLM_PRECOS no .env).

A maior parte da entrada vem do cache de prompt: a leitura do cache custa uma fração
do preço de entrada (CACHE_LEITURA_FATOR) e a escrita, um acréscimo (CACHE_ESCRITA_FATOR).
"""

from typing import Any

from agent.config import Config


def precos_por_milhao(config: Config, modelo: str) -> dict[str, float] | None:
    """Preço por milhão de tokens, como o painel mostra. None se o modelo não tem preço."""
    preco = config.llm_precos.get(modelo)
    if not preco:
        return None
    return {"entrada": round(preco["entrada"] * 1_000_000, 4), "saida": round(preco["saida"] * 1_000_000, 4)}


def custo(config: Config, modelo: str, tokens: dict[str, int]) -> dict[str, Any] | None:
    """Custo em US$ por componente, com e sem cache. None se o modelo não tem preço configurado."""
    preco = config.llm_precos.get(modelo)
    if not preco:
        return None
    entrada, saida = preco["entrada"], preco["saida"]
    partes = {
        "entrada": tokens.get("entrada", 0) * entrada,
        "cache_leitura": tokens.get("cache_leitura", 0) * entrada * config.cache_leitura_fator,
        "cache_escrita": tokens.get("cache_escrita", 0) * entrada * config.cache_escrita_fator,
        "saida": tokens.get("saida", 0) * saida,
    }
    toda_a_entrada = sum(tokens.get(k, 0) for k in ("entrada", "cache_leitura", "cache_escrita"))
    return {
        **{k: round(v, 6) for k, v in partes.items()},
        "total": round(sum(partes.values()), 6),
        # O mesmo pedido sem cache de prompt: toda a entrada pelo preço cheio.
        "sem_cache": round(toda_a_entrada * entrada + tokens.get("saida", 0) * saida, 6),
    }
