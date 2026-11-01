# Imagem única para todos os serviços Python.
# Uso: build context na raiz do repositório e --build-arg SERVICE=<pasta em services/>.
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /uvx /bin/

ARG SERVICE
ARG MODULE
ENV SERVICO_MODULO=${MODULE}
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_CACHE=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH=/opt/venv/bin:$PATH \
    PYTHONUNBUFFERED=1

# A estrutura /src espelha o repositório, para que o caminho relativo
# ../../libs/bussola_comum do pyproject funcione igual dentro e fora do container.
WORKDIR /src/services/${SERVICE}

COPY ruff.toml /src/ruff.toml
COPY libs/ /src/libs/

# Dependências primeiro, para aproveitar o cache de camadas.
COPY services/${SERVICE}/pyproject.toml ./
RUN uv sync --no-install-project

COPY services/${SERVICE}/ ./
RUN uv sync \
    && useradd --create-home --uid 1000 bussola \
    && chown -R bussola /src

USER bussola
EXPOSE 8000
CMD ["sh", "-c", "exec python -m \"$SERVICO_MODULO\""]
