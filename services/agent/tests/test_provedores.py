"""Provedores de LLM com respostas de API simuladas: sem rede, sem chave."""

import json
from types import SimpleNamespace as NS

import pytest

from agent.llm.base import DefinicaoTool, ErroProvedor, ResultadoTool, nome_da_api, nome_para_api
from agent.llm.provedor_anthropic import BETA_FALLBACK, SessaoAnthropic
from agent.llm.provedor_azure import SessaoAzureOpenAI

pytestmark = pytest.mark.anyio
TOOL = DefinicaoTool("cliente.obter_perfil", "Perfil da cliente.", {"type": "object", "properties": {}})


def test_nomes_com_ponto_viram_nomes_validos_para_a_api():
    assert nome_para_api("cliente.obter_perfil") == "cliente__obter_perfil"
    assert nome_da_api("cliente__obter_perfil") == "cliente.obter_perfil"
    assert nome_da_api(nome_para_api("risco.verificar_alcada")) == "risco.verificar_alcada"


# --- Anthropic ---------------------------------------------------------------------


class AnthropicFalso:
    def __init__(self, respostas):
        self.respostas = list(respostas)
        self.pedidos: list[dict] = []
        self.beta = NS(messages=NS(create=self._criar))

    async def _criar(self, **parametros):
        self.pedidos.append(parametros)
        return self.respostas.pop(0)


def _uso(entrada=100, saida=20, cache=50):
    return NS(
        input_tokens=entrada,
        output_tokens=saida,
        cache_read_input_tokens=cache,
        cache_creation_input_tokens=0,
    )


def _sessao_anthropic(respostas, fallbacks=True):
    falso = AnthropicFalso(respostas)
    sessao = SessaoAnthropic(
        "sistema", "pedido", modelo="claude-opus-5-5", esforco="medium", fallbacks=fallbacks, cliente=falso
    )
    return sessao, falso


