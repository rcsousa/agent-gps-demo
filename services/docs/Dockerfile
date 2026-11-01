# Build context: raiz do repositório (para incluir o infográfico de docs/assets).
FROM squidfunk/mkdocs-material:9 AS build
WORKDIR /docs
COPY services/docs/ ./
COPY docs/assets/mapa-da-demo.png conteudo/assets/mapa-da-demo.png
COPY services/contexto-mcp/ontologia/ ontologia/
COPY services/skills-mcp/skills/ skills/
RUN mkdocs build --strict --site-dir /site

FROM nginx:1.27-alpine
COPY --from=build /site /usr/share/nginx/html
