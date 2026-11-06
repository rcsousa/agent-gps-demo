"""Sem login, nenhuma parte da experiência abre: páginas levam à tela de login, dados voltam 401."""

import json
import os
import re
import urllib.error
import urllib.request

import pytest
from conftest import WEB

# Um abridor sem o cookie que o conftest instala: o que um visitante sem login veria.
SEM_SESSAO = urllib.request.build_opener()


def _status_sem_sessao(caminho: str, metodo: str = "GET") -> tuple[int, str]:
    pedido = urllib.request.Request(f"{WEB}{caminho}", method=metodo, data=b"" if metodo == "POST" else None)
    try:
        with SEM_SESSAO.open(pedido, timeout=10) as resposta:
            return resposta.status, resposta.read().decode(errors="replace")
    except urllib.error.HTTPError as erro:
        return erro.code, erro.read().decode(errors="replace")


@pytest.mark.parametrize(
    "caminho",
    [
        "/",
        "/mapa?visao=raio-x",
        "/status",
        "/bastidores/",
        "/abertura/infografico.dzi",
        "/assets/qualquer.js",
        "/index.html",
        "/interno/sessao",
    ],
)
def test_paginas_e_arquivos_sem_sessao_nao_abrem(caminho):
    status, corpo = _status_sem_sessao(caminho)
    assert status == 401, caminho
    assert "/entrar/" in corpo and "Raio-X" not in corpo


@pytest.mark.parametrize(
    ("metodo", "caminho"),
    [
        ("GET", "/api/status"),
        ("GET", "/api/mapa"),
        ("POST", "/api/execucoes"),
        ("POST", "/simulador/reset"),
    ],
)
def test_dados_e_acoes_sem_sessao_voltam_401(metodo, caminho):
    status, corpo = _status_sem_sessao(caminho, metodo)
    assert status == 401 and json.loads(corpo) == {"erro": "sem_sessao"}


def test_so_a_tela_de_login_e_publica():
    status, corpo = _status_sem_sessao("/entrar/")
    assert status == 200 and "Entrar" in corpo


def test_sem_sessao_a_pagina_leva_ao_login_guardando_o_destino(pagina_sem_sessao):
    pagina_sem_sessao.goto(f"{WEB}/mapa?visao=raio-x#topo", wait_until="networkidle")
    pagina_sem_sessao.wait_for_url(re.compile(r"/entrar/\?volta="))
    assert "volta=%2Fmapa%3Fvisao%3Draio-x%23topo" in pagina_sem_sessao.url
    assert pagina_sem_sessao.get_by_role("heading", name="Entrar na demo").is_visible()
    assert pagina_sem_sessao.locator(".mapa").count() == 0


def test_login_errado_mostra_o_erro_e_nao_entra(pagina_sem_sessao):
    pagina_sem_sessao.goto(f"{WEB}/entrar/", wait_until="networkidle")
    pagina_sem_sessao.get_by_label("Usuário").fill("ninguem")
    pagina_sem_sessao.get_by_label("Senha", exact=True).fill("senha-errada-123")
    pagina_sem_sessao.get_by_role("button", name="Entrar").click()
    # O aviso do formulário (o Carbon também põe um role=alert vazio em cada campo de texto).
    alerta = pagina_sem_sessao.locator("#entrar-erro")
    alerta.wait_for()
    assert alerta.get_attribute("role") == "alert"
    assert "Não foi possível entrar" in alerta.inner_text()
    assert "/entrar/" in pagina_sem_sessao.url


def test_com_sessao_a_tela_de_login_nao_leva_para_fora_do_site(pagina):
    # Já logado, o login segue para o destino; um destino de outro site vira a abertura.
    pagina.goto(f"{WEB}/entrar/?volta=//exemplo.com/roubo", wait_until="load")
    pagina.wait_for_url(f"{WEB}/")
    assert pagina.url == f"{WEB}/"


def test_sair_encerra_a_sessao(pagina):
    pagina.goto(f"{WEB}/status", wait_until="networkidle")
    assert "Conectado como servico:e2e" in pagina.locator(".sessao__usuario").inner_text()
    pagina.get_by_role("button", name="Sair").click()
    pagina.wait_for_url(re.compile(r"/entrar/$"))
    pagina.goto(f"{WEB}/mapa", wait_until="networkidle")
    pagina.wait_for_url(re.compile(r"/entrar/\?volta="))


@pytest.mark.skipif(
    not (os.environ.get("E2E_USUARIO") and os.environ.get("E2E_SENHA")),
    reason="Defina E2E_USUARIO e E2E_SENHA (um usuário real do AUTH_USUARIOS) para testar o login de ponta a ponta.",
)
def test_login_de_verdade_volta_ao_destino(pagina_sem_sessao):
    pagina_sem_sessao.goto(f"{WEB}/mapa?visao=raio-x", wait_until="networkidle")
    pagina_sem_sessao.wait_for_url(re.compile(r"/entrar/"))
    pagina_sem_sessao.get_by_label("Usuário").fill(os.environ["E2E_USUARIO"])
    pagina_sem_sessao.get_by_label("Senha", exact=True).fill(os.environ["E2E_SENHA"])
    pagina_sem_sessao.get_by_role("button", name="Entrar").click()
    pagina_sem_sessao.wait_for_url(re.compile(r"/mapa\?visao=raio-x"))
    pagina_sem_sessao.locator(".mapa").wait_for()
