"""Placar: agregado da sessão por modo × modelo e a referência versionada."""

from agent import placar


def _execucao(ident, modo, modelo, cumpridas, total, segundos=10.0, custo=0.01, status="concluida"):
    return {
        "id": ident,
        "modo": modo,
        "modelo": modelo,
        "provedor": "anthropic",
        "status": status,
        "apolice": "HOR-1",
        "metricas": {
            "caso": "caminho-feliz",
            "duracao_s": segundos,
            "custo_usd": {"total": custo},
            "regras": {"cumpridas": cumpridas, "total": total, "regras": {}},
            "tools_irrelevantes": [],
        },
    }


def test_sessao_agrega_por_modo_e_modelo_e_ignora_em_andamento():
    execucoes = [
        _execucao("a", "com_skill", "haiku", 5, 5, segundos=30, custo=0.012),
        _execucao("b", "com_skill", "haiku", 4, 5, segundos=40, custo=0.014),
        _execucao("c", "sem_skill", "haiku", 3, 5),
        _execucao("d", "sem_skill", "haiku", 0, 0, status="rodando"),
    ]
    dados = placar.montar(execucoes)
    agregado = {(g["modo"], g["modelo"]): g for g in dados["sessao"]["agregado"]}
    com = agregado[("com_skill", "haiku")]
    assert (com["execucoes"], com["cumpridas"], com["total"], com["perfeitas"]) == (2, 9, 10, 1)
    assert com["segundos_medio"] == 35.0 and com["custo_medio_usd"] == 0.013
    assert [e["id"] for e in dados["sessao"]["execucoes"]] == ["a", "b", "c"]


def test_referencia_do_experimento():
    ref = placar.referencia()
    linhas = {(r["modelo"], r["modo"]): r for r in ref["linhas"]}
    assert linhas[("claude-haiku-5-5", "com_skill")]["cumpridas"] == 89
    assert linhas[("claude-opus-5-5", "sem_skill")]["total"] == 90
