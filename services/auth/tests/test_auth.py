"""Login, sessão e bloqueio: sem sessão válida, o nginx não deixa passar nada."""

import pytest
from fastapi.testclient import TestClient

from auth import senhas, sessao
from auth.criar_usuario import main as criar_usuario
from auth.main import Config, Tentativas, UsuariosInvalidos, criar_app, ler_usuarios

SEGREDO = "segredo-de-teste"
SENHA = "uma-senha-longa"
HASH = senhas.gerar_hash(SENHA)


def _cliente(**extra) -> TestClient:
    config = Config(auth_usuarios=f"ana={HASH}", auth_segredo=SEGREDO, **extra)
    return TestClient(criar_app(config, Tentativas(maximo=3, janela_s=60)))


def _entrar(cliente: TestClient, usuario="ana", senha=SENHA):
    return cliente.post("/auth/entrar", json={"usuario": usuario, "senha": senha})


# ------------------------------------------------------------------ senhas


def test_hash_confere_so_a_senha_certa():
    assert senhas.conferir(SENHA, HASH)
    assert not senhas.conferir("outra-senha", HASH)
    assert senhas.gerar_hash(SENHA) != HASH  # sal novo a cada hash


def test_hash_cabe_no_env_sem_escapar():
    for proibido in ("$", ",", "=", " "):
        assert proibido not in HASH


def test_hash_malformado_nunca_confere():
    for ruim in ("", "scrypt", "bcrypt.1.2.3.a.b", "scrypt.x.8.1.a.b"):
        assert not senhas.conferir(SENHA, ruim)


# ------------------------------------------------------------------ sessão


def test_token_valido_adulterado_e_vencido():
    token = sessao.emitir(SEGREDO, "ana", 60, agora=1000)
    assert sessao.validar(SEGREDO, token, agora=1030) == "ana"
    assert sessao.validar(SEGREDO, token, agora=1061) is None  # venceu
    assert sessao.validar("outro-segredo", token, agora=1030) is None
    usuario, expira, nonce, assinatura = token.split(".")
    estendido = f"{usuario}.{int(expira) + 9999}.{nonce}.{assinatura}"
    assert sessao.validar(SEGREDO, estendido, agora=1030) is None  # não dá para esticar a sessão
    assert sessao.validar(SEGREDO, "lixo", agora=1030) is None
    assert sessao.validar(SEGREDO, None) is None


# ------------------------------------------------------------------ usuários do .env


def test_le_varios_usuarios():
    assert ler_usuarios(f" ana={HASH} , Ricardo={HASH},") == {"ana": HASH, "ricardo": HASH}
    assert ler_usuarios("") == {}


def test_usuario_malformado_falha_com_mensagem_clara():
    with pytest.raises(UsuariosInvalidos, match="criar-usuario"):
        ler_usuarios("ana:senha-em-texto")


# ------------------------------------------------------------------ rotas


def test_sem_sessao_o_verificar_recusa():
    assert _cliente().get("/verificar").status_code == 401


def test_login_abre_a_sessao_e_o_verificar_libera():
    cliente = _cliente()
    resposta = _entrar(cliente)
    assert resposta.status_code == 200 and resposta.json() == {"usuario": "ana"}
    cookie = resposta.headers["set-cookie"]
    assert "HttpOnly" in cookie and "SameSite=lax" in cookie and "Secure" not in cookie
    verificado = cliente.get("/verificar")
    assert verificado.status_code == 204 and verificado.headers["x-bussola-usuario"] == "ana"
    assert cliente.get("/auth/eu").json() == {"usuario": "ana"}


def test_cookie_seguro_quando_atras_de_https():
    assert "Secure" in _entrar(_cliente(auth_cookie_seguro=True)).headers["set-cookie"]


def test_nome_ignora_maiusculas():
    assert _entrar(_cliente(), usuario="  ANA ").status_code == 200


def test_senha_errada_e_usuario_inexistente_respondem_igual():
    cliente = _cliente()
    errada, inexistente = _entrar(cliente, senha="errada"), _entrar(cliente, usuario="joao")
    assert errada.status_code == inexistente.status_code == 401
    assert errada.json() == inexistente.json() == {"erro": "credenciais"}
    assert "set-cookie" not in errada.headers


def test_muitas_tentativas_bloqueiam_ate_a_senha_certa():
    cliente = _cliente()
    for _ in range(3):
        assert _entrar(cliente, senha="errada").status_code == 401
    bloqueado = _entrar(cliente)  # nem a senha certa passa durante o bloqueio
    assert bloqueado.status_code == 429 and int(bloqueado.headers["retry-after"]) > 0


def test_sair_apaga_o_cookie():
    cliente = _cliente()
    _entrar(cliente)
    assert cliente.post("/auth/sair").status_code == 200
    assert cliente.get("/verificar").status_code == 401


def test_usuario_removido_do_env_perde_a_sessao():
    token = sessao.emitir(SEGREDO, "ana", 3600)
    sem_ana = TestClient(criar_app(Config(auth_usuarios=f"ricardo={HASH}", auth_segredo=SEGREDO)))
    sem_ana.cookies.set(sessao.NOME_DO_COOKIE, token)
    assert sem_ana.get("/verificar").status_code == 401


def test_sem_usuarios_o_login_explica():
    cliente = TestClient(criar_app(Config(auth_segredo=SEGREDO)))
    resposta = _entrar(cliente)
    assert resposta.status_code == 503 and resposta.json()["erro"] == "sem_usuarios"


def test_sessao_interna_so_com_o_segredo():
    cliente = _cliente()
    assert cliente.post("/interno/sessao", json={}).status_code == 403
    errado = {"Authorization": "Bearer outro"}
    assert cliente.post("/interno/sessao", json={}, headers=errado).status_code == 403
    certo = {"Authorization": f"Bearer {SEGREDO}"}
    resposta = cliente.post("/interno/sessao", json={"nome": "e2e"}, headers=certo)
    assert resposta.status_code == 200
    cliente.cookies.set(resposta.json()["cookie"], resposta.json()["valor"])
    assert cliente.get("/auth/eu").json() == {"usuario": "servico:e2e"}


def test_sessao_interna_desligada_sem_segredo_no_env():
    cliente = TestClient(criar_app(Config(auth_usuarios=f"ana={HASH}")))
    assert cliente.post("/interno/sessao", json={}, headers={"Authorization": "Bearer "}).status_code == 403


# ------------------------------------------------------------------ criar_usuario


def test_criar_usuario_gera_a_linha_do_env(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", __import__("io").StringIO(SENHA + "\n"))
    assert criar_usuario(["Maria", "--senha-stdin"]) == 0
    linha = capsys.readouterr().out.strip()
    nome, guardado = linha.split("=", 1)
    assert nome == "maria" and senhas.conferir(SENHA, guardado)
    assert ler_usuarios(linha) == {"maria": guardado}


def test_criar_usuario_recusa_senha_curta(monkeypatch):
    monkeypatch.setattr("sys.stdin", __import__("io").StringIO("curta\n"))
    assert criar_usuario(["maria", "--senha-stdin"]) == 1
