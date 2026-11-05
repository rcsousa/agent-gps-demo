"""Autenticação da demo: quem não está logado não vê nenhuma parte da experiência.

O nginx do web pergunta a este serviço, a cada requisição, se a sessão é válida (auth_request em
/verificar). Só a tela de login (/entrar/) e as rotas /auth/* passam sem sessão. Os usuários vêm
do .env (AUTH_USUARIOS), com a senha em hash scrypt; ver scripts/criar-usuario.sh.
"""

import logging
import re
import secrets
import time
from collections import defaultdict, deque

from fastapi import FastAPI, Header, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from auth import senhas, sessao
from bussola_comum.config import ConfigBase
from bussola_comum.saude import rota_saude

log = logging.getLogger("auth")

SEGREDO_DE_EXEMPLO = "troque-este-segredo"
PREFIXO_DE_SERVICO = "servico:"  # sessões internas (testes, ensaio), emitidas só dentro da rede
NOME_VALIDO = re.compile(r"^[a-z0-9][a-z0-9._-]{0,39}$")

# Limite de tentativas erradas por endereço: protege a senha contra adivinhação.
TENTATIVAS_MAXIMAS = 5
JANELA_DAS_TENTATIVAS_S = 300


class Config(ConfigBase):
    servico_nome: str = "auth"
    auth_usuarios: str = ""
    auth_segredo: str = ""
    auth_sessao_horas: float = 12
    auth_cookie_seguro: bool = False  # ligue quando a demo estiver atrás de HTTPS


class Credenciais(BaseModel):
    usuario: str = Field(max_length=40)
    senha: str = Field(max_length=200)


class PedidoDeSessaoInterna(BaseModel):
    nome: str = Field(default="testes", pattern=r"^[a-z0-9-]{1,30}$")


class UsuariosInvalidos(ValueError):
    pass


def ler_usuarios(texto: str) -> dict[str, str]:
    """AUTH_USUARIOS="ana=scrypt...,ricardo=scrypt..." → {"ana": "scrypt...", ...}."""
    usuarios: dict[str, str] = {}
    for item in filter(None, (parte.strip() for parte in texto.split(","))):
        nome, separador, guardado = item.partition("=")
        nome = nome.strip().lower()
        if not separador or not NOME_VALIDO.match(nome) or not guardado.startswith("scrypt."):
            raise UsuariosInvalidos(
                f"AUTH_USUARIOS: a entrada '{nome or item[:12]}' não está no formato nome=scrypt.… "
                "Gere cada linha com ./scripts/criar-usuario.sh."
            )
        usuarios[nome] = guardado.strip()
    return usuarios


class Tentativas:
    """Erros de login recentes por endereço, em memória (a demo tem um só auth)."""

    def __init__(self, maximo: int = TENTATIVAS_MAXIMAS, janela_s: float = JANELA_DAS_TENTATIVAS_S):
        self.maximo, self.janela_s = maximo, janela_s
        self._erros: dict[str, deque[float]] = defaultdict(deque)

    def _recentes(self, chave: str, agora: float) -> deque[float]:
        erros = self._erros[chave]
        while erros and agora - erros[0] > self.janela_s:
            erros.popleft()
        return erros

    def bloqueado_por(self, chave: str, agora: float | None = None) -> int:
        """Segundos até liberar, ou 0 se pode tentar."""
        agora = time.monotonic() if agora is None else agora
        erros = self._recentes(chave, agora)
        if len(erros) < self.maximo:
            return 0
        return max(1, int(self.janela_s - (agora - erros[0])))

    def errou(self, chave: str, agora: float | None = None) -> None:
        self._erros[chave].append(time.monotonic() if agora is None else agora)

    def acertou(self, chave: str) -> None:
        self._erros.pop(chave, None)


