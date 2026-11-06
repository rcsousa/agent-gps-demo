# Build context: raiz do repositório (o infográfico, a ontologia, as skills e o compose).

# Diagramas e tabelas gerados do próprio repositório: a doc não desatualiza em relação à demo.
FROM python:3.12-alpine AS diagramas
RUN apk add --no-cache graphviz && pip install --no-cache-dir "pyyaml>=6" "pydantic>=2" "pytest>=8"
# O zoom dos diagramas (svg-pan-zoom), servido pelo próprio site: versão fixa e checksum conferido.
RUN mkdir /vendor \
    && wget -qO /vendor/svg-pan-zoom.min.js https://cdn.jsdelivr.net/npm/svg-pan-zoom@3.6.2/dist/svg-pan-zoom.min.js \
    && echo "9c8fc41b3359e699990766dd7a943595d234a80c880a90dfc14b920a273b99d8  /vendor/svg-pan-zoom.min.js" | sha256sum -c -
WORKDIR /repo
COPY docker-compose.yml ./
COPY gravacoes/ gravacoes/
COPY services/web/nginx.conf services/web/nginx.conf
COPY services/simulator/incidentes.yaml services/simulator/incidentes.yaml
COPY services/smoke/referencia/ services/smoke/referencia/
COPY services/mcp-gateway/config/ services/mcp-gateway/config/
COPY services/contexto-mcp/ontologia/ services/contexto-mcp/ontologia/
COPY services/skills-mcp/skills/ services/skills-mcp/skills/
# Os módulos do agent, do gateway e do contexto-mcp: o diagrama de componentes lê o código.
COPY services/agent/src/agent/ services/agent/src/agent/
COPY services/mcp-gateway/src/mcp_gateway/ services/mcp-gateway/src/mcp_gateway/
COPY services/contexto-mcp/src/contexto_mcp/ services/contexto-mcp/src/contexto_mcp/
COPY services/docs/gerar/ /gerar/
# O mesmo carregador de ontologia que o seed usa para montar o Neo4j (só yaml e pydantic).
ENV PYTHONPATH=/repo/services/contexto-mcp/src
WORKDIR /gerar
RUN RAIZ_DO_REPOSITORIO=/repo python -m pytest -q -p no:cacheprovider \
    && python diagramas.py /repo /saida /gerado

FROM squidfunk/mkdocs-material:9 AS build
WORKDIR /docs
COPY services/docs/ ./
COPY docs/assets/infografico_horizontal.jpeg conteudo/assets/infografico.jpeg
COPY --from=diagramas /saida/ conteudo/assets/diagramas/
COPY --from=diagramas /vendor/ conteudo/javascripts/vendor/
COPY --from=diagramas /gerado/ gerado/
COPY services/contexto-mcp/ontologia/ ontologia/
COPY services/skills-mcp/skills/ skills/
# Código real, citado por trecho (marcadores --8<-- no próprio código): a doc mostra o que roda.
COPY services/mcp-gateway/src/mcp_gateway/servidor_mcp.py codigo/gateway/servidor_mcp.py
COPY services/mcp-gateway/src/mcp_gateway/catalogo.py codigo/gateway/catalogo.py
COPY services/contexto-mcp/src/contexto_mcp/grafo.py codigo/contexto/grafo.py
COPY services/contexto-mcp/src/contexto_mcp/seed.py codigo/contexto/seed.py
COPY libs/bussola_comum/src/bussola_comum/regras.py codigo/comum/regras.py
COPY services/web/src/mapa/diretor.ts codigo/web/diretor.ts
RUN mkdocs build --strict --site-dir /site

FROM nginx:1.27-alpine
COPY --from=build /site /usr/share/nginx/html
