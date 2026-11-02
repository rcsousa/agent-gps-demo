# Contexto de build: a raiz do repositório (o infográfico fica em docs/assets).

# Tiles do deep zoom da tela de abertura, gerados do infográfico horizontal (2198×1446).
# O libvips do Debian traz o dzsave (o do Alpine não tem suporte a DZI).
FROM debian:bookworm-slim AS tiles
RUN apt-get update && apt-get install -y --no-install-recommends libvips-tools && rm -rf /var/lib/apt/lists/*
COPY docs/assets/infografico_horizontal.jpeg /entrada/infografico.jpeg
RUN vips dzsave /entrada/infografico.jpeg /saida/infografico --tile-size 512 --suffix ".jpg[Q=86]"

FROM node:22-alpine AS build
WORKDIR /app
COPY services/web/package.json services/web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY services/web/ .
RUN npm run build

FROM nginx:1.27-alpine
COPY services/web/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
COPY --from=tiles /saida/ /usr/share/nginx/html/abertura/
