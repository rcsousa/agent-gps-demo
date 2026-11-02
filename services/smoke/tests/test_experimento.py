"""Agregação do experimento com eventos sintéticos: não chama o modelo nem o mundo simulado."""

from smoke.experimento import agregar, registro


def _execucao(caso: str, modo: str, modelo: str, chamadas: list[tuple[str, dict]], apolice=None, segundos=10):
    eventos = [{"tipo": "run.started", "dados": {"modelo": modelo}}]
    eventos += [
        {"tipo": "tool.called", "dados": {"tool": tool, "status": "ok", "argumentos": argumentos}}
        for tool, argumentos in chamadas
    ]
    eventos.append(
        {
            "tipo": "run.finished",
            "dados": {
                "apolice": apolice,
                "mensagem_final": "",
                "metricas": {
                    "chamadas_tool": len(chamadas),
                    "tokens": {"entrada": 10, "cache_leitura": 90, "cache_escrita": 0, "saida": 5},
                },
            },
        }
    )
    return {"incidente": caso, "modo": modo, "segundos": segundos, "eventos": eventos}


CERTO = [
    ("consentimento.verificar", {}),
    ("cliente.obter_imovel", {}),
    ("risco.avaliar_adequacao", {}),
    ("seguradoras.gerar_proposta", {}),
    ("seguradoras.emitir_apolice", {}),
]
IMOVEL_ANTES = [CERTO[1], CERTO[0], *CERTO[2:]]


def test_soma_repeticoes_e_guarda_a_pior_execucao():
    registros = [
        registro(_execucao("caminho-feliz", "com_skill", "haiku", CERTO, apolice="HOR-1")),
        registro(_execucao("caminho-feliz", "com_skill", "haiku", IMOVEL_ANTES, apolice="HOR-2")),
        registro(
            _execucao("caminho-feliz", "sem_skill", "haiku", [("seguradoras.contratacao_expressa", {})])
        ),
    ]
    por_caso = agregar(registros, ("caso", "modo"))
    com = por_caso[("caminho-feliz", "com_skill")]
    assert (com["cumpridas"], com["total"], com["execucoes"], com["perfeitas"]) == (9, 10, 2, 1)
    assert com["pior"] == 0.8 and com["falhas"] == {"consentimento antes do imóvel": 1}

    sem = agregar(registros, ("modo",))[("sem_skill",)]
    assert sem["falhas"]["não usou atalho legado"] == 1 and sem["perfeitas"] == 0
    assert registros[0]["modelo"] == "haiku" and registros[0]["entrada"] == 100


def test_tentativa_barrada_pelo_gateway_nao_conta_como_feita():
    barrada = _execucao("caminho-feliz", "com_skill", "haiku", CERTO, apolice="HOR-1")
    # Tentou ler o imóvel cedo; o gateway barrou (fora de ordem) e o agente seguiu a ordem.
    barrada["eventos"].insert(
        1,
        {
            "tipo": "tool.called",
            "dados": {"tool": "cliente.obter_imovel", "status": "erro", "argumentos": {}},
        },
    )
    assert registro(barrada)["regras"]["consentimento antes do imóvel"]


def test_na_alcada_a_ana_quer_a_arte_ou_o_especialista():
    from smoke.experimento import _resposta_da_ana

    assert (
        _resposta_da_ana(
            "alcada-ana-excedida",
            ["Não tenho coleção. Seguir com a Farol", "Tenho coleção. Quero entender antes"],
        )
        == "Tenho coleção. Quero entender antes"
    )
    assert (
        _resposta_da_ana(
            "alcada-ana-excedida",
            ["Seguir só com o apartamento (R$ 780.000)", "Cotar com R$ 1.800.000 e enviar ao especialista"],
        )
        == "Cotar com R$ 1.800.000 e enviar ao especialista"
    )
    assert _resposta_da_ana("caminho-feliz", ["Sim", "Não"]) == "Sim"


def test_custo_com_e_sem_cache_pela_tabela_de_precos():
    from smoke.experimento import _usd, custo_usd

    tabela = {
        "modelos": {"claude-opus-5-5": {"entrada": 4.0, "saida": 20.0}},
        "cache": {"leitura": 0.1, "escrita": 1.25},
    }
    tokens = {"entrada": 1_000, "cache_leitura": 100_000, "cache_escrita": 10_000, "saida": 5_000}
    c = custo_usd("claude-opus-5-5", tokens, tabela)
    assert round(c["total"], 6) == round(0.004 + 0.04 + 0.05 + 0.1, 6)
    assert round(c["sem_cache"], 6) == round(111_000 * 0.000004 + 0.1, 6)
    assert custo_usd("outro", tokens, tabela) is None
    assert _usd(1234.5, 2) == "US$ 1.234,50"