def criar_app(config: Config | None = None, tentativas: Tentativas | None = None) -> FastAPI:
    config = config or Config()
    usuarios = ler_usuarios(config.auth_usuarios)
    tentativas = tentativas or Tentativas()
    segredo = config.auth_segredo
    if not segredo:
        # Sem segredo no .env, um aleatório por subida: funciona, mas as sessões caem a cada restart
        # e as sessões internas (testes) não conseguem ser emitidas.
        segredo = secrets.token_urlsafe(32)
        log.warning("AUTH_SEGREDO vazio: usando um segredo aleatório; as sessões caem a cada restart.")
    elif segredo == SEGREDO_DE_EXEMPLO:
        log.warning("AUTH_SEGREDO ainda é o valor de exemplo do .env.example: troque antes de expor a demo.")
    if not usuarios:
        log.warning(
            "Nenhum usuário em AUTH_USUARIOS: ninguém consegue entrar. Use ./scripts/criar-usuario.sh."
        )
    duracao_s = int(config.auth_sessao_horas * 3600)

    app = FastAPI(title="auth", docs_url=None, redoc_url=None, openapi_url=None)
    app.add_api_route("/saude", rota_saude(config.servico_nome), methods=["GET"])

    def usuario_da_sessao(request: Request) -> str | None:
        usuario = sessao.validar(segredo, request.cookies.get(sessao.NOME_DO_COOKIE))
        if usuario is None:
            return None
        # Tirar alguém do .env revoga as sessões dele no próximo restart do auth.
        if usuario in usuarios or usuario.startswith(PREFIXO_DE_SERVICO):
            return usuario
        return None

    def gravar_cookie(resposta: Response, token: str) -> None:
        resposta.set_cookie(
            sessao.NOME_DO_COOKIE,
            token,
            max_age=duracao_s,
            path="/",
            httponly=True,
            samesite="lax",
            secure=config.auth_cookie_seguro,
        )

    @app.get("/verificar")
    async def verificar(request: Request) -> Response:
        """Para o auth_request do nginx: 204 com sessão válida, 401 sem."""
        usuario = usuario_da_sessao(request)
        if usuario is None:
            return Response(status_code=401)
        return Response(status_code=204, headers={"X-Bussola-Usuario": usuario})

    @app.post("/auth/entrar")
    async def entrar(credenciais: Credenciais, request: Request) -> Response:
        if not usuarios:
            return JSONResponse(
                {"erro": "sem_usuarios", "mensagem": "Nenhum usuário configurado no servidor."},
                status_code=503,
            )
        endereco = request.headers.get("x-real-ip") or (request.client.host if request.client else "?")
        espera = tentativas.bloqueado_por(endereco)
        if espera:
            return JSONResponse(
                {"erro": "muitas_tentativas", "espera_s": espera},
                status_code=429,
                headers={"Retry-After": str(espera)},
            )
        nome = credenciais.usuario.strip().lower()
        guardado = usuarios.get(nome, senhas.HASH_FICTICIO)
        if not (senhas.conferir(credenciais.senha, guardado) and nome in usuarios):
            tentativas.errou(endereco)
            log.info("Login recusado para '%s' de %s", nome[:40], endereco)
            return JSONResponse({"erro": "credenciais"}, status_code=401)
        tentativas.acertou(endereco)
        log.info("Login de '%s' de %s", nome, endereco)
        resposta = JSONResponse({"usuario": nome})
        gravar_cookie(resposta, sessao.emitir(segredo, nome, duracao_s))
        return resposta

    @app.post("/auth/sair")
    async def sair() -> Response:
        resposta = JSONResponse({"ok": True})
        resposta.delete_cookie(sessao.NOME_DO_COOKIE, path="/", samesite="lax", httponly=True)
        return resposta

    @app.get("/auth/eu")
    async def eu(request: Request) -> Response:
        usuario = usuario_da_sessao(request)
        if usuario is None:
            return JSONResponse({"erro": "sem_sessao"}, status_code=401)
        return JSONResponse({"usuario": usuario})

    @app.post("/interno/sessao")
    async def sessao_interna(
        pedido: PedidoDeSessaoInterna, authorization: str = Header(default="")
    ) -> Response:
        """Sessão para testes e ensaios dentro da rede do compose.

        O nginx não encaminha /interno: só quem está na rede interna e conhece o AUTH_SEGREDO chega aqui.
        """
        esperado = f"Bearer {config.auth_segredo}"
        if not config.auth_segredo or not secrets.compare_digest(authorization, esperado):
            return JSONResponse({"erro": "nao_autorizado"}, status_code=403)
        usuario = PREFIXO_DE_SERVICO + pedido.nome
        return JSONResponse(
            {"cookie": sessao.NOME_DO_COOKIE, "valor": sessao.emitir(segredo, usuario, duracao_s)}
        )

    return app
