"""Ontologias quebradas precisam falhar com mensagens claras."""

import shutil
from pathlib import Path

import pytest

from contexto_mcp.ontologia import PASTA_PADRAO, ErroOntologia, carregar_ontologia

ESQUEMA_MINIMO = """
proveniencia_padrao: {fonte: Teste, data: 2026-10-01, responsavel: Time, confianca: alta}
entidades:
  - {id: cliente-x, tipo: Cliente, nome: X, descricao: Cliente de teste.}
  - {id: conta-x, tipo: Conta, nome: Conta X, descricao: Conta de teste.}
relacoes:
"""


def _pasta(tmp_path: Path, instancia: str) -> Path:
    for nome in ("esquema.yaml", "bairros.yaml"):
        shutil.copy(PASTA_PADRAO / nome, tmp_path / nome)
    (tmp_path / "instancias").mkdir()
    (tmp_path / "instancias" / "teste.yaml").write_text(instancia, encoding="utf-8")
    return tmp_path


def _problemas(tmp_path: Path, instancia: str) -> list[str]:
    with pytest.raises(ErroOntologia) as erro:
        carregar_ontologia(_pasta(tmp_path, instancia), limites=None)
    return erro.value.problemas


def test_ontologia_minima_valida(tmp_path):
    ontologia = carregar_ontologia(
        _pasta(tmp_path, ESQUEMA_MINIMO + "  - [cliente-x, POSSUI, conta-x]\n"), limites=None
    )
    assert ontologia.entidades["conta-x"].bairro == "cliente"


def test_relacao_para_id_inexistente(tmp_path):
    [problema] = _problemas(tmp_path, ESQUEMA_MINIMO + "  - [cliente-x, POSSUI, conta-fantasma]\n")
    assert "destino 'conta-fantasma' não existe" in problema
    assert "teste.yaml" in problema


def test_relacao_fora_do_esquema(tmp_path):
    problemas = _problemas(tmp_path, ESQUEMA_MINIMO + "  - [conta-x, POSSUI, cliente-x]\n")
    assert any("não aceita origem do tipo Conta" in p for p in problemas)
    assert any("não aceita destino do tipo Cliente" in p for p in problemas)


def test_tipo_desconhecido(tmp_path):
    instancia = ESQUEMA_MINIMO.replace("tipo: Conta", "tipo: Contra")
    assert any("tipo desconhecido 'Contra'" in p for p in _problemas(tmp_path, instancia))


def test_proveniencia_faltando(tmp_path):
    instancia = ESQUEMA_MINIMO.replace("responsavel: Time, ", "")
    problemas = _problemas(tmp_path, instancia)
    assert any("responsavel" in p for p in problemas)


def test_id_repetido(tmp_path):
    instancia = ESQUEMA_MINIMO.replace("id: conta-x", "id: cliente-x")
    assert any("id repetido" in p for p in _problemas(tmp_path, instancia))


def test_tamanho_fora_da_faixa(tmp_path):
    with pytest.raises(ErroOntologia) as erro:
        carregar_ontologia(_pasta(tmp_path, ESQUEMA_MINIMO), limites=(150, 300))
    assert any("o alvo é de 150 a 300" in p for p in erro.value.problemas)