async def test_anthropic_tool_use_e_resultados():
    blocos = [
        NS(type="text", text="Vou consultar."),
        NS(type="tool_use", id="tu_1", name="cliente__obter_perfil", input={"cliente_id": "cliente-ana"}),
    ]
    sessao, falso = _sessao_anthropic([NS(content=blocos, stop_reason="tool_use", usage=_uso())])
    passo = await sessao.passo([TOOL])

    assert passo.texto == "Vou consultar." and not passo.fim
    assert passo.chamadas[0].nome == "cliente.obter_perfil"
    assert passo.chamadas[0].argumentos == {"cliente_id": "cliente-ana"}
    assert (passo.uso.entrada, passo.uso.saida, passo.uso.cache_leitura) == (100, 20, 50)

    pedido = falso.pedidos[0]
    assert pedido["model"] == "claude-opus-5-5"
    assert pedido["output_config"] == {"effort": "medium"}
    assert pedido["tools"][0]["name"] == "cliente__obter_perfil"
    assert pedido["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert pedido["betas"] == [BETA_FALLBACK] and pedido["fallbacks"] == "default"
    assert "temperature" not in pedido

    sessao.adicionar_resultados([ResultadoTool("tu_1", '{"nome": "Ana"}')])
    # Histórico só cresce: os blocos crus da resposta ficam como vieram.
    assert sessao.mensagens[1] == {"role": "assistant", "content": blocos}
    assert sessao.mensagens[2]["content"][0] == {
        "type": "tool_result",
        "tool_use_id": "tu_1",
        "content": '{"nome": "Ana"}',
        "is_error": False,
    }


async def test_anthropic_fim_recusa_e_limite():
    respostas = [
        NS(content=[NS(type="text", text="Pronto, Ana.")], stop_reason="end_turn", usage=_uso()),
        NS(content=[], stop_reason="refusal", usage=_uso()),
        NS(content=[NS(type="text", text="...")], stop_reason="max_tokens", usage=_uso()),
    ]
    sessao, _ = _sessao_anthropic(respostas)
    fim = await sessao.passo([])
    recusa = await sessao.passo([])
    limite = await sessao.passo([])
    assert fim.fim and fim.texto == "Pronto, Ana."
    assert recusa.fim and recusa.motivo_parada == "recusa"
    assert limite.fim and limite.motivo_parada == "limite_de_tokens"


async def test_anthropic_sem_fallback_quando_desligado():
    sessao, falso = _sessao_anthropic(
        [NS(content=[NS(type="text", text="ok")], stop_reason="end_turn", usage=_uso())], fallbacks=False
    )
    await sessao.passo([])
    assert "fallbacks" not in falso.pedidos[0] and "betas" not in falso.pedidos[0]


def test_anthropic_sem_chave_explica_o_que_fazer():
    with pytest.raises(ErroProvedor, match="ANTHROPIC_API_KEY"):
        SessaoAnthropic("s", "p", modelo="claude-opus-5-5", esforco="medium", fallbacks=True)


# --- Azure OpenAI ------------------------------------------------------------------


class AzureFalso:
    def __init__(self, respostas):
        self.respostas = list(respostas)
        self.pedidos: list[dict] = []
        self.chat = NS(completions=NS(create=self._criar))

    async def _criar(self, **parametros):
        self.pedidos.append(parametros)
        return self.respostas.pop(0)


async def test_azure_tool_calls_e_resultados():
    chamada = NS(
        id="call_1",
        function=NS(name="cliente__obter_perfil", arguments=json.dumps({"cliente_id": "cliente-ana"})),
    )
    resposta = NS(
        choices=[NS(message=NS(content=None, tool_calls=[chamada]), finish_reason="tool_calls")],
        usage=NS(prompt_tokens=80, completion_tokens=10, prompt_tokens_details=NS(cached_tokens=40)),
    )
    falso = AzureFalso([resposta])
    sessao = SessaoAzureOpenAI("sistema", "pedido", cliente=falso)
    sessao.modelo = "gpt-deployment"
    passo = await sessao.passo([TOOL])

    assert passo.chamadas[0].nome == "cliente.obter_perfil"
    assert passo.uso.cache_leitura == 40
    assert falso.pedidos[0]["tools"][0]["function"]["name"] == "cliente__obter_perfil"
    sessao.adicionar_resultados([ResultadoTool("call_1", "{}")])
    assert sessao.mensagens[-1] == {"role": "tool", "tool_call_id": "call_1", "content": "{}"}
    assert sessao.mensagens[-2]["tool_calls"][0]["id"] == "call_1"


def test_azure_incompleto_explica_o_que_falta():
    with pytest.raises(ErroProvedor, match="AZURE_OPENAI"):
        SessaoAzureOpenAI("s", "p")


# --- Microsoft Foundry (Claude na Azure) ---------------------------------------------


def test_foundry_usa_o_cliente_da_azure_e_desliga_fallbacks():
    from anthropic import AsyncAnthropicFoundry

    sessao = SessaoAnthropic(
        "s",
        "p",
        modelo="claude-opus-5-5",
        esforco="medium",
        fallbacks=True,
        plataforma="foundry",
        foundry_base_url="https://exemplo.api.cognitive.microsoft.com/anthropic/",
        foundry_api_key="chave-de-teste",
    )
    assert isinstance(sessao.cliente, AsyncAnthropicFoundry)
    assert str(sessao.cliente.base_url).startswith("https://exemplo.api.cognitive.microsoft.com/anthropic")
    assert sessao.fallbacks is False  # o Foundry não oferece fallback do lado do servidor


async def test_foundry_envia_o_deployment_sem_betas_de_fallback():
    falso = AnthropicFalso([NS(content=[NS(type="text", text="ok")], stop_reason="end_turn", usage=_uso())])
    sessao = SessaoAnthropic(
        "s",
        "p",
        modelo="claude-opus-5-5",
        esforco="medium",
        fallbacks=True,
        plataforma="foundry",
        cliente=falso,
    )
    await sessao.passo([TOOL])
    pedido = falso.pedidos[0]
    assert pedido["model"] == "claude-opus-5-5" and pedido["output_config"] == {"effort": "medium"}
    assert "betas" not in pedido and "fallbacks" not in pedido


def test_foundry_incompleto_explica_o_que_falta():
    with pytest.raises(ErroProvedor, match="ANTHROPIC_FOUNDRY_BASE_URL"):
        SessaoAnthropic("s", "p", modelo="m", esforco="medium", fallbacks=True, plataforma="foundry")


def test_config_do_foundry_exige_endpoint_e_chave():
    from agent.config import Config

    vazio = {"anthropic_foundry_base_url": "", "anthropic_foundry_api_key": ""}  # independe do .env
    assert not Config(anthropic_plataforma="foundry", anthropic_api_key="x", **vazio).llm_configurado
    assert Config(
        anthropic_plataforma="foundry",
        anthropic_foundry_base_url="https://e/anthropic/",
        anthropic_foundry_api_key="k",
    ).llm_configurado


async def test_limite_de_tokens_espera_o_que_a_api_pede_e_tenta_de_novo():
    import httpx
    from anthropic import RateLimitError

    resposta_429 = httpx.Response(
        429, headers={"retry-after": "7"}, request=httpx.Request("POST", "https://x")
    )
    limite = RateLimitError("Rate limit", response=resposta_429, body=None)
    ok = NS(content=[NS(type="text", text="ok")], stop_reason="end_turn", usage=_uso())
    falso = AnthropicFalso([limite, ok])

    async def criar(**parametros):
        falso.pedidos.append(parametros)
        resposta = falso.respostas.pop(0)
        if isinstance(resposta, Exception):
            raise resposta
        return resposta

    falso.beta = NS(messages=NS(create=criar))
    esperas: list[float] = []

    async def dormir(segundos):
        esperas.append(segundos)

    sessao = SessaoAnthropic(
        "s", "p", modelo="m", esforco="medium", fallbacks=False, cliente=falso, dormir=dormir
    )
    passo = await sessao.passo([])
    assert passo.texto == "ok" and esperas == [7.0] and len(falso.pedidos) == 2


async def test_cache_automatico_cobre_o_historico():
    sessao, falso = _sessao_anthropic(
        [NS(content=[NS(type="text", text="ok")], stop_reason="end_turn", usage=_uso())]
    )
    await sessao.passo([])
    assert falso.pedidos[0]["cache_control"] == {"type": "ephemeral"}
