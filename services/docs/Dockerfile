# Build context: raiz do repositório (o infográfico, a ontologia, as skills e o compose).

# Diagramas gerados do próprio repositório: a doc não desatualiza em relação à demo.
FROM python:3.12-alpine AS diagramas
RUN apk add --no-cache graphviz && pip install --no-cache-dir "pyyaml>=6" "pytest>=8"
WORKDIR /repo
COPY docker-compose.yml ./
COPY services/mcp-gateway/config/ services/mcp-gateway/config/
COPY services/contexto-mcp/ontologia/ services/contexto-mcp/ontologia/
COPY services/skills-mcp/skills/ services/skills-mcp/skills/
COPY services/docs/gerar/ /gerar/
WORKDIR /gerar
RUN RAIZ_DO_REPOSITORIO=/repo python -m pytest -q -p no:cacheprovider && python diagramas.py /repo /saida

FROM squidfunk/mkdocs-material:9 AS build
WORKDIR /docs
COPY services/docs/ ./
COPY docs/assets/infografico_horizontal.jpeg conteudo/assets/infografico.jpeg
COPY --from=diagramas /saida/ conteudo/assets/diagramas/
COPY services/contexto-mcp/ontologia/ ontologia/
COPY services/skills-mcp/skills/ skills/
RUN mkdocs build --strict --site-dir /site

FROM nginx:1.27-alpine
COPY --from=build /site /usr/share/nginx/html
