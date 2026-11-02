# Testes ponta a ponta no navegador (Chromium do Playwright), na rede interna do compose.
# A viagem usa o provedor roteiro: nenhum token é gasto.
FROM mcr.microsoft.com/playwright/python:v1.55.0-noble

# axe-playwright-python traz o axe-core embutido: a auditoria de acessibilidade roda sem rede.
RUN pip install --no-cache-dir --break-system-packages "playwright==1.55.0" "pytest>=8,<9" "axe-playwright-python==0.1.4"
# ffmpeg: os vídeos das cenas para os bastidores (./scripts/capturar-cenas.sh).
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*

WORKDIR /e2e
COPY tests ./tests
COPY capturas.py ensaio.py ./
ENV WEB_URL=http://web
CMD ["pytest", "-v", "tests"]
